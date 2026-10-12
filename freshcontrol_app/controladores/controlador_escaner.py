# Controlador del escáner y búsqueda de productos.
# Sirve para consultar códigos de barras, cargar datos públicos y registrar movimientos de stock.
from datetime import date
import requests
from base_de_datos.gestor_bd import GestorBD


class ControladorEscaner:
    def __init__(self):
        self.bd = GestorBD()

    def _stock_column(self):
        return self.bd.get_stock_column_name()

    def procesar_codigo(self, codigo_barras):
        """Busca el producto asociado a un código de barras."""
        stock_col = self._stock_column()
        sql = f"""
            SELECT id_producto, codigo_barras, nombre, categoria, {stock_col} AS cantidad_stock, unidad_medida, fecha_vencimiento, pasillo
            FROM productos
            WHERE codigo_barras = ?
        """
        res = self.bd.ejecutar_consulta(sql, (codigo_barras,))
        return res[0] if res else None

    def buscar_datos_publicos(self, codigo_barras):
        """Consulta nombre y categoría pública para completar un alta escaneada."""
        try:
            respuesta = requests.get(
                f"https://world.openfoodfacts.org/api/v2/product/{codigo_barras}.json",
                params={"fields": "product_name,product_name_es,categories_tags"},
                timeout=5,
            )
            respuesta.raise_for_status()
            producto = respuesta.json().get("product", {})
            nombre = (producto.get("product_name_es") or producto.get("product_name") or "").strip()
            if not nombre:
                return None
            categoria = "Otros"
            for etiqueta in producto.get("categories_tags", []):
                etiqueta = etiqueta.rsplit(":", 1)[-1].replace("-", " ").strip()
                if etiqueta:
                    categoria = etiqueta[:1].upper() + etiqueta[1:]
                    break
            return {"codigo": codigo_barras, "nombre": nombre, "categoria": categoria}
        except (requests.RequestException, ValueError, TypeError):
            return None

    def registrar_movimiento(self, id_producto, tipo_movimiento, cantidad, id_empleado):
        """Registra una entrada o salida de stock y actualiza la cantidad del producto."""
        fecha_actual = date.today().isoformat()
        stock_col = self._stock_column()

        sql_stock = f"SELECT {stock_col} FROM productos WHERE id_producto = ?"
        res = self.bd.ejecutar_consulta(sql_stock, (id_producto,))
        if not res:
            return False, "Producto no encontrado."

        stock_actual = res[0][0] or 0

        if tipo_movimiento.lower() == "salida":
            if stock_actual < cantidad:
                return False, "Stock insuficiente para realizar la salida."
            nuevo_stock = stock_actual - cantidad
        elif tipo_movimiento.lower() == "entrada":
            nuevo_stock = stock_actual + cantidad
        else:
            return False, "Tipo de movimiento no válido."

        sql_mov = """
            INSERT INTO movimientos (id_producto, id_usuario, tipo, cantidad, fecha_hora, detalle)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        exito_mov = self.bd.ejecutar_comando(
            sql_mov,
            (id_producto, id_empleado, tipo_movimiento.lower(), cantidad, fecha_actual, f"Movimiento de {tipo_movimiento.lower()}"),
        )

        if not exito_mov:
            return False, "Error al registrar el movimiento."

        sql_update = f"UPDATE productos SET {stock_col} = ? WHERE id_producto = ?"
        exito_update = self.bd.ejecutar_comando(sql_update, (nuevo_stock, id_producto))

        if exito_update:
            return True, f"Movimiento registrado. Nuevo stock: {nuevo_stock}"
        return False, "Error al actualizar el stock del producto."