from datetime import date, timedelta
from base_de_datos.gestor_bd import GestorBD

class ControladorInventario:
    def __init__(self):
        self.bd = GestorBD()

    def registrar_producto(self, codigo_barras, nombre, categoria, cantidad, unidad, fecha_ven, id_proveedor=None):
        """ Registra un nuevo producto en la base de datos """
        fecha_ingreso = date.today().isoformat()
        sql = """
            INSERT INTO productos (codigo_barras, nombre, categoria, cantidad_stock, unidad_medida, fecha_ingreso, fecha_vencimiento, id_proveedor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.bd.ejecutar_comando(sql, (codigo_barras, nombre, categoria, cantidad, unidad, fecha_ingreso, fecha_ven, id_proveedor))

    def obtener_productos(self):
        """ Devuelve el listado completo de productos """
        sql = "SELECT id_producto, codigo_barras, nombre, categoria, cantidad_stock, fecha_vencimiento FROM productos"
        return self.bd.ejecutar_consulta(sql)

    def buscar_por_codigo(self, codigo_barras):
        """ Busca un producto por su código de barras """
        sql = "SELECT * FROM productos WHERE codigo_barras = ?"
        res = self.bd.ejecutar_consulta(sql, (codigo_barras,))
        return res[0] if res else None

    def consultar_alertas_vencimiento(self, dias_limite=7):
        """ Retorna productos vencidos o próximos a vencer en 'dias_limite' """
        hoy = date.today()
        limite = hoy + timedelta(dias=dias_limite)
        
        sql = """
            SELECT id_producto, nombre, cantidad_stock, fecha_vencimiento 
            FROM productos 
            WHERE fecha_vencimiento <= ?
            ORDER BY fecha_vencimiento ASC
        """
        return self.bd.ejecutar_consulta(sql, (limite.isoformat(),))