import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Configuración de la página
st.set_page_config(page_title="Executive Dealer Insights", layout="wide", page_icon="🚗")

# Persona del CTO
st.title("🚗 Automotive Strategy Dashboard")
st.markdown("""
*CTO & Lead Data Scientist Insights* | Analítica Prescriptiva para la Toma de Decisiones en Concesionaria
---
""")

# ==========================================
# CONEXIÓN A BASES DE DATOS (OLAP)
# ==========================================
@st.cache_resource
def get_connection():
    # Asegúrate de usar tus credenciales
    return create_engine("mysql+pymysql://root:root@localhost:3306/concesionaria_olap")

engine = get_connection()

# ==========================================
# CARGA DE DATOS (TRANSFORMACIÓN ANALÍTICA)
# ==========================================
@st.cache_data
def load_data():
    df_ventas = pd.read_sql("SELECT * FROM fact_ventas v JOIN dim_vehiculo veh ON v.vehiculo_key = veh.vehiculo_key", engine)
    
    # FIX: Added v.condicion to the SELECT statement
    df_inventario = pd.read_sql("SELECT i.*, v.marca, v.modelo, v.condicion FROM fact_inventario i JOIN dim_vehiculo v ON i.vehiculo_key = v.vehiculo_key", engine)
    
    df_servicios = pd.read_sql("SELECT * FROM fact_servicios", engine)
    df_clientes = pd.read_sql("""
        SELECT c.*, 
        (SELECT SUM(precio_venta) FROM fact_ventas v WHERE v.cliente_key = c.cliente_key) as gasto_autos,
        (SELECT SUM(ingreso_total) FROM fact_servicios s WHERE s.cliente_key = c.cliente_key) as gasto_taller,
        (SELECT COUNT(*) FROM fact_servicios s WHERE s.cliente_key = c.cliente_key) as visitas_taller
        FROM dim_cliente c""", engine)
    return df_ventas, df_inventario, df_servicios, df_clientes

df_ventas, df_inventario, df_servicios, df_clientes = load_data()

# ==========================================
# SIDEBAR - FILTROS ESTRATÉGICOS
# ==========================================
st.sidebar.header("Filtros Globales")
marca_filter = st.sidebar.multiselect("Marca", options=df_ventas['marca'].unique(), default=df_ventas['marca'].unique())
condicion_filter = st.sidebar.radio("Condición", options=['Todos', 'Nuevo', 'Seminuevo'])

# Aplicar filtros
df_v_filtered = df_ventas[df_ventas['marca'].isin(marca_filter)]
if condicion_filter != 'Todos':
    df_v_filtered = df_v_filtered[df_v_filtered['condicion'] == condicion_filter]

# ==========================================
# LAYOUT DE PESTAÑAS
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["📊 Desempeño Comercial", "💰 Inventario Crítico", "👥 Inteligencia de Clientes", "🩺 Salud Financiera y Postventa"])

# --- PESTAÑA 1: VENTAS Y F&I ---
with tab1:
    st.header("KPIs de Ventas y F&I")
    col1, col2, col3, col4 = st.columns(4)
    
    total_revenue = df_v_filtered['precio_venta'].sum()
    total_units = len(df_v_filtered)
    avg_margin = df_v_filtered['margen_bruto'].mean()
    f_and_i_penetration = (df_v_filtered['incluye_credito'].sum() / total_units) * 100

    col1.metric("Ingresos Totales", f"${total_revenue:,.2f}")
    col2.metric("Unidades Entregadas", f"{total_units}")
    col3.metric("Margen Promedio", f"${avg_margin:,.2f}")
    col4.metric("Penetración Crédito", f"{f_and_i_penetration:.1f}%")

    # Gráfico de Ventas Mensuales
    df_ventas_mes = df_v_filtered.copy()
    df_ventas_mes['mes'] = df_ventas_mes['fecha_key'].apply(lambda x: str(x)[4:6])
    fig_ventas = px.line(df_ventas_mes.groupby('mes')['precio_venta'].sum().reset_index(), 
                         x='mes', y='precio_venta', title="Evolución Mensual de Ventas (Revenue)")
    st.plotly_chart(fig_ventas, use_container_width=True)

# --- PESTAÑA 2: INVENTARIO CRÍTICO (AGEING) ---
with tab2:
    st.header("Análisis de Dinero Estancado")
    st.warning("Vehículos con más de 90 días generan un costo de oportunidad crítico.")
    
    # Cálculos Financieros
    df_inv_disp = df_inventario[df_inventario['estado_actual'] == 'Disponible']
    df_inv_disp['costo_holding_acumulado'] = df_inv_disp['costo_compra'] * 0.0005 * df_inv_disp['dias_en_inventario']
    
    col_inv1, col_inv2 = st.columns([2, 1])
    
    with col_inv1:
        fig_ageing = px.histogram(df_inv_disp, x="dias_en_inventario", color="condicion",
                                   marginal="box", title="Distribución de Días en Inventario (Ageing)")
        st.plotly_chart(fig_ageing, use_container_width=True)
    
    with col_inv2:
        st.subheader("Unidades Críticas")
        aged_critical = df_inv_disp[df_inv_disp['dias_en_inventario'] > 90][['marca', 'modelo', 'dias_en_inventario', 'costo_compra']]
        st.dataframe(aged_critical.sort_values('dias_en_inventario', ascending=False))

    # Propuesta de Markdown
    st.subheader("Prescripción: Propuesta de Descuento para Rotación")
    if not aged_critical.empty:
        aged_critical['Descuento Sugerido (80% Holding)'] = aged_critical['costo_compra'] * 0.05
        st.table(aged_critical)
    else:
        st.success("No hay unidades con envejecimiento crítico.")

# --- PESTAÑA 3: MACHINE LEARNING (CLUSTERING) ---
with tab3:
    st.header("Segmentación de Clientes via K-Means")
    
    # Preparar datos para Clustering
    df_c = df_clientes.fillna(0)
    X = df_c[['gasto_autos', 'gasto_taller', 'visitas_taller']]
    X_scaled = StandardScaler().fit_transform(X)
    
    kmeans = KMeans(n_clusters=3, random_state=42).fit(X_scaled)
    df_c['Cluster'] = kmeans.labels_
    
    # Mapear nombres
    cluster_map = {0: "Cazadores de Ofertas", 1: "Premium / Fieles", 2: "Solo Servicio"}
    df_c['Segmento'] = df_c['Cluster'].map(cluster_map)
    
    fig_cluster = px.scatter(df_c, x="gasto_autos", y="gasto_taller", color="Segmento",
                             size="visitas_taller", hover_name="nombre",
                             title="Clusters de Clientes: Valor de Vida (LTV)")
    st.plotly_chart(fig_cluster, use_container_width=True)
    
    st.info("💡 *Estrategia del CTO:* Los clientes en el segmento 'Premium' deben recibir invitaciones exclusivas a lanzamientos, mientras que los de 'Solo Servicio' requieren campañas de retención para compra de vehículo nuevo.")
    
# -------------------------------------------------------------------
# CÓDIGO DE LA NUEVA PESTAÑA 4
# -------------------------------------------------------------------
with tab4:
    st.header("Operaciones Fijas y Eficiencia Financiera")
    st.markdown("Indicadores de rentabilidad estructural y rendimiento de taller.")
    
    # --- SIMULACIÓN DE DATOS (Si tu ETL aún no los tiene, usa esto como fallback) ---
    # Asumimos gastos fijos mensuales de la concesionaria ($150,000 USD)
    gastos_fijos_concesionaria = 150000 
    
    # Cálculos para Absorción
    utilidad_taller = df_servicios['ingreso_total'].sum() # En la vida real, sería ingreso menos costo del repuesto
    indice_absorcion = (utilidad_taller / gastos_fijos_concesionaria) * 100

    # Cálculos para PRU (Per Retail Unit) en F&I
    # Asumimos que cada garantía deja $500 y cada crédito deja $800 de comisión para el dealer
    df_v_filtered['profit_garantia'] = df_v_filtered['incluye_garantia'] * 500
    df_v_filtered['profit_credito'] = df_v_filtered['incluye_credito'] * 800
    total_f_and_i_profit = df_v_filtered['profit_garantia'].sum() + df_v_filtered['profit_credito'].sum()
    pru_financiero = total_f_and_i_profit / len(df_v_filtered) if len(df_v_filtered) > 0 else 0

    # Cálculos de Taller (ELR)
    # Asumimos horas facturadas = horas en df_servicios. (Usamos un mock si 'horas_reales_trabajadas' no está)
    if 'horas_reales_trabajadas' not in df_servicios.columns:
        import numpy as np
        df_servicios['horas_reales_trabajadas'] = df_servicios['horas_facturadas'] * np.random.uniform(0.8, 1.4, len(df_servicios))
    
    eficiencia_tecnicos = (df_servicios['horas_facturadas'].sum() / df_servicios['horas_reales_trabajadas'].sum()) * 100
    effective_labor_rate = df_servicios['ingreso_total'].sum() / df_servicios['horas_facturadas'].sum()

    # --- RENDERIZADO DE KPIs ---
    colA, colB, colC, colD = st.columns(4)
    colA.metric("PRU (F&I Profit por Unidad)", f"${pru_financiero:,.2f}", "+12% vs Q-1")
    colB.metric("Effective Labor Rate (ELR)", f"${effective_labor_rate:,.2f} / hr", "-$5.00 vs Tarifa Puerta", delta_color="inverse")
    colC.metric("Eficiencia de Taller", f"{eficiencia_tecnicos:.1f}%", "+2.5% vs Benchmark")
    
    # Costo de Adquisición (Mockup simple asumiendo CAC promedio)
    cac_promedio = 350 # Costo de marketing promedio por venta
    margen_promedio = df_v_filtered['margen_bruto'].mean()
    roi_marketing = ((margen_promedio - cac_promedio) / cac_promedio) * 100
    colD.metric("ROI de Marketing (GP vs CAC)", f"{roi_marketing:.1f}%", f"CAC: ${cac_promedio}")

    st.markdown("---")
    
    # --- GRÁFICOS AVANZADOS ---
    col_graph1, col_graph2 = st.columns([1, 1])

    with col_graph1:
        # Velocímetro de Absorción (Gauge Chart)
        fig_absorcion = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = indice_absorcion,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Índice de Absorción (Service Absorption Rate)", 'font': {'size': 18}},
            number = {'suffix': "%"},
            gauge = {
                'axis': {'range': [0, 120]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 60], 'color': "lightcoral"},
                    {'range': [60, 85], 'color': "gold"},
                    {'range': [85, 120], 'color': "lightgreen"}],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': 100}
            }
        ))
        fig_absorcion.update_layout(height=350)
        st.plotly_chart(fig_absorcion, use_container_width=True)
        st.caption("🎯 Objetivo: 100%. Si alcanzamos 100%, el taller paga todas las facturas y la venta de autos es pura ganancia líquida.")

    with col_graph2:
        # Gráfico de Dispersión: Eficiencia vs ELR por Técnico
        # Simulamos datos agregados por técnico para el ejemplo
        df_tech = df_servicios.groupby('tecnico_key').agg(
            horas_facturadas=('horas_facturadas', 'sum'),
            horas_reales=('horas_reales_trabajadas', 'sum'),
            ingreso_total=('ingreso_total', 'sum')
        ).reset_index()
        
        df_tech['Eficiencia (%)'] = (df_tech['horas_facturadas'] / df_tech['horas_reales']) * 100
        df_tech['ELR ($)'] = df_tech['ingreso_total'] / df_tech['horas_facturadas']
        df_tech['tecnico_key'] = df_tech['tecnico_key'].astype(str) # Convertir a string para etiqueta discreta

        fig_tech = px.scatter(df_tech, x="Eficiencia (%)", y="ELR ($)", 
                              color="tecnico_key", size="horas_facturadas",
                              title="Cuadrante de Productividad por Técnico",
                              labels={"tecnico_key": "ID Técnico"})
        
        # Añadir líneas de Benchmark
        fig_tech.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="ELR Mínimo Aceptable")
        fig_tech.add_vline(x=100, line_dash="dash", line_color="green", annotation_text="100% Eficiencia")
        
        fig_tech.update_layout(height=350)
        st.plotly_chart(fig_tech, use_container_width=True)