-- Crear y usar la base de datos analítica
CREATE DATABASE IF NOT EXISTS concesionaria_olap;
USE concesionaria_olap;

-- ==========================================
-- TABLAS DIMENSIÓN (El contexto)
-- ==========================================

-- 1. Dimensión Tiempo
CREATE TABLE dim_tiempo (
    fecha_key INT PRIMARY KEY, -- Formato YYYYMMDD
    fecha DATE NOT NULL,
    dia INT NOT NULL,
    mes INT NOT NULL,
    anio INT NOT NULL,
    trimestre INT NOT NULL,
    dia_semana VARCHAR(20) NOT NULL
);

-- 2. Dimensión Cliente
CREATE TABLE dim_cliente (
    cliente_key INT PRIMARY KEY, -- Usaremos el mismo ID del OLTP
    nombre VARCHAR(150),
    ciudad VARCHAR(100),
    tipo_cliente VARCHAR(50)
);

-- 3. Dimensión Vehículo (Desnormalizada para análisis rápido)
CREATE TABLE dim_vehiculo (
    vehiculo_key VARCHAR(17) PRIMARY KEY, -- Usaremos el VIN
    marca VARCHAR(50),
    modelo VARCHAR(50),
    anio INT,
    condicion VARCHAR(20)
);

-- 4. Dimensión Empleado (Asesores y Técnicos)
CREATE TABLE dim_empleado (
    empleado_key INT PRIMARY KEY,
    nombre VARCHAR(150),
    rol VARCHAR(50)
);

-- ==========================================
-- TABLAS DE HECHOS (Las métricas)
-- ==========================================

-- 1. Hechos: Ventas (Mide la eficiencia comercial)
CREATE TABLE fact_ventas (
    venta_id INT PRIMARY KEY,
    fecha_key INT NOT NULL,
    cliente_key INT NOT NULL,
    vehiculo_key VARCHAR(17) NOT NULL,
    vendedor_key INT NOT NULL,
    precio_venta DECIMAL(10,2) NOT NULL,
    costo_compra DECIMAL(10,2) NOT NULL,
    margen_bruto DECIMAL(10,2) NOT NULL, -- precio_venta - costo_compra
    incluye_garantia BOOLEAN,
    incluye_credito BOOLEAN,
    FOREIGN KEY (fecha_key) REFERENCES dim_tiempo(fecha_key),
    FOREIGN KEY (cliente_key) REFERENCES dim_cliente(cliente_key),
    FOREIGN KEY (vehiculo_key) REFERENCES dim_vehiculo(vehiculo_key),
    FOREIGN KEY (vendedor_key) REFERENCES dim_empleado(empleado_key)
);

-- 2. Hechos: Inventario Snapshot (Mide el "dinero estancado")
-- Esta tabla guarda el estado del inventario para calcular el Ageing
CREATE TABLE fact_inventario (
    vehiculo_key VARCHAR(17) PRIMARY KEY,
    fecha_ingreso_key INT NOT NULL,
    fecha_venta_key INT, -- Puede ser nulo si no se ha vendido
    costo_compra DECIMAL(10,2) NOT NULL,
    estado_actual VARCHAR(30) NOT NULL,
    dias_en_inventario INT NOT NULL, -- Calculado en el ETL
    FOREIGN KEY (vehiculo_key) REFERENCES dim_vehiculo(vehiculo_key),
    FOREIGN KEY (fecha_ingreso_key) REFERENCES dim_tiempo(fecha_key)
);

-- 3. Hechos: Servicios Taller (Mide la postventa)
CREATE TABLE fact_servicios (
    or_id INT PRIMARY KEY,
    fecha_key INT NOT NULL,
    cliente_key INT NOT NULL,
    vehiculo_key VARCHAR(17) NOT NULL,
    tecnico_key INT NOT NULL,
    horas_facturadas DECIMAL(5,2) NOT NULL,
    ingreso_total DECIMAL(10,2) NOT NULL, -- Mano de obra + Repuestos
    FOREIGN KEY (fecha_key) REFERENCES dim_tiempo(fecha_key),
    FOREIGN KEY (cliente_key) REFERENCES dim_cliente(cliente_key),
    FOREIGN KEY (vehiculo_key) REFERENCES dim_vehiculo(vehiculo_key),
    FOREIGN KEY (tecnico_key) REFERENCES dim_empleado(empleado_key)
);