from datetime import date, timedelta
from base_de_datos.gestor_bd import GestorBD

class ControladorReportes:
    def __init__(self):
        self.bd = GestorBD()

    def resumen_inventario(self):
        """ Retorna total de productos registrados y la suma de stock general """
        sql = "SELECT COUNT(*), SUM(cantidad_stock) FROM productos"
        res = self.bd.ejecutar_consulta(sql)
        if res and res[0][0] is not None:
            return {
                "total_productos": res[0][0],
                "stock_total": res[0][1] or 0
            }
        return {"total_productos": 0, "stock_total": 0}

    def obtener_productos_vencidos(self):
        """ Retorna el listado de productos cuya fecha de vencimiento es menor o igual a hoy """
        hoy = date.today().isoformat()
        sql = """
            SELECT id_producto, codigo_barras, nombre, cantidad_stock, fecha_vencimiento
            FROM productos
            WHERE fecha_vencimiento <= ?
            ORDER BY fecha_vencimiento ASC
        """
        return self.bd.ejecutar_consulta(sql, (hoy,))

    def obtener_productos_por_vencer(self, dias=7):
        """ Retorna productos que vencerán en los próximos 'dias' """
        hoy = date.today()
        limite = (hoy + timedelta(dias=dias)).isoformat()
        
        sql = """
            SELECT id_producto, codigo_barras, nombre, cantidad_stock, fecha_vencimiento
            FROM productos
            WHERE fecha_vencimiento > ? AND fecha_vencimiento <= ?
            ORDER BY fecha_vencimiento ASC
        """
        return self.bd.ejecutar_consulta(sql, (hoy.isoformat(), limite))

    def historial_movimientos(self, limite=20):
        """ Retorna los últimos 'limite' movimientos realizados con nombre de producto y empleado """
        sql = """
            SELECT m.id_movimiento, p.nombre, m.tipo_movimiento, m.cantidad, m.fecha_movimiento, e.nombre
            FROM movimientos m
            JOIN productos p ON m.id_producto = p.id_producto
            JOIN empleados e ON m.id_empleado = e.id_empleado
            ORDER BY m.id_movimiento DESC
            LIMIT ?
        """
        return self.bd.ejecutar_consulta(sql, (limite,))