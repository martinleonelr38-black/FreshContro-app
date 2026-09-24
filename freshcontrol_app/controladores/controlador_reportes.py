import os
from datetime import date, timedelta

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from base_de_datos.gestor_bd import GestorBD


class ControladorReportes:
    def __init__(self):
        self.bd = GestorBD()

    def resumen_inventario(self):
        """Retorna total de productos registrados y la suma de stock general."""
        sql = "SELECT COUNT(*), SUM(cantidad_stock) FROM productos"
        res = self.bd.ejecutar_consulta(sql)
        if res and res[0][0] is not None:
            return {"total_productos": res[0][0], "stock_total": res[0][1] or 0}
        return {"total_productos": 0, "stock_total": 0}

    def obtener_productos_vencidos(self):
        """Retorna productos cuya fecha de vencimiento es menor o igual a hoy."""
        hoy = date.today().isoformat()
        sql = """
            SELECT id_producto, codigo_barras, nombre, cantidad_stock, fecha_vencimiento
            FROM productos
            WHERE fecha_vencimiento <= ?
            ORDER BY fecha_vencimiento ASC
        """
        return self.bd.ejecutar_consulta(sql, (hoy,))

    def obtener_productos_por_vencer(self, dias=7):
        """Retorna productos que vencerán en los próximos 'dias'."""
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
        """Retorna los últimos movimientos con nombre del producto y empleado."""
        sql = """
            SELECT m.id_movimiento, p.nombre, m.tipo, m.cantidad, m.fecha_hora, m.detalle
            FROM movimientos m
            JOIN productos p ON m.id_producto = p.id_producto
            ORDER BY m.id_movimiento DESC
            LIMIT ?
        """
        return self.bd.ejecutar_consulta(sql, (limite,))

    def obtener_proveedores(self):
        """Retorna proveedores registrados."""
        sql = "SELECT id_proveedor, nombre, telefono, correo FROM proveedores ORDER BY nombre ASC"
        return self.bd.ejecutar_consulta(sql)

    def _ruta_reporte(self, nombre_archivo):
        carpeta = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reportes")
        os.makedirs(carpeta, exist_ok=True)
        return os.path.join(carpeta, nombre_archivo)

    def exportar_pdf(self, tipo="movimientos", nombre_archivo="reporte_freshcontrol.pdf"):
        """Genera un PDF con movimientos, vencimientos o proveedores."""
        file_path = self._ruta_reporte(nombre_archivo)

        if tipo == "vencimiento":
            titulo = "Reporte de productos próximos a vencer"
            cabecera = ["ID", "Código", "Nombre", "Stock", "Vencimiento"]
            filas = self.obtener_productos_por_vencer(30)
            datos = [cabecera] + [[str(item[0]), str(item[1]), str(item[2]), str(item[3]), str(item[4])] for item in filas]
        elif tipo == "proveedores":
            titulo = "Reporte de proveedores"
            cabecera = ["ID", "Nombre", "Teléfono", "Correo"]
            filas = self.obtener_proveedores()
            datos = [cabecera] + [[str(item[0]), str(item[1]), str(item[2]), str(item[3])] for item in filas]
        else:
            titulo = "Reporte de movimientos"
            cabecera = ["ID", "Producto", "Tipo", "Cantidad", "Fecha", "Detalle"]
            filas = self.historial_movimientos(50)
            datos = [cabecera] + [[str(item[0]), str(item[1]), str(item[2]), str(item[3]), str(item[4]), str(item[5])] for item in filas]

        styles = getSampleStyleSheet()
        story = [Paragraph(titulo, styles['Title']), Spacer(1, 12)]
        tabla = Table(datos)
        tabla.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0e7a4b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMMARGIN', (0, 0), (-1, -1), 8),
            ])
        )
        story.append(tabla)

        doc = SimpleDocTemplate(file_path, pagesize=letter)
        doc.build(story)
        return file_path

    def exportar_excel(self, tipo="movimientos", nombre_archivo="reporte_freshcontrol.xlsx"):
        """Genera un Excel con movimientos, vencimientos o proveedores."""
        file_path = self._ruta_reporte(nombre_archivo)
        wb = Workbook()
        ws = wb.active
        ws.title = tipo.title()

        if tipo == "vencimiento":
            ws.append(["ID", "Código", "Nombre", "Stock", "Vencimiento"])
            for item in self.obtener_productos_por_vencer(30):
                ws.append([item[0], item[1], item[2], item[3], item[4]])
        elif tipo == "proveedores":
            ws.append(["ID", "Nombre", "Teléfono", "Correo"])
            for item in self.obtener_proveedores():
                ws.append([item[0], item[1], item[2], item[3]])
        else:
            ws.append(["ID", "Producto", "Tipo", "Cantidad", "Fecha", "Detalle"])
            for item in self.historial_movimientos(50):
                ws.append([item[0], item[1], item[2], item[3], item[4], item[5]])

        header_fill = PatternFill("solid", fgColor="0E7A4B")
        header_font = Font(color="FFFFFF", bold=True)
        thin = Side(style="thin", color="D0D0D0")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.border = border

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
            for cell in row:
                cell.border = border

        ws.freeze_panes = 'A2'
        wb.save(file_path)
        return file_path