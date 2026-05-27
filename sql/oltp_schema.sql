-- Crear y usar la base de datos
CREATE DATABASE IF NOT EXISTS concesionaria_oltp;
USE concesionaria_oltp;

-- 1. Tabla de Empleados (Vendedores, Técnicos, F&I)
CREATE TABLE empleados (
    empleado_id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_completo VARCHAR(150) NOT NULL,
    rol VARCHAR(50) NOT NULL -- 'Ventas', 'Tecnico', 'F&I'
);

-- 2. Tabla de Clientes
CREATE TABLE clientes (
    cliente_id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    email VARCHAR(100),
    telefono VARCHAR(20),
    ciudad VARCHAR(100),
    tipo_cliente VARCHAR(50) -- 'Regular', 'Premium'
);

-- 3. Tabla de Vehículos (Inventario)
CREATE TABLE vehiculos (
    vin VARCHAR(17) PRIMARY KEY,
    marca VARCHAR(50) NOT NULL,
    modelo VARCHAR(50) NOT NULL,
    anio INT NOT NULL,
    condicion VARCHAR(20) NOT NULL, -- 'Nuevo', 'Seminuevo'
    costo_compra DECIMAL(10,2) NOT NULL,
    estado_inventario VARCHAR(30) NOT NULL, -- 'Disponible', 'Vendido', 'En Recon'
    fecha_ingreso DATE NOT NULL
);

-- 4. Tabla de Leads (CRM)
CREATE TABLE leads (
    lead_id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    vehiculo_interes_vin VARCHAR(17),
    vendedor_id INT NOT NULL,
    fecha_creacion DATE NOT NULL,
    estado_lead VARCHAR(30) NOT NULL, -- 'Nuevo', 'Test Drive', 'Negociacion', 'Cerrado', 'Perdido'
    motivo_perdida VARCHAR(100), -- Ej. 'Precio alto', 'Compró en competencia'
    FOREIGN KEY (cliente_id) REFERENCES clientes(cliente_id),
    FOREIGN KEY (vehiculo_interes_vin) REFERENCES vehiculos(vin),
    FOREIGN KEY (vendedor_id) REFERENCES empleados(empleado_id)
);

-- 5. Tabla de Ventas (F&I y Cierres)
CREATE TABLE ventas (
    venta_id INT AUTO_INCREMENT PRIMARY KEY,
    lead_id INT NOT NULL,
    cliente_id INT NOT NULL,
    vehiculo_vin VARCHAR(17) NOT NULL,
    vendedor_id INT NOT NULL,
    fecha_venta DATE NOT NULL,
    precio_venta DECIMAL(10,2) NOT NULL,
    incluye_garantia_ext BOOLEAN DEFAULT FALSE,
    incluye_credito BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(cliente_id),
    FOREIGN KEY (vehiculo_vin) REFERENCES vehiculos(vin),
    FOREIGN KEY (vendedor_id) REFERENCES empleados(empleado_id)
);

-- 6. Tabla de Órdenes de Reparación (Postventa/Taller)
CREATE TABLE ordenes_reparacion (
    or_id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    vehiculo_vin VARCHAR(17) NOT NULL,
    tecnico_id INT NOT NULL,
    fecha_apertura DATE NOT NULL,
    horas_facturadas DECIMAL(5,2) NOT NULL,
    costo_repuestos DECIMAL(10,2) NOT NULL,
    costo_mano_obra DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (cliente_id) REFERENCES clientes(cliente_id),
    FOREIGN KEY (vehiculo_vin) REFERENCES vehiculos(vin),
    FOREIGN KEY (tecnico_id) REFERENCES empleados(empleado_id)
);