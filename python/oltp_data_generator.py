# -*- coding: utf-8 -*-
import pandas as pd
import random
from faker import Faker
from datetime import timedelta
from sqlalchemy import create_engine

# Inicializar Faker
fake = Faker('es_MX') # Genera datos en español
Faker.seed(42)
random.seed(42)

# ==========================================
# 1. CONEXIÓN A MYSQL
# ==========================================
# Cambia 'usuario' y 'password' por tus credenciales locales de MySQL
# Formato: mysql+pymysql://usuario:contraseña@localhost:3306/nombre_bd
engine = create_engine("mysql+pymysql://root:root@localhost:3306/concesionaria_oltp")

print("Conexión exitosa a MySQL. Iniciando generación de datos...")

# ==========================================
# 2. GENERACIÓN DE EMPLEADOS
# ==========================================
empleados = []
roles = ['Ventas', 'Tecnico', 'F&I']
for i in range(1, 21):
    empleados.append({
        'empleado_id': i,
        'nombre_completo': fake.name(),
        'rol': random.choices(roles, weights=[50, 40, 10])[0] # Más vendedores y técnicos
    })
df_empleados = pd.DataFrame(empleados)
vendedores_ids = df_empleados[df_empleados['rol'] == 'Ventas']['empleado_id'].tolist()
tecnicos_ids = df_empleados[df_empleados['rol'] == 'Tecnico']['empleado_id'].tolist()

# ==========================================
# 3. GENERACIÓN DE CLIENTES
# ==========================================
clientes = []
for i in range(1, 501):
    clientes.append({
        'cliente_id': i,
        'nombre': fake.name(),
        'email': fake.ascii_free_email(),
        'telefono': fake.phone_number(),
        'ciudad': fake.city(),
        'tipo_cliente': random.choices(['Regular', 'Premium'], weights=[80, 20])[0]
    })
df_clientes = pd.DataFrame(clientes)

# ==========================================
# 4. GENERACIÓN DE VEHÍCULOS
# ==========================================
marcas_modelos = {
    'Toyota': ['Corolla', 'RAV4', 'Hilux'],
    'Ford': ['Escape', 'F-150', 'Explorer'],
    'Honda': ['Civic', 'CR-V', 'Accord'],
    'Nissan': ['Sentra', 'Versa', 'Frontier']
}

vehiculos = []
vines_generados = []
for _ in range(300):
    vin = fake.bothify(text='?#?#??##?##??????', letters='ABCDEFGHJKLMNPRSTUVWXYZ')
    marca = random.choice(list(marcas_modelos.keys()))
    modelo = random.choice(marcas_modelos[marca])
    anio = random.randint(2018, 2024)
    condicion = 'Nuevo' if anio >= 2023 else 'Seminuevo'
    fecha_ingreso = fake.date_between(start_date='-2y', end_date='today')
    
    vehiculos.append({
        'vin': vin,
        'marca': marca,
        'modelo': modelo,
        'anio': anio,
        'condicion': condicion,
        'costo_compra': round(random.uniform(15000, 45000), 2),
        'estado_inventario': 'Disponible', # Se actualizará luego si se vende
        'fecha_ingreso': fecha_ingreso
    })
    vines_generados.append(vin)
df_vehiculos = pd.DataFrame(vehiculos)

# ==========================================
# 5. GENERACIÓN DE LEADS & VENTAS (Logica de negocio)
# ==========================================
leads = []
ventas = []
motivos_perdida = ['Precio alto', 'No aprobó crédito', 'Compró en competencia', 'Solo mirando']

lead_id_counter = 1
venta_id_counter = 1

for vin in vines_generados:
    vehiculo = df_vehiculos[df_vehiculos['vin'] == vin].iloc[0]
    fecha_ingreso = vehiculo['fecha_ingreso']
    
    # Cada vehículo genera entre 1 y 3 leads
    num_leads = random.randint(1, 3)
    fue_vendido = False
    
    for _ in range(num_leads):
        if fue_vendido:
            break # Si ya se vendió, no genera más leads
            
        cliente_id = random.randint(1, 500)
        vendedor_id = random.choice(vendedores_ids)
        # El lead se crea DESPUÉS del ingreso del vehículo
        fecha_creacion_lead = fecha_ingreso + timedelta(days=random.randint(1, 30))
        
        # Probabilidad de cierre: 30%
        estado_lead = random.choices(
            ['Nuevo', 'Test Drive', 'Negociacion', 'Cerrado', 'Perdido'], 
            weights=[10, 20, 20, 30, 20]
        )[0]
        
        motivo = random.choice(motivos_perdida) if estado_lead == 'Perdido' else None
        
        leads.append({
            'lead_id': lead_id_counter,
            'cliente_id': cliente_id,
            'vehiculo_interes_vin': vin,
            'vendedor_id': vendedor_id,
            'fecha_creacion': fecha_creacion_lead,
            'estado_lead': estado_lead,
            'motivo_perdida': motivo
        })
        
        if estado_lead == 'Cerrado':
            fue_vendido = True
            # Venta ocurre entre 1 y 15 días después del lead
            fecha_venta = fecha_creacion_lead + timedelta(days=random.randint(1, 15))
            precio_venta = vehiculo['costo_compra'] * random.uniform(1.05, 1.25) # Margen de ganancia
            
            ventas.append({
                'venta_id': venta_id_counter,
                'lead_id': lead_id_counter,
                'cliente_id': cliente_id,
                'vehiculo_vin': vin,
                'vendedor_id': vendedor_id,
                'fecha_venta': fecha_venta,
                'precio_venta': round(precio_venta, 2),
                'incluye_garantia_ext': random.choice([True, False]),
                'incluye_credito': random.choice([True, False])
            })
            # Actualizar estado de inventario
            df_vehiculos.loc[df_vehiculos['vin'] == vin, 'estado_inventario'] = 'Vendido'
            venta_id_counter += 1
            
        lead_id_counter += 1

df_leads = pd.DataFrame(leads)
df_ventas = pd.DataFrame(ventas)

# ==========================================
# 6. GENERACIÓN DE ÓRDENES DE REPARACIÓN (Taller)
# ==========================================
ordenes = []
or_id_counter = 1

# Solo entran al taller vehículos que ya fueron vendidos
for index, venta in df_ventas.iterrows():
    # Probabilidad del 60% de que vuelva al servicio al menos una vez
    if random.random() < 0.6:
        num_visitas = random.randint(1, 3)
        ultima_fecha = venta['fecha_venta']
        
        for _ in range(num_visitas):
            # Visita al taller ocurre después de la venta (ej. mantenimientos cada 6 meses)
            fecha_apertura = ultima_fecha + timedelta(days=random.randint(90, 180))
            tecnico_id = random.choice(tecnicos_ids)
            horas = round(random.uniform(1.0, 5.0), 2)
            
            ordenes.append({
                'or_id': or_id_counter,
                'cliente_id': venta['cliente_id'],
                'vehiculo_vin': venta['vehiculo_vin'],
                'tecnico_id': tecnico_id,
                'fecha_apertura': fecha_apertura,
                'horas_facturadas': horas,
                'costo_repuestos': round(random.uniform(50, 400), 2),
                'costo_mano_obra': round(horas * 60, 2) # $60 por hora
            })
            ultima_fecha = fecha_apertura
            or_id_counter += 1

df_ordenes = pd.DataFrame(ordenes)

# ==========================================
# 7. CARGA DE DATOS A MYSQL (LOAD)
# ==========================================
print("Cargando datos a la base de datos OLTP...")

# Importante: El orden importa debido a las llaves foráneas (Foreign Keys)
df_empleados.to_sql('empleados', con=engine, if_exists='append', index=False)
df_clientes.to_sql('clientes', con=engine, if_exists='append', index=False)
df_vehiculos.to_sql('vehiculos', con=engine, if_exists='append', index=False)
df_leads.to_sql('leads', con=engine, if_exists='append', index=False)
df_ventas.to_sql('ventas', con=engine, if_exists='append', index=False)
df_ordenes.to_sql('ordenes_reparacion', con=engine, if_exists='append', index=False)

print("¡Proceso completado con éxito! El sistema transaccional está listo.")