from datetime import date
from base_de_datos.gestor_bd import GestorBD

class ControladorEscaner:
    def __init__(self):
        self.bd = GestorBD()

    def procesar_codigo(self, codigo_barras):
        """
        Busca el producto asociado a un código de barras.
        Retorna la tupla con la información del producto o None si no existe.
        """
        sql = """
            SELECT id_producto, codigo_barras, nombre, categoria, cantidad_stock, unidad_medida, fecha_vencimiento
            FROM productos
            WHERE codigo_barras = ?
        """
        res = self.bd.ejecutar_consulta(sql, (codigo_barras,))
        return res[0] if res else None

    def registrar_movimiento(self, id_producto, tipo_movimiento, cantidad, id_empleado):
        """
        Registra una entrada o salida de stock y actualiza la cantidad en la tabla productos.
        """
        fecha_actual = date.today().isoformat()
        
        # 1. Obtener stock actual
        sql_stock = "SELECT cantidad_stock FROM productos WHERE id_producto = ?"
        res = self.bd.ejecutar_consulta(sql_stock, (id_producto,))
        if not res:
            return False, "Producto no encontrado."

        stock_actual = res[0][0]

        if tipo_movimiento.lower() == 'salida':
            if stock_actual < cantidad:
                return False, "Stock insuficiente para realizar la salida."
            nuevo_stock = stock_actual - cantidad
        elif tipo_movimiento.lower() == 'entrada':
            nuevo_stock = stock_actual + cantidad
        else:
            return False, "Tipo de movimiento no válido."

        # 2. Registrar el movimiento en la tabla 'movimientos'
        sql_mov = """
            INSERT INTO movimientos (id_producto, tipo_movimiento, cantidad, fecha_movimiento, id_empleado)
            VALUES (?, ?, ?, ?, ?)
        """
        exito_mov = self.bd.ejecutar_comando(sql_mov, (id_producto, tipo_movimiento.lower(), cantidad, fecha_actual, id_empleado))

        if not exito_mov:
            return False, "Error al registrar el movimiento."

        # 3. Actualizar el stock del producto
        sql_update = "UPDATE productos SET cantidad_stock = ? WHERE id_producto = ?"
        exito_update = self.bd.ejecutar_comando(sql_update, (nuevo_stock, id_producto))

        if exito_update:
            return True, f"Movimiento registrado. Nuevo stock: {nuevo_stock}"
        else:
            return False, "Error al actualizar el stock del producto."