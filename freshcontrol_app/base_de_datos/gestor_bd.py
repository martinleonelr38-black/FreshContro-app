import sqlite3
import os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "freshcontrol.db")


class GestorBD:
    """Clase para ejecutar comandos directos en la base de datos."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def obtener_conexion(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ejecutar_comando(self, sql, parametros=()):
        conn = self.obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(sql, parametros)
        conn.commit()
        conn.close()
        return True

    def ejecutar_consulta(self, sql, parametros=()):
        conn = self.obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(sql, parametros)
        rows = cursor.fetchall()
        conn.close()
        return [tuple(row) for row in rows]

    def listar_productos_por_categoria(self):
        conn = self.obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT categoria, COUNT(*) AS total, COALESCE(SUM(cantidad_stock), 0) AS stock_total
            FROM productos
            GROUP BY categoria
            ORDER BY categoria ASC
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [tuple(row) for row in rows]

    def listar_proveedores(self):
        conn = self.obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT id_proveedor, nombre, telefono, correo FROM proveedores ORDER BY nombre ASC")
        rows = cursor.fetchall()
        conn.close()
        return [tuple(row) for row in rows]

    def registrar_proveedor(self, nombre, telefono="", correo=""):
        try:
            conn = self.obtener_conexion()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO proveedores (nombre, telefono, correo) VALUES (?, ?, ?)",
                (nombre, telefono, correo),
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def obtener_productos_por_vencer(self, dias=7):
        conn = self.obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id_producto, nombre, categoria, cantidad_stock, fecha_vencimiento
            FROM productos
            WHERE fecha_vencimiento IS NOT NULL AND fecha_vencimiento <= date('now', '+' || ? || ' days')
            ORDER BY fecha_vencimiento ASC
            """,
            (dias,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [tuple(row) for row in rows]

    def obtener_notificaciones_gerente(self, dias=7):
        notificaciones = []
        conn = self.obtener_conexion()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT nombre, categoria, cantidad_stock, fecha_vencimiento
            FROM productos
            WHERE fecha_vencimiento IS NOT NULL AND fecha_vencimiento <= date('now', '+' || ? || ' days')
            ORDER BY fecha_vencimiento ASC
            """,
            (dias,),
        )
        for nombre, categoria, stock, fecha in cursor.fetchall():
            fecha_hoy = date.today()
            fecha_prod = date.fromisoformat(fecha)
            dias_restantes = (fecha_prod - fecha_hoy).days
            if dias_restantes < 0:
                detalle = f"{nombre} vencido hace {abs(dias_restantes)} días"
            else:
                detalle = f"{nombre} vence en {dias_restantes} días"
            notificaciones.append(("Vencimiento", detalle, categoria, stock, fecha))

        cursor.execute(
            """
            SELECT nombre, categoria, cantidad_stock
            FROM productos
            WHERE cantidad_stock <= 5
            ORDER BY cantidad_stock ASC
            """
        )
        for nombre, categoria, stock in cursor.fetchall():
            notificaciones.append(("Stock bajo", f"{nombre} ({categoria}) tiene {stock} unidades disponibles", categoria, stock, "-"))

        conn.close()
        return notificaciones

    def listar_movimientos(self, limite=20):
        conn = self.obtener_conexion()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT m.id_movimiento, p.nombre, p.categoria, m.tipo, m.cantidad, m.fecha_hora, m.detalle
            FROM movimientos m
            JOIN productos p ON p.id_producto = m.id_producto
            ORDER BY m.id_movimiento DESC
            LIMIT ?
            """,
            (limite,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [tuple(row) for row in rows]

    def get_stock_column_name(self):
        conn = self.obtener_conexion()
        columnas = [row[1] for row in conn.execute("PRAGMA table_info(productos)").fetchall()]
        conn.close()
        if "cantidad_stock" in columnas:
            return "cantidad_stock"
        if "stock" in columnas:
            return "stock"
        return "cantidad_stock"


def obtener_conexion():
    """Crea y retorna la conexión con la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def migrar_esquema_productos():
    """Ajusta la tabla productos para soportar stock y atributos del panel sin duplicar columnas."""
    conn = obtener_conexion()
    columnas = [row[1] for row in conn.execute("PRAGMA table_info(productos)").fetchall()]

    if "cantidad_stock" not in columnas and "stock" in columnas:
        conn.execute("ALTER TABLE productos RENAME TO productos_legacy")
        conn.execute(
            """
            CREATE TABLE productos (
                id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_barras TEXT UNIQUE,
                nombre TEXT NOT NULL,
                categoria TEXT,
                precio REAL DEFAULT 0.0,
                cantidad_stock INTEGER DEFAULT 0,
                fecha_vencimiento DATE,
                id_proveedor INTEGER,
                pasillo TEXT DEFAULT 'A',
                imagen TEXT DEFAULT '',
                FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO productos (id_producto, codigo_barras, nombre, categoria, precio, cantidad_stock, fecha_vencimiento, id_proveedor, pasillo, imagen)
            SELECT id_producto, codigo_barras, nombre, categoria, precio, stock, fecha_vencimiento, id_proveedor, 'A', ''
            FROM productos_legacy
            """
        )
        conn.execute("DROP TABLE productos_legacy")

    columnas = [row[1] for row in conn.execute("PRAGMA table_info(productos)").fetchall()]
    for nombre_columna, default in (("pasillo", "'A'"), ("imagen", "''")):
        if nombre_columna not in columnas:
            conn.execute(f"ALTER TABLE productos ADD COLUMN {nombre_columna} TEXT DEFAULT {default}")

    conn.commit()
    conn.close()


def inicializar_bd():
    """Crea las tablas de usuarios, empleados, proveedores, productos y movimientos si no existen."""
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute(
        """
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
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS empleados (
            id_empleado INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            telefono TEXT NOT NULL,
            cargo TEXT,
            rol TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS proveedores (
            id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            correo TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_barras TEXT UNIQUE,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio REAL DEFAULT 0.0,
            cantidad_stock INTEGER DEFAULT 0,
            fecha_vencimiento DATE,
            id_proveedor INTEGER,
            pasillo TEXT DEFAULT 'A',
            imagen TEXT DEFAULT '',
            FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor) ON DELETE SET NULL
        )
        """
    )

    migrar_esquema_productos()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS movimientos (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL,
            id_usuario INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            detalle TEXT,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        )
        """
    )

    conn.commit()
    conn.close()


def registrar_usuario(nombre, apellido, usuario, password, email, telefono, cargo="Empleado", rol="empleado"):
    """Inserta en 'usuarios' si el rol es 'gerente' o en 'empleados' si es 'empleado'."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT usuario FROM usuarios WHERE usuario = ? UNION SELECT usuario FROM empleados WHERE usuario = ?",
            (usuario, usuario),
        )
        if cursor.fetchone():
            conn.close()
            return False, "El nombre de usuario ya existe"

        if rol.lower() == "gerente":
            cursor.execute(
                """
                INSERT INTO usuarios (nombre, apellido, usuario, password, email, telefono, cargo, rol)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (nombre, apellido, usuario, password, email, telefono, cargo, rol),
            )
        else:
            cursor.execute(
                """
                INSERT INTO empleados (nombre, apellido, usuario, password, email, telefono, cargo, rol)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (nombre, apellido, usuario, password, email, telefono, cargo, rol),
            )

        conn.commit()
        conn.close()
        return True, "Registro exitoso"
    except Exception as e:
        return False, f"Error en la base de datos: {e}"


def verificar_credenciales(usuario, password):
    """Verifica las credenciales primero en usuarios y luego en empleados."""
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id_usuario AS id, nombre, apellido, usuario, password, email, telefono, cargo, rol
        FROM usuarios WHERE usuario = ? AND password = ?
        """,
        (usuario, password),
    )
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            """
            SELECT id_empleado AS id, nombre, apellido, usuario, password, email, telefono, cargo, rol
            FROM empleados WHERE usuario = ? AND password = ?
            """,
            (usuario, password),
        )
        user = cursor.fetchone()

    conn.close()
    return user


def obtener_metricas_dashboard():
    """Retorna las métricas actualizadas de la base de datos."""
    conn = obtener_conexion()
    cursor = conn.cursor()

    stock_col = "cantidad_stock" if "cantidad_stock" in [row[1] for row in conn.execute("PRAGMA table_info(productos)").fetchall()] else "stock"

    cursor.execute("SELECT COALESCE(COUNT(*), 0) FROM productos")
    total_productos = cursor.fetchone()[0]

    cursor.execute(f"SELECT COALESCE(COUNT(*), 0) FROM productos WHERE {stock_col} <= 5")
    stock_bajo = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COALESCE(COUNT(*), 0) FROM productos
        WHERE fecha_vencimiento BETWEEN DATE('now') AND DATE('now', '+7 days')
        """
    )
    por_vencer = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COALESCE(COUNT(*), 0) FROM productos
        WHERE fecha_vencimiento < DATE('now')
        """
    )
    vencidos = cursor.fetchone()[0]

    conn.close()

    return {
        "total_productos": total_productos,
        "stock_bajo": stock_bajo,
        "por_vencer": por_vencer,
        "vencidos": vencidos,
    }


def registrar_movimiento(id_producto, id_usuario, tipo, cantidad, detalle=""):
    """Registra entradas/salidas y actualiza stock."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        stock_col = "cantidad_stock" if "cantidad_stock" in [row[1] for row in conn.execute("PRAGMA table_info(productos)").fetchall()] else "stock"

        cursor.execute(
            """
            INSERT INTO movimientos (id_producto, id_usuario, tipo, cantidad, detalle)
            VALUES (?, ?, ?, ?, ?)
            """,
            (id_producto, id_usuario, tipo, cantidad, detalle),
        )

        if tipo.lower() == "entrada":
            cursor.execute(f"UPDATE productos SET {stock_col} = {stock_col} + ? WHERE id_producto = ?", (cantidad, id_producto))
        elif tipo.lower() == "salida":
            cursor.execute(f"UPDATE productos SET {stock_col} = MAX(0, {stock_col} - ?) WHERE id_producto = ?", (cantidad, id_producto))

        conn.commit()
        conn.close()
        return True, "Movimiento registrado y stock actualizado"
    except Exception as e:
        return False, f"Error al registrar movimiento: {e}"


def obtener_movimientos_recientes(limite=5):
    """Obtiene los últimos movimientos de la base de datos."""
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 
            m.fecha_hora,
            m.tipo,
            p.nombre AS producto,
            m.cantidad,
            m.detalle
        FROM movimientos m
        JOIN productos p ON m.id_producto = p.id_producto
        ORDER BY m.id_movimiento DESC
        LIMIT ?
        """,
        (limite,),
    )

    movimientos = cursor.fetchall()
    conn.close()
    return movimientos


if __name__ == "__main__":
    inicializar_bd()
    print("Base de datos inicializada correctamente.")