import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "freshcontrol.db")

def obtener_conexion():
    """Crea y retorna la conexión con la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_bd():
    """Crea la tabla unificada de usuarios y demás tablas necesarias."""
    conn = obtener_conexion()
    cursor = conn.cursor()

    # Tabla de Usuarios (Soporta Gerentes y Empleados)
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

    # Tabla de Productos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_barras TEXT UNIQUE,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio REAL,
            stock INTEGER DEFAULT 0,
            fecha_vencimiento DATE
        )
    """)

    conn.commit()
    conn.close()

def registrar_usuario(nombre, apellido, usuario, password, email, telefono, cargo="Gerente", rol="gerente"):
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
        return True, "Registro guardado correctamente"
    except sqlite3.IntegrityError:
        return False, "El nombre de usuario ya existe"
    except Exception as e:
        return False, f"Error al guardar: {e}"

def verificar_credenciales(usuario, password):
    """Consulta la BD y retorna los datos del usuario si coinciden usuario y contraseña."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM usuarios WHERE usuario = ? AND password = ?
    """, (usuario, password))
    
    user = cursor.fetchone()
    conn.close()
    return user

if __name__ == "__main__":
    inicializar_bd()
    print("Base de datos inicializada correctamente.")