from base_de_datos.gestor_bd import GestorBD

def inicializar_tablas():
    bd = GestorBD()
    
    # 1. Proveedores
    bd.ejecutar_comando("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        telefono TEXT,
        correo TEXT
    );
    """)
    
    # 2. Empleados
    bd.ejecutar_comando("""
    CREATE TABLE IF NOT EXISTS empleados (
        id_empleado INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        cargo TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        contrasena TEXT NOT NULL
    );
    """)
    
    # 3. Productos
    bd.ejecutar_comando("""
    CREATE TABLE IF NOT EXISTS productos (
        id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_barras TEXT UNIQUE,
        nombre TEXT NOT NULL,
        categoria TEXT,
        cantidad_stock INTEGER DEFAULT 0,
        unidad_medida TEXT,
        fecha_ingreso DATE,
        fecha_vencimiento DATE,
        id_proveedor INTEGER,
        FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor) ON DELETE SET NULL
    );
    """)
    
    # 4. Movimientos
    bd.ejecutar_comando("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
        id_producto INTEGER NOT NULL,
        tipo_movimiento TEXT NOT NULL,
        cantidad INTEGER NOT NULL,
        fecha_movimiento DATE NOT NULL,
        id_empleado INTEGER NOT NULL,
        FOREIGN KEY (id_producto) REFERENCES productos (id_producto) ON DELETE CASCADE,
        FOREIGN KEY (id_empleado) REFERENCES empleados (id_empleado) ON DELETE CASCADE
    );
    """)

    # 5. Alertas
    bd.ejecutar_comando("""
    CREATE TABLE IF NOT EXISTS alertas (
        id_alerta INTEGER PRIMARY KEY AUTOINCREMENT,
        id_producto INTEGER NOT NULL,
        tipo_alerta TEXT NOT NULL,
        mensaje TEXT NOT NULL,
        fecha_generada DATE NOT NULL,
        leido INTEGER DEFAULT 0,
        FOREIGN KEY (id_producto) REFERENCES productos (id_producto) ON DELETE CASCADE
    );
    """)
    
    print("Base de datos inicializada con éxito.")

if __name__ == "__main__":
    inicializar_tablas()