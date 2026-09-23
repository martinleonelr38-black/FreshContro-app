import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "freshcontrol.db")

def obtener_conexion():
    """Crea y retorna la conexión con la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_bd():
    """Crea las tablas de usuarios, productos y movimientos si no existen."""
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            telefono TEXT NOT NULL,
            cargo TEXT,
            rol TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_barras TEXT UNIQUE,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio REAL DEFAULT 0.0,
            stock INTEGER DEFAULT 0,
            fecha_vencimiento DATE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL,
            id_usuario INTEGER NOT NULL,
            tipo TEXT NOT NULL, -- 'Entrada' o 'Salida'
            cantidad INTEGER NOT NULL,
            fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            detalle TEXT,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        )
    """)

    conn.commit()
    conn.close()

def registrar_usuario(nombre, apellido, usuario, password, email, telefono, cargo="Empleado", rol="empleado"):
    """Inserta un nuevo usuario (gerente o empleado) en la base de datos."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO usuarios (nombre, apellido, usuario, password, email, telefono, cargo, rol)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (nombre, apellido, usuario, password, email, telefono, cargo, rol))
        
        conn.commit()
        conn.close()
        return True, "Usuario registrado exitosamente"
    except sqlite3.IntegrityError:
        return False, "El nombre de usuario ya existe"
    except Exception as e:
        return False, f"Error en la base de datos: {e}"

def verificar_credenciales(usuario, password):
    """Verifica usuario y contraseña en la BD. Retorna la fila si coincide, None si no."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM usuarios WHERE usuario = ? AND password = ?
    """, (usuario, password))
    
    user = cursor.fetchone()
    conn.close()
    return user

# ==========================================
# FUNCIONES DE MÉTRICAS E INVENTARIO
# ==========================================

def obtener_metricas_dashboard():
    """
    Retorna un diccionario con las métricas para los paneles.
    Si no hay datos, todos los valores serán 0.
    """
    conn = obtener_conexion()
    cursor = conn.cursor()

    # Total de productos distintos
    cursor.execute("SELECT COALESCE(COUNT(*), 0) FROM productos")
    total_productos = cursor.fetchone()[0]

    # Productos con stock bajo (ejemplo: <= 5 unidades)
    cursor.execute("SELECT COALESCE(COUNT(*), 0) FROM productos WHERE stock <= 5")
    stock_bajo = cursor.fetchone()[0]

    # Productos por vencer (en los próximos 7 días)
    cursor.execute("""
        SELECT COALESCE(COUNT(*), 0) FROM productos 
        WHERE fecha_vencimiento BETWEEN DATE('now') AND DATE('now', '+7 days')
    """)
    por_vencer = cursor.fetchone()[0]

    # Productos vencidos
    cursor.execute("""
        SELECT COALESCE(COUNT(*), 0) FROM productos 
        WHERE fecha_vencimiento < DATE('now')
    """)
    vencidos = cursor.fetchone()[0]

    conn.close()

    return {
        "total_productos": total_productos,
        "stock_bajo": stock_bajo,
        "por_vencer": por_vencer,
        "vencidos": vencidos
    }

def registrar_movimiento(id_producto, id_usuario, tipo, cantidad, detalle=""):
    """
    Registra un movimiento (Entrada/Salida) y actualiza el stock del producto en la misma transacción.
    """
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        # Insertar movimiento
        cursor.execute("""
            INSERT INTO movimientos (id_producto, id_usuario, tipo, cantidad, detalle)
            VALUES (?, ?, ?, ?, ?)
        """, (id_producto, id_usuario, tipo, cantidad, detalle))

        # Actualizar stock en productos
        if tipo.lower() == "entrada":
            cursor.execute("UPDATE productos SET stock = stock + ? WHERE id_producto = ?", (cantidad, id_producto))
        elif tipo.lower() == "salida":
            cursor.execute("UPDATE productos SET stock = MAX(0, stock - ?) WHERE id_producto = ?", (cantidad, id_producto))

        conn.commit()
        conn.close()
        return True, "Movimiento registrado y stock actualizado"
    except Exception as e:
        return False, f"Error al registrar movimiento: {e}"

def obtener_movimientos_recientes(limite=5):
    """
    Obtiene los últimos movimientos con el nombre del producto y el usuario/empleado que los realizó.
    """
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            m.fecha_hora,
            m.tipo,
            p.nombre AS producto,
            m.cantidad,
            (u.nombre || ' ' || u.apellido) AS empleado,
            m.detalle
        FROM movimientos m
        JOIN productos p ON m.id_producto = p.id_producto
        JOIN usuarios u ON m.id_usuario = u.id_usuario
        ORDER BY m.id_movimiento DESC
        LIMIT ?
    """, (limite,))

    movimientos = cursor.fetchall()
    conn.close()
    return movimientos

if __name__ == "__main__":
    inicializar_bd()
    print("Base de datos inicializada correctamente.")