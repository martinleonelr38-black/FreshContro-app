# Gestor central de la base de datos.
# Sirve para crear, consultar, actualizar y migrar la información del inventario y usuarios.
import sqlite3
import os
from datetime import date, datetime

from kivy.utils import platform

if platform == "android":
    from android.storage import app_storage_path

    DB_DIRECTORY = app_storage_path()
else:
    DB_DIRECTORY = os.path.dirname(__file__)

os.makedirs(DB_DIRECTORY, exist_ok=True)
DB_PATH = os.path.join(DB_DIRECTORY, "freshcontrol.db")


class GestorBD:
    """Clase para ejecutar comandos directos en la base de datos."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def obtener_conexion(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
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

    def obtener_estado_acceso(self):
        rows = self.ejecutar_consulta(
            "SELECT intentos_fallidos, bloqueado FROM estado_acceso WHERE id_estado = 1"
        )
        return rows[0] if rows else (0, 0)

    def registrar_fallo_acceso(self, max_intentos=5):
        conn = self.obtener_conexion()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE estado_acceso
                SET intentos_fallidos = MIN(intentos_fallidos + 1, ?),
                    bloqueado = CASE WHEN intentos_fallidos + 1 >= ? THEN 1 ELSE bloqueado END
                WHERE id_estado = 1
                """,
                (max_intentos, max_intentos),
            )
            conn.commit()
            row = cursor.execute(
                "SELECT intentos_fallidos, bloqueado FROM estado_acceso WHERE id_estado = 1"
            ).fetchone()
            return tuple(row) if row else (0, 0)
        finally:
            conn.close()

    def reiniciar_estado_acceso(self):
        return self.ejecutar_comando(
            "UPDATE estado_acceso SET intentos_fallidos = 0, bloqueado = 0 WHERE id_estado = 1"
        )

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

    def registrar_producto_proveedor(self, id_proveedor, id_producto, cantidad_suministrada, precio_proveedor):
        """Registra los productos que trae un proveedor con su cantidad y precio."""
        try:
            conn = self.obtener_conexion()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO producto_proveedor (id_proveedor, id_producto, cantidad_suministrada, precio_proveedor)
                VALUES (?, ?, ?, ?)
                """,
                (id_proveedor, id_producto, cantidad_suministrada, precio_proveedor),
            )
            conn.commit()
            conn.close()
            return True, "Producto del proveedor registrado con éxito"
        except Exception as e:
            return False, f"Error al registrar producto de proveedor: {e}"

    def registrar_movimiento(self, id_producto, id_usuario, tipo, cantidad, detalle=""):
        """Registra entradas/salidas y actualiza stock."""
        try:
            cantidad = int(cantidad)
            if cantidad <= 0 or tipo.lower() not in ("entrada", "salida"):
                return False, "Tipo o cantidad de movimiento no válido"
            conn = self.obtener_conexion()
            cursor = conn.cursor()
            stock_col = "cantidad_stock"

            producto = cursor.execute(
                f"SELECT {stock_col}, fecha_vencimiento, precio FROM productos WHERE id_producto = ?",
                (id_producto,),
            ).fetchone()
            if not producto:
                conn.close()
                return False, "Producto no encontrado"
            if tipo.lower() == "salida" and (producto[0] or 0) < cantidad:
                conn.close()
                return False, "Stock insuficiente"

            columnas_movimiento = {
                fila[1] for fila in cursor.execute("PRAGMA table_info(movimientos)").fetchall()
            }
            columnas_extra = []
            valores_extra = []
            if "fecha_vencimiento_producto" in columnas_movimiento:
                columnas_extra.append("fecha_vencimiento_producto")
                valores_extra.append(producto[1])
            if "precio_unitario" in columnas_movimiento:
                columnas_extra.append("precio_unitario")
                valores_extra.append(producto[2] or 0)
            columnas_sql = ", " + ", ".join(columnas_extra) if columnas_extra else ""
            valores_sql = ", " + ", ".join("?" for _ in valores_extra) if valores_extra else ""
            cursor.execute(
                f"INSERT INTO movimientos (id_producto, id_usuario, tipo, cantidad, detalle{columnas_sql}) "
                f"VALUES (?, ?, ?, ?, ?{valores_sql})",
                (id_producto, id_usuario, tipo, cantidad, detalle, *valores_extra),
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

    def listar_productos_vencidos(self):
        conn = self.obtener_conexion()
        try:
            rows = conn.execute(
                """
                SELECT id_producto, nombre, cantidad_stock, fecha_vencimiento
                FROM productos
                WHERE fecha_vencimiento IS NOT NULL AND date(fecha_vencimiento) <= date('now')
                    AND COALESCE(cantidad_stock, 0) > 0
                ORDER BY date(fecha_vencimiento), nombre
                """
            ).fetchall()
            return [tuple(row) for row in rows]
        finally:
            conn.close()

    def eliminar_fecha_vencimiento(self, id_producto):
        """Quita únicamente la fecha de vencimiento, sin eliminar producto o stock."""
        return self.ejecutar_comando(
            "UPDATE productos SET fecha_vencimiento = NULL WHERE id_producto = ?",
            (id_producto,),
        )

    def buscar_productos(self, texto="", categoria=None):
        """Busca por fragmento de nombre, código o categoría."""
        filtros = []
        parametros = []
        if texto.strip():
            termino = f"%{texto.strip()}%"
            filtros.append("(nombre LIKE ? OR codigo_barras LIKE ? OR categoria LIKE ?)")
            parametros.extend((termino, termino, termino))
        if categoria:
            filtros.append("categoria = ?")
            parametros.append(categoria)
        where = " WHERE " + " AND ".join(filtros) if filtros else ""
        return self.ejecutar_consulta(
            "SELECT id_producto, codigo_barras, nombre, categoria, cantidad_stock, fecha_vencimiento "
            f"FROM productos{where} ORDER BY nombre COLLATE NOCASE",
            tuple(parametros),
        )

    def retirar_stock_vencido(self, id_producto=None, id_usuario=1):
        conn = self.obtener_conexion()
        try:
            cursor = conn.cursor()
            sql = "SELECT id_producto, cantidad_stock, fecha_vencimiento, COALESCE(precio, 0) FROM productos WHERE fecha_vencimiento IS NOT NULL AND date(fecha_vencimiento) <= date('now') AND COALESCE(cantidad_stock, 0) > 0"
            parametros = []
            if id_producto is not None:
                sql += " AND id_producto = ?"
                parametros.append(id_producto)
            productos_vencidos = cursor.execute(sql, parametros).fetchall()
            ids_vencidos = [row[0] for row in productos_vencidos]
            if not ids_vencidos:
                return 0

            columnas_movimiento = {
                row[1] for row in cursor.execute("PRAGMA table_info(movimientos)").fetchall()
            }
            for producto_id, cantidad, fecha_vencimiento, precio in productos_vencidos:
                columnas_extra = []
                valores_extra = []
                if "fecha_vencimiento_producto" in columnas_movimiento:
                    columnas_extra.append("fecha_vencimiento_producto")
                    valores_extra.append(fecha_vencimiento)
                if "precio_unitario" in columnas_movimiento:
                    columnas_extra.append("precio_unitario")
                    valores_extra.append(precio)
                nombres_extra = ", " + ", ".join(columnas_extra) if columnas_extra else ""
                valores_sql = ", " + ", ".join("?" for _ in valores_extra) if valores_extra else ""
                cursor.execute(
                    f"INSERT INTO movimientos (id_producto, id_usuario, tipo, cantidad, detalle{nombres_extra}) "
                    f"VALUES (?, ?, ?, ?, ?{valores_sql})",
                    (producto_id, id_usuario, "vencido", cantidad, "Retiro de stock por vencimiento", *valores_extra),
                )

            placeholders = ", ".join("?" for _ in ids_vencidos)
            cursor.execute(
                f"UPDATE productos SET cantidad_stock = 0, fecha_vencimiento = NULL WHERE id_producto IN ({placeholders})",
                ids_vencidos,
            )
            cantidad_retirada = cursor.rowcount

            conn.commit()
            return cantidad_retirada
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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

        cursor.execute(
            """SELECT p.nombre, p.categoria, p.cantidad_stock, m.cantidad, m.fecha_hora
               FROM movimientos m JOIN productos p ON p.id_producto = m.id_producto
               WHERE lower(m.tipo) = 'salida'
               ORDER BY m.id_movimiento DESC LIMIT 10"""
        )
        for nombre, categoria, stock, cantidad, fecha in cursor.fetchall():
            notificaciones.append((
                "Stock reducido",
                f"{nombre}: salida de {cantidad} unidad(es); quedan {stock} ({fecha})",
                categoria,
                stock,
                fecha,
            ))

        conn.close()
        return notificaciones

    def sincronizar_alertas(self, dias=30):
        """Guarda en alertas los avisos actuales sin duplicarlos en el mismo día."""
        conn = self.obtener_conexion()
        try:
            cursor = conn.cursor()
            fecha_generada = date.today().isoformat()
            avisos = []

            productos_por_vencer = cursor.execute(
                """
                SELECT id_producto, nombre, fecha_vencimiento
                FROM productos
                WHERE fecha_vencimiento IS NOT NULL
                    AND date(fecha_vencimiento) <= date('now', '+' || ? || ' days')
                """,
                (dias,),
            ).fetchall()
            for id_producto, nombre, vencimiento in productos_por_vencer:
                tipo = "Vencimiento"
                avisos.append((id_producto, tipo, f"{nombre} vence el {vencimiento}"))

            productos_stock_bajo = cursor.execute(
                """
                SELECT id_producto, nombre, cantidad_stock
                FROM productos
                WHERE COALESCE(cantidad_stock, 0) <= 5
                """
            ).fetchall()
            for id_producto, nombre, stock in productos_stock_bajo:
                tipo = "Stock bajo"
                avisos.append((id_producto, tipo, f"{nombre} tiene {stock} unidades disponibles"))

            salidas_recientes = cursor.execute(
                """
                SELECT p.id_producto, p.nombre, m.cantidad
                FROM movimientos m
                JOIN productos p ON p.id_producto = m.id_producto
                WHERE lower(m.tipo) = 'salida'
                ORDER BY m.id_movimiento DESC
                LIMIT 10
                """
            ).fetchall()
            for id_producto, nombre, cantidad in salidas_recientes:
                tipo = "Stock reducido"
                avisos.append((id_producto, tipo, f"{nombre}: salida de {cantidad} unidad(es)"))

            for id_producto, tipo, mensaje in avisos:
                existe = cursor.execute(
                    """
                    SELECT 1 FROM alertas
                    WHERE id_producto = ? AND tipo_alerta = ? AND mensaje = ?
                        AND fecha_generada = ?
                    LIMIT 1
                    """,
                    (id_producto, tipo, mensaje, fecha_generada),
                ).fetchone()
                if not existe:
                    cursor.execute(
                        """
                        INSERT INTO alertas
                            (id_producto, tipo_alerta, mensaje, fecha_generada, leido)
                        VALUES (?, ?, ?, ?, 0)
                        """,
                        (id_producto, tipo, mensaje, fecha_generada),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def listar_alertas(self, limite=50):
        return self.ejecutar_consulta(
            """
            SELECT a.id_alerta, a.id_producto, p.nombre, a.tipo_alerta,
                   a.mensaje, a.fecha_generada, a.leido
            FROM alertas a
            JOIN productos p ON p.id_producto = a.id_producto
            ORDER BY a.leido ASC, date(a.fecha_generada) DESC, a.id_alerta DESC
            LIMIT ?
            """,
            (limite,),
        )

    def marcar_alerta_leida(self, id_alerta):
        return self.ejecutar_comando(
            "UPDATE alertas SET leido = 1 WHERE id_alerta = ?",
            (id_alerta,),
        )

    def listar_movimientos(self, limite=20):
        conn = self.obtener_conexion()
        cursor = conn.cursor()
        columnas_producto = {
            row[1] for row in cursor.execute("PRAGMA table_info(productos)").fetchall()
        }
        expresion_sector = (
            "COALESCE(NULLIF(TRIM(p.pasillo), ''), 'Sin sector')"
            if "pasillo" in columnas_producto
            else "'Sin sector'"
        )
        cursor.execute(
            f"""
            SELECT m.id_movimiento, p.nombre, p.categoria, m.tipo, m.cantidad,
                   m.fecha_hora, m.detalle, p.codigo_barras, {expresion_sector} AS sector
            FROM movimientos m
            JOIN productos p ON p.id_producto = m.id_producto
            ORDER BY m.id_movimiento DESC
            """ + (" LIMIT ?" if limite is not None else ""),
            (limite,) if limite is not None else (),
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
    conn.execute("PRAGMA foreign_keys = ON")
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
    if "precio" not in columnas:
        conn.execute("ALTER TABLE productos ADD COLUMN precio REAL DEFAULT 0.0")
    for nombre_columna, definicion in (
        ("pasillo", "TEXT DEFAULT 'A'"),
        ("imagen", "TEXT DEFAULT ''"),
        ("unidad_medida", "TEXT DEFAULT 'unidad(es)'"),
        ("fecha_ingreso", "DATE"),
        ("congelado", "INTEGER DEFAULT 0"),
        ("fecha_congelacion", "DATE"),
    ):
        if nombre_columna not in columnas:
            conn.execute(f"ALTER TABLE productos ADD COLUMN {nombre_columna} {definicion}")

    tabla_movimientos = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'movimientos'"
    ).fetchone()
    if tabla_movimientos:
        columnas_movimientos = {
            row[1] for row in conn.execute("PRAGMA table_info(movimientos)").fetchall()
        }
        for nombre_columna, tipo in (
            ("fecha_vencimiento_producto", "DATE"),
            ("precio_unitario", "REAL DEFAULT 0"),
        ):
            if nombre_columna not in columnas_movimientos:
                conn.execute(f"ALTER TABLE movimientos ADD COLUMN {nombre_columna} {tipo}")

    # Crear tabla de relación producto_proveedor si no existe
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS producto_proveedor (
            id_relacion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_proveedor INTEGER NOT NULL,
            id_producto INTEGER NOT NULL,
            cantidad_suministrada INTEGER DEFAULT 0,
            precio_proveedor REAL DEFAULT 0.0,
            fecha_registro DATE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor) ON DELETE CASCADE,
            FOREIGN KEY (id_producto) REFERENCES productos (id_producto) ON DELETE CASCADE
        )
        """
    )

    tabla_legacy = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'productos_legacy'"
    ).fetchone()
    if tabla_legacy:
        columnas_legacy = {
            row[1] for row in conn.execute("PRAGMA table_info(productos_legacy)").fetchall()
        }
        columnas_producto = {
            row[1] for row in conn.execute("PRAGMA table_info(productos)").fetchall()
        }
        columnas_mapeadas = [
            (columna, "stock" if columna == "cantidad_stock" and "stock" in columnas_legacy else columna)
            for columna in (
                "id_producto",
                "codigo_barras",
                "nombre",
                "categoria",
                "precio",
                "cantidad_stock",
                "fecha_vencimiento",
                "id_proveedor",
            )
            if columna in columnas_producto
            and (columna in columnas_legacy or (columna == "cantidad_stock" and "stock" in columnas_legacy))
        ]
        if {"id_producto", "nombre"}.issubset(
            {destino for destino, _ in columnas_mapeadas}
        ):
            destinos = ", ".join(f'"{destino}"' for destino, _ in columnas_mapeadas)
            origenes = ", ".join(f'"{origen}"' for _, origen in columnas_mapeadas)
            conn.execute(
                f"INSERT OR IGNORE INTO productos ({destinos}) "
                f"SELECT {origenes} FROM productos_legacy"
            )

    tabla_movimientos = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'movimientos'"
    ).fetchone()
    if tabla_movimientos:
        claves_foraneas = conn.execute("PRAGMA foreign_key_list(movimientos)").fetchall()
        if any(fila[2] == "productos_legacy" for fila in claves_foraneas):
            movimientos_sin_producto = conn.execute(
                """
                SELECT m.id_movimiento, m.id_producto
                FROM movimientos m
                LEFT JOIN productos p ON p.id_producto = m.id_producto
                WHERE p.id_producto IS NULL
                LIMIT 1
                """
            ).fetchone()
            if movimientos_sin_producto:
                raise sqlite3.IntegrityError(
                    "No se puede eliminar productos_legacy: "
                    f"el movimiento {movimientos_sin_producto[0]} referencia al producto "
                    f"{movimientos_sin_producto[1]} que no existe en productos"
                )

            conn.execute(
                """
                CREATE TABLE movimientos_nuevo (
                    id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_producto INTEGER NOT NULL,
                    id_usuario INTEGER NOT NULL,
                    tipo TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
                    detalle TEXT,
                    fecha_vencimiento_producto DATE,
                    precio_unitario REAL DEFAULT 0,
                    FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
                )
                """
            )
            columnas_movimientos = {
                fila[1] for fila in conn.execute("PRAGMA table_info(movimientos)").fetchall()
            }
            columnas_copiadas = [
                columna
                for columna in (
                    "id_movimiento",
                    "id_producto",
                    "id_usuario",
                    "tipo",
                    "cantidad",
                    "fecha_hora",
                    "detalle",
                    "fecha_vencimiento_producto",
                    "precio_unitario",
                )
                if columna in columnas_movimientos
            ]
            lista_columnas = ", ".join(f'"{columna}"' for columna in columnas_copiadas)
            conn.execute(
                f"INSERT INTO movimientos_nuevo ({lista_columnas}) "
                f"SELECT {lista_columnas} FROM movimientos"
            )
            conn.execute("DROP TABLE movimientos")
            conn.execute("ALTER TABLE movimientos_nuevo RENAME TO movimientos")

    conn.execute("DROP TABLE IF EXISTS productos_legacy")
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
        CREATE TABLE IF NOT EXISTS estado_acceso (
            id_estado INTEGER PRIMARY KEY CHECK (id_estado = 1),
            intentos_fallidos INTEGER NOT NULL DEFAULT 0,
            bloqueado INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cursor.execute("INSERT OR IGNORE INTO estado_acceso (id_estado) VALUES (1)")

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
            unidad_medida TEXT DEFAULT 'unidad(es)',
            fecha_ingreso DATE,
            congelado INTEGER DEFAULT 0,
            fecha_congelacion DATE,
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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alertas (
            id_alerta INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL,
            tipo_alerta TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            fecha_generada DATE NOT NULL,
            leido INTEGER DEFAULT 0,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE
        )
        """
    )

    migrar_esquema_productos()

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