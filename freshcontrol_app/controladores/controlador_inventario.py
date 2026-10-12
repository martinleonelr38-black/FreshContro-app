# Controlador del inventario.
# Sirve para manejar altas, búsquedas, vencimientos y reglas operativas del stock.
import calendar
import unicodedata
from datetime import date, datetime, timedelta
from base_de_datos.gestor_bd import GestorBD

class ControladorInventario:
    def __init__(self):
        self.bd = GestorBD()

    @staticmethod
    def calcular_vencimiento_congelado(fecha_vencimiento, categoria):
        """Extiende la fecha base según alimento y evita desbordes de fin de mes."""
        meses_por_categoria = {
            "carnes": 6,
            "pescados": 3,
            "pescado": 3,
            "lacteos": 2,
            "lácteos": 2,
            "verduras": 8,
            "frutas": 8,
            "panificados": 3,
        }
        categoria_normalizada = "".join(
            caracter for caracter in unicodedata.normalize("NFD", str(categoria or "").casefold())
            if unicodedata.category(caracter) != "Mn"
        )
        meses = meses_por_categoria.get(categoria_normalizada)
        if meses is None:
            if any(palabra in categoria_normalizada for palabra in ("carne", "meat")):
                meses = 6
            elif any(palabra in categoria_normalizada for palabra in ("pescad", "fish", "seafood")):
                meses = 3
            elif any(palabra in categoria_normalizada for palabra in ("lact", "dairy")):
                meses = 2
            elif any(palabra in categoria_normalizada for palabra in ("verd", "vegetable", "frut", "fruit")):
                meses = 8
            else:
                meses = 3
        fecha = datetime.strptime(str(fecha_vencimiento)[:10], "%Y-%m-%d").date()
        mes_total = fecha.month - 1 + meses
        anio = fecha.year + mes_total // 12
        mes = mes_total % 12 + 1
        dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
        return date(anio, mes, dia).isoformat()

    def quitar_fecha_vencimiento(self, id_producto):
        return self.bd.eliminar_fecha_vencimiento(id_producto)

    def registrar_producto(self, codigo_barras, nombre, categoria, cantidad, unidad, fecha_ven, id_proveedor=None, pasillo="A", imagen=""):
        """Registra un nuevo producto en la base de datos."""
        fecha_ingreso = date.today().isoformat()
        sql = """
            INSERT INTO productos (codigo_barras, nombre, categoria, cantidad_stock, unidad_medida,
                                   fecha_ingreso, fecha_vencimiento, id_proveedor, pasillo, imagen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.bd.ejecutar_comando(
            sql,
            (codigo_barras, nombre, categoria, cantidad, unidad, fecha_ingreso, fecha_ven, id_proveedor, pasillo, imagen),
        )

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