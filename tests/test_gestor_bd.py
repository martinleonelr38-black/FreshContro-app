import os
import sqlite3
import unittest

from freshcontrol_app.base_de_datos.gestor_bd import GestorBD


class TestGestorBD(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(os.path.dirname(__file__), "test_freshcontrol.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        self.gestor = GestorBD(db_path=self.db_path)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE usuarios (
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
        cur.execute("""
            CREATE TABLE empleados (
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
        """)
        cur.execute("""
            CREATE TABLE proveedores (
                id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT,
                correo TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE productos (
                id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_barras TEXT UNIQUE,
                nombre TEXT NOT NULL,
                categoria TEXT,
                cantidad_stock INTEGER DEFAULT 0,
                fecha_vencimiento DATE,
                id_proveedor INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE movimientos (
                id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
                id_producto INTEGER NOT NULL,
                id_usuario INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
                detalle TEXT
            )
        """)
        cur.execute("INSERT INTO proveedores (nombre, telefono, correo) VALUES (?, ?, ?)", ("Proveedor 1", "123", "a@b.com"))
        cur.execute("INSERT INTO productos (codigo_barras, nombre, categoria, cantidad_stock, fecha_vencimiento, id_proveedor) VALUES (?, ?, ?, ?, ?, ?)", ("111", "Leche", "Lácteos", 20, "2026-10-10", 1))
        cur.execute("INSERT INTO movimientos (id_producto, id_usuario, tipo, cantidad, detalle) VALUES (?, ?, ?, ?, ?)", (1, 1, "entrada", 5, "Ingreso inicial"))
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_listar_productos_por_categoria(self):
        productos = self.gestor.listar_productos_por_categoria()
        self.assertTrue(len(productos) >= 1)
        self.assertEqual(productos[0][0], "Lácteos")

    def test_obtener_notificaciones_gerente(self):
        notifs = self.gestor.obtener_notificaciones_gerente()
        self.assertIsInstance(notifs, list)

    def test_registrar_proveedor(self):
        ok = self.gestor.registrar_proveedor("Proveedor 2", "456", "c@d.com")
        self.assertTrue(ok)
        proveedores = self.gestor.listar_proveedores()
        self.assertTrue(any(p[1] == "Proveedor 2" for p in proveedores))


if __name__ == "__main__":
    unittest.main()
