import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine
import warnings
warnings.filterwarnings('ignore')

# Configuración visual para los gráficos
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)

# ==========================================
# 1. CONEXIÓN AL DATA WAREHOUSE (OLAP)
# ==========================================
# Reemplaza con tus credenciales
engine = create_engine("mysql+pymysql://root:2006@localhost:3306/concesionaria_olap")
print("Conectado al OLAP. Extrayendo inteligencia de negocio...")

# ==========================================
# 2. MODELO DE CLUSTERING (K-MEANS): SEGMENTACIÓN DE CLIENTES
# ==========================================
print("\n--- Ejecutando Segmentación de Clientes ---")

# Consulta SQL analítica: Agregamos el comportamiento del cliente en Ventas y Taller
query_clientes = """
SELECT 
    c.cliente_key,
    c.nombre,
    COUNT(DISTINCT v.venta_id) as autos_comprados,
    COALESCE(SUM(v.precio_venta), 0) as gastado_autos,
    COALESCE(AVG(v.margen_bruto / v.precio_venta), 0) as porcentaje_margen,
    COUNT(DISTINCT s.or_id) as visitas_taller,
    COALESCE(SUM(s.ingreso_total), 0) as gastado_taller
FROM dim_cliente c
LEFT JOIN fact_ventas v ON c.cliente_key = v.cliente_key
LEFT JOIN fact_servicios s ON c.cliente_key = s.cliente_key
GROUP BY c.cliente_key, c.nombre
HAVING autos_comprados > 0 OR visitas_taller > 0;
"""
df_clientes = pd.read_sql(query_clientes, con=engine)

# Selección de features para el K-Means
features = ['gastado_autos', 'porcentaje_margen', 'visitas_taller', 'gastado_taller']
X = df_clientes[features]

# Escalar los datos (vital para K-Means)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Entrenar el modelo
kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
df_clientes['cluster'] = kmeans.fit_predict(X_scaled)

# Asignar nombres comerciales a los clusters basándonos en los centroides
# (Lógica simplificada: mayor margen y autos = Premium, bajo margen = Buscadores, solo taller = Solo Servicio)
cluster_means = df_clientes.groupby('cluster')[features].mean()

def nombrar_cluster(row):
    if row['gastado_autos'] == 0 and row['visitas_taller'] > 0:
        return 'Solo Servicio'
    elif row['porcentaje_margen'] < cluster_means['porcentaje_margen'].mean():
        return 'Buscadores de Ofertas'
    else:
        return 'Premium / Fieles'

df_clientes['Segmento'] = df_clientes.apply(nombrar_cluster, axis=1)

print("Distribución de Clientes:")
print(df_clientes['Segmento'].value_counts())

# Gráfico 1: Scatter plot de Clientes
plt.figure()
sns.scatterplot(data=df_clientes, x='gastado_autos', y='gastado_taller', hue='Segmento', palette='viridis', s=100, alpha=0.7)
plt.title("Segmentación de Clientes (LTV Autos vs Taller)", fontsize=14, fontweight='bold')
plt.xlabel("Monto Gastado en Vehículos ($)")
plt.ylabel("Monto Gastado en Taller ($)")
plt.savefig("grafico_segmentacion_clientes.png")
print("-> Gráfico guardado como 'grafico_segmentacion_clientes.png'")

# ==========================================
# 3. REPORTE PRESCRIPTIVO: DINERO ESTANCADO Y COSTO DE OPORTUNIDAD
# ==========================================
print("\n--- Ejecutando Análisis de Inventario y Floorplan ---")

# Extraer inventario disponible
query_inventario = """
SELECT 
    i.vehiculo_key,
    v.marca,
    v.modelo,
    v.condicion,
    i.costo_compra,
    i.dias_en_inventario
FROM fact_inventario i
JOIN dim_vehiculo v ON i.vehiculo_key = v.vehiculo_key
WHERE i.estado_actual = 'Disponible'
"""
df_inventario = pd.read_sql(query_inventario, con=engine)

# Variables Financieras Asumidas
TASA_INTERES_ANUAL = 0.08 # 8% anual de Floorplan
DEPRECIACION_MENSUAL = 0.015 # 1.5% mensual de pérdida de valor comercial

# Cálculo del Daily Holding Cost (Costo Financiero Diario)
tasa_diaria_total = (TASA_INTERES_ANUAL / 365) + (DEPRECIACION_MENSUAL / 30)

df_inventario['costo_diario'] = df_inventario['costo_compra'] * tasa_diaria_total
df_inventario['perdida_acumulada'] = df_inventario['costo_diario'] * df_inventario['dias_en_inventario']

# Filtrar autos críticos (> 90 días)
aged_inventory = df_inventario[df_inventario['dias_en_inventario'] > 90].copy()

# Algoritmo de Propuesta de Descuento (Price Markdown)
# Lógica: Es mejor descontar el 80% de lo que ya hemos perdido en costo financiero para mover el auto HOY, 
# antes de seguir perdiendo dinero mañana.
aged_inventory['descuento_sugerido'] = aged_inventory['perdida_acumulada'] * 0.8
aged_inventory['nuevo_precio_minimo'] = aged_inventory['costo_compra'] - aged_inventory['descuento_sugerido']

print(f"\nAlerta: Tienes {len(aged_inventory)} vehículos con más de 90 días.")
print(f"Pérdida financiera acumulada total: ${aged_inventory['perdida_acumulada'].sum():,.2f}")

if not aged_inventory.empty:
    print("\nTop 5 Vehículos Críticos a Descontar:")
    print(aged_inventory[['marca', 'modelo', 'dias_en_inventario', 'costo_compra', 'perdida_acumulada', 'descuento_sugerido']].head())

# Gráfico 2: Distribución de Ageing y Pérdida
plt.figure()
sns.histplot(data=df_inventario, x='dias_en_inventario', weights='perdida_acumulada', bins=20, color='darkred', kde=True)
plt.axvline(90, color='black', linestyle='--', label='Límite Crítico (90 días)')
plt.title("Costo Financiero Estancado vs Edad del Inventario", fontsize=14, fontweight='bold')
plt.xlabel("Días en Inventario (Ageing)")
plt.ylabel("Pérdida Acumulada ($ USD)")
plt.legend()
plt.savefig("grafico_dinero_estancado.png")
print("-> Gráfico guardado como 'grafico_dinero_estancado.png'")

# ==========================================
# 4. CUADRO DE MANDO: EFICIENCIA DE VENDEDORES (F&I UPSELL)
# ==========================================
print("\n--- Analizando Rentabilidad por Vendedor (Front-End vs Back-End) ---")

query_ventas = """
SELECT 
    e.nombre as vendedor,
    COUNT(v.venta_id) as total_unidades,
    SUM(v.margen_bruto) as utilidad_metal,
    SUM(CASE WHEN v.incluye_garantia = 1 THEN 1 ELSE 0 END) as ventas_garantia,
    SUM(CASE WHEN v.incluye_credito = 1 THEN 1 ELSE 0 END) as ventas_credito
FROM fact_ventas v
JOIN dim_empleado e ON v.vendedor_key = e.empleado_key
GROUP BY e.nombre
"""
df_rendimiento = pd.read_sql(query_ventas, con=engine)

# Calcular penetración
df_rendimiento['penetracion_back_end'] = ((df_rendimiento['ventas_garantia'] + df_rendimiento['ventas_credito']) / (df_rendimiento['total_unidades'] * 2)) * 100

# Gráfico 3: Rentabilidad vs Penetración de Seguros/Créditos
plt.figure()
sns.barplot(data=df_rendimiento.sort_values('utilidad_metal', ascending=False).head(10), 
            x='utilidad_metal', y='vendedor', color='steelblue', label='Utilidad Metal (Front-End)')

# Eje secundario para la penetración
ax2 = plt.twiny()
sns.scatterplot(data=df_rendimiento.sort_values('utilidad_metal', ascending=False).head(10), 
                x='penetracion_back_end', y='vendedor', color='orange', s=150, label='Penetración F&I (%)', ax=ax2)

plt.title("Top Vendedores: Utilidad Bruta vs Eficiencia en F&I (Seguros/Créditos)", fontsize=14, fontweight='bold')
plt.savefig("grafico_eficiencia_vendedores.png")
print("-> Gráfico guardado como 'grafico_eficiencia_vendedores.png'")

print("\n¡Análisis completo! Los reportes están listos para la junta con el Gerente General.")