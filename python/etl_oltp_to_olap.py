import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# ==========================================
# 1. CONEXIONES A MYSQL
# ==========================================
# Reemplaza con tus credenciales
engine_oltp = create_engine("mysql+pymysql://root:@localhost:3306/concesionaria_oltp")
engine_olap = create_engine("mysql+pymysql://root:@localhost:3306/concesionaria_olap")

print("Conexiones establecidas. Iniciando proceso ETL...")

# ==========================================
# 2. EXTRACT (Extracción desde OLTP)
# ==========================================
print("Extrayendo datos del OLTP...")
df_empleados = pd.read_sql("SELECT * FROM empleados", con=engine_oltp)
df_clientes = pd.read_sql("SELECT * FROM clientes", con=engine_oltp)
df_vehiculos = pd.read_sql("SELECT * FROM vehiculos", con=engine_oltp)
df_ventas = pd.read_sql("SELECT * FROM ventas", con=engine_oltp)
df_ordenes = pd.read_sql("SELECT * FROM ordenes_reparacion", con=engine_oltp)

# ==========================================
# 3. TRANSFORM (Transformación)
# ==========================================
print("Transformando datos para el modelo OLAP...")

# 3.1 Crear Dimensión Tiempo Dinámica
def generar_dim_tiempo(start_date, end_date):
    date_range = pd.date_range(start=start_date, end=end_date)
    dim_tiempo = pd.DataFrame({
        'fecha': date_range,
        'fecha_key': date_range.strftime('%Y%m%d').astype(int),
        'dia': date_range.day,
        'mes': date_range.month,
        'anio': date_range.year,
        'trimestre': date_range.quarter,
        'dia_semana': date_range.day_name() # En inglés, se puede mapear a español si se desea
    })
    return dim_tiempo

# Encontrar fecha mínima y máxima entre ventas, órdenes e ingresos
fechas_todas = pd.concat([df_ventas['fecha_venta'], df_ordenes['fecha_apertura'], df_vehiculos['fecha_ingreso']])
fecha_min = fechas_todas.min()
fecha_max = fechas_todas.max() # O datetime.today().date()
dim_tiempo = generar_dim_tiempo(fecha_min, fecha_max)

# 3.2 Transformar Dimensiones Clientes, Vehículos, Empleados
dim_cliente = df_clientes[['cliente_id', 'nombre', 'ciudad', 'tipo_cliente']].rename(columns={'cliente_id': 'cliente_key'})
dim_vehiculo = df_vehiculos[['vin', 'marca', 'modelo', 'anio', 'condicion']].rename(columns={'vin': 'vehiculo_key'})
dim_empleado = df_empleados[['empleado_id', 'nombre_completo', 'rol']].rename(columns={'empleado_id': 'empleado_key', 'nombre_completo': 'nombre'})

# 3.3 Transformar Fact Ventas
fact_ventas = df_ventas.copy()
fact_ventas['fecha_key'] = pd.to_datetime(fact_ventas['fecha_venta']).dt.strftime('%Y%m%d').astype(int)
# Unir con vehiculos para traer el costo y calcular el margen bruto
fact_ventas = fact_ventas.merge(df_vehiculos[['vin', 'costo_compra']], left_on='vehiculo_vin', right_on='vin', how='left')
fact_ventas['margen_bruto'] = fact_ventas['precio_venta'] - fact_ventas['costo_compra']

fact_ventas = fact_ventas[[
    'venta_id', 'fecha_key', 'cliente_id', 'vehiculo_vin', 'vendedor_id', 
    'precio_venta', 'costo_compra', 'margen_bruto', 'incluye_garantia_ext', 'incluye_credito'
]].rename(columns={
    'cliente_id': 'cliente_key', 
    'vehiculo_vin': 'vehiculo_key', 
    'vendedor_id': 'vendedor_key',
    'incluye_garantia_ext': 'incluye_garantia'
})

# 3.4 Transformar Fact Servicios (Taller)
fact_servicios = df_ordenes.copy()
fact_servicios['fecha_key'] = pd.to_datetime(fact_servicios['fecha_apertura']).dt.strftime('%Y%m%d').astype(int)
fact_servicios['ingreso_total'] = fact_servicios['costo_repuestos'] + fact_servicios['costo_mano_obra']

fact_servicios = fact_servicios[[
    'or_id', 'fecha_key', 'cliente_id', 'vehiculo_vin', 'tecnico_id', 'horas_facturadas', 'ingreso_total'
]].rename(columns={
    'cliente_id': 'cliente_key',
    'vehiculo_vin': 'vehiculo_key',
    'tecnico_id': 'tecnico_key'
})

# 3.5 Transformar Fact Inventario (Ageing)
fact_inventario = df_vehiculos[['vin', 'fecha_ingreso', 'costo_compra', 'estado_inventario']].copy()
fact_inventario['fecha_ingreso_key'] = pd.to_datetime(fact_inventario['fecha_ingreso']).dt.strftime('%Y%m%d').astype(int)

# Buscar fecha de venta (si existe)
ventas_fechas = df_ventas[['vehiculo_vin', 'fecha_venta']].copy()
ventas_fechas['fecha_venta_key'] = pd.to_datetime(ventas_fechas['fecha_venta']).dt.strftime('%Y%m%d').astype(int)

fact_inventario = fact_inventario.merge(ventas_fechas, left_on='vin', right_on='vehiculo_vin', how='left')

# Calcular días en inventario
fecha_hoy = pd.to_datetime(datetime.today().date())
fact_inventario['fecha_ingreso'] = pd.to_datetime(fact_inventario['fecha_ingreso'])
fact_inventario['fecha_venta'] = pd.to_datetime(fact_inventario['fecha_venta'])

# Si se vendió, los días son fecha_venta - fecha_ingreso. Si no, hoy - fecha_ingreso
fact_inventario['dias_en_inventario'] = fact_inventario.apply(
    lambda row: (row['fecha_venta'] - row['fecha_ingreso']).days if pd.notnull(row['fecha_venta']) else (fecha_hoy - row['fecha_ingreso']).days,
    axis=1
)

fact_inventario = fact_inventario[[
    'vin', 'fecha_ingreso_key', 'fecha_venta_key', 'costo_compra', 'estado_inventario', 'dias_en_inventario'
]].rename(columns={'vin': 'vehiculo_key', 'estado_inventario': 'estado_actual'})
# Convertir NaN a None (o un valor int por defecto) para MySQL en fecha_venta_key
fact_inventario['fecha_venta_key'] = fact_inventario['fecha_venta_key'].astype('Int64')

# ==========================================
# 4. LOAD (Carga al OLAP)
# ==========================================
print("Cargando datos al Data Warehouse (OLAP)...")

# Cargar Dimensiones primero (por las llaves foráneas)
dim_tiempo.to_sql('dim_tiempo', con=engine_olap, if_exists='append', index=False)
dim_cliente.to_sql('dim_cliente', con=engine_olap, if_exists='append', index=False)
dim_vehiculo.to_sql('dim_vehiculo', con=engine_olap, if_exists='append', index=False)
dim_empleado.to_sql('dim_empleado', con=engine_olap, if_exists='append', index=False)

# Cargar Hechos
fact_ventas.to_sql('fact_ventas', con=engine_olap, if_exists='append', index=False)
fact_servicios.to_sql('fact_servicios', con=engine_olap, if_exists='append', index=False)
fact_inventario.to_sql('fact_inventario', con=engine_olap, if_exists='append', index=False)

print("¡Proceso ETL completado con éxito! El Data Warehouse está listo para ser analizado.")