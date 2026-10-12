# Módulo de reportes.
# Sirve para generar resúmenes, PDF y Excel de movimientos, vencimientos e inventario.
import os
from datetime import date, timedelta

from kivy.utils import platform
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

rl_config.pageCompression = 0
rl_config.useA85 = 0

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
        columnas_producto = {
            fila[1] for fila in self.bd.ejecutar_consulta("PRAGMA table_info(productos)")
        }
        expresion_sector = (
            "COALESCE(NULLIF(TRIM(p.pasillo), ''), 'Sin sector')"
            if "pasillo" in columnas_producto
            else "'Sin sector'"
        )
        sql = """
            SELECT m.id_movimiento, p.nombre, m.tipo, m.cantidad, m.fecha_hora,
                   m.detalle, p.codigo_barras, p.categoria, {sector} AS sector
            FROM movimientos m
            JOIN productos p ON m.id_producto = p.id_producto
            ORDER BY sector ASC, m.id_movimiento DESC
            LIMIT ?
        """.format(sector=expresion_sector)
        return self.bd.ejecutar_consulta(sql, (limite,))

    def obtener_proveedores(self):
        """Retorna proveedores registrados."""
        sql = "SELECT id_proveedor, nombre, telefono, correo FROM proveedores ORDER BY nombre ASC"
        return self.bd.ejecutar_consulta(sql)

    def obtener_productos_vencidos_completo(self):
        """Retorna productos vencidos con proveedor y precio actual."""
        sql = """
            SELECT p.nombre, p.cantidad_stock, p.fecha_vencimiento,
                   COALESCE(pr.nombre, 'Sin proveedor') AS proveedor, p.precio
            FROM productos p
            LEFT JOIN proveedores pr ON pr.id_proveedor = p.id_proveedor
            WHERE p.fecha_vencimiento IS NOT NULL AND p.fecha_vencimiento <= date('now')
            ORDER BY p.fecha_vencimiento ASC, p.nombre ASC
        """
        return self.bd.ejecutar_consulta(sql)

    def obtener_vencidos_del_mes(self, anio=None, mes=None):
        """Lista vencimientos del mes con cantidad retirada y valor estimado."""
        hoy = date.today()
        anio = int(anio or hoy.year)
        mes = int(mes or hoy.month)
        inicio = date(anio, mes, 1).isoformat()
        fin = date(anio + (mes == 12), 1 if mes == 12 else mes + 1, 1).isoformat()
        columnas_producto = {
            fila[1] for fila in self.bd.ejecutar_consulta("PRAGMA table_info(productos)")
        }
        columnas_movimiento = {
            fila[1] for fila in self.bd.ejecutar_consulta("PRAGMA table_info(movimientos)")
        }
        resultados = {}

        if {"fecha_vencimiento_producto", "precio_unitario"}.issubset(columnas_movimiento):
            movimientos = self.bd.ejecutar_consulta(
                """SELECT p.id_producto, p.nombre, SUM(m.cantidad),
                          SUM(m.cantidad * COALESCE(m.precio_unitario, 0)),
                          m.fecha_vencimiento_producto
                   FROM movimientos m JOIN productos p ON p.id_producto = m.id_producto
                   WHERE lower(m.tipo) = 'vencido'
                     AND m.fecha_vencimiento_producto >= ? AND m.fecha_vencimiento_producto < ?
                   GROUP BY p.id_producto, p.nombre, m.fecha_vencimiento_producto""",
                (inicio, fin),
            )
            resultados.update({(fila[0], fila[4]): fila for fila in movimientos})

        columnas_actuales = ["id_producto", "nombre", "cantidad_stock", "fecha_vencimiento"]
        precio = "precio" if "precio" in columnas_producto else "0"
        if set(columnas_actuales).issubset(columnas_producto):
            activos = self.bd.ejecutar_consulta(
                f"""SELECT id_producto, nombre, cantidad_stock,
                           COALESCE({precio}, 0) * COALESCE(cantidad_stock, 0), fecha_vencimiento
                    FROM productos WHERE fecha_vencimiento >= ? AND fecha_vencimiento < ?
                      AND COALESCE(cantidad_stock, 0) > 0""",
                (inicio, fin),
            )
            for fila in activos:
                resultados.setdefault((fila[0], fila[4]), fila)
        return sorted(resultados.values(), key=lambda fila: (fila[4], fila[1]))

    def obtener_inventario_almacen(self):
        """Retorna el inventario actual del almacén con su proveedor."""
        sql = """
            SELECT p.nombre, p.categoria, p.cantidad_stock, p.precio,
                   COALESCE(pr.nombre, 'Sin proveedor') AS proveedor,
                   p.fecha_vencimiento
            FROM productos p
            LEFT JOIN proveedores pr ON pr.id_proveedor = p.id_proveedor
            ORDER BY p.categoria ASC, p.nombre ASC
        """
        return self.bd.ejecutar_consulta(sql)

    def _crear_tabla_reporte(self, filas, col_widths):
        """Crea una tabla con estilo común para reportes PDF."""
        datos = [[str(celda) if celda is not None else '-' for celda in fila] for fila in filas]
        tabla = Table(datos, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0e7a4b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BOTTOMMARGIN', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
            ])
        )
        return tabla

    def _ruta_reporte(self, nombre_archivo):
        if platform == "android":
            from android.storage import app_storage_path

            carpeta = os.path.join(app_storage_path(), "reportes")
        else:
            carpeta = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reportes")
        os.makedirs(carpeta, exist_ok=True)
        return os.path.join(carpeta, nombre_archivo)

    def exportar_pdf(self, tipo="movimientos", nombre_archivo="reporte_freshcontrol.pdf", anio=None, mes=None):
        """Genera un PDF con movimientos, vencimientos o inventario."""
        file_path = self._ruta_reporte(nombre_archivo)
        paginas = landscape(letter) if tipo == "movimientos" else letter

        if tipo == "vencidos_mensual":
            hoy = date.today()
            anio = int(anio or hoy.year)
            mes = int(mes or hoy.month)
            filas = self.obtener_vencidos_del_mes(anio, mes)
            titulo = f"Reporte mensual de productos vencidos - {mes:02d}/{anio}"
            datos = [["Producto", "Cantidad vencida", "Valor estimado", "Fecha de vencimiento"]]
            datos.extend([[str(fila[1]), str(fila[2]), f"{float(fila[3] or 0):.2f}", str(fila[4])] for fila in filas])
            if len(datos) == 1:
                datos.append(["Sin productos vencidos en el mes", "0", "0.00", "-"])
            else:
                total_unidades = sum(int(fila[2] or 0) for fila in filas)
                total_valor = sum(float(fila[3] or 0) for fila in filas)
                datos.append(["TOTAL", str(total_unidades), f"{total_valor:.2f}", "-"])
            story = [Paragraph(titulo, getSampleStyleSheet()["Title"]), Spacer(1, 12)]
            story.append(self._crear_tabla_reporte(datos, [55 * mm, 35 * mm, 35 * mm, 35 * mm]))
            SimpleDocTemplate(file_path, pagesize=letter).build(story)
            return file_path

        if tipo == "vencimiento":
            titulo = "Reporte de productos próximos a vencer"
            cabecera = ["ID", "Código", "Nombre", "Stock", "Vencimiento"]
            filas = self.obtener_productos_por_vencer(30)
            datos = [cabecera] + [[str(item[0]), str(item[1]), str(item[2]), str(item[3]), str(item[4])] for item in filas]
            col_widths = [12 * mm, 24 * mm, 42 * mm, 16 * mm, 28 * mm]
        else:
            titulo = "Reporte general de almacén"
            styles = getSampleStyleSheet()
            story = [Paragraph(titulo, styles['Title']), Spacer(1, 12)]

            story.append(Paragraph("Productos vencidos", styles['Heading2']))
            vencidos = self.obtener_productos_vencidos_completo()
            cabecera_vencidos = ["Producto", "Stock", "Vencimiento", "Proveedor", "Precio"]
            filas_vencidos = [cabecera_vencidos] + [[str(item[0]), str(item[1]), str(item[2]), str(item[3]), str(item[4])] for item in vencidos]
            story.append(self._crear_tabla_reporte(filas_vencidos, [42 * mm, 18 * mm, 28 * mm, 36 * mm, 20 * mm]))
            story.append(Spacer(1, 18))

            story.append(Paragraph("Inventario del almacén", styles['Heading2']))
            inventario = self.obtener_inventario_almacen()
            cabecera_inventario = ["Producto", "Categoría", "Stock", "Precio", "Proveedor", "Vencimiento"]
            filas_inventario = [cabecera_inventario] + [[str(item[0]), str(item[1]), str(item[2]), str(item[3]), str(item[4]), str(item[5] or '-') ] for item in inventario]
            story.append(self._crear_tabla_reporte(filas_inventario, [34 * mm, 24 * mm, 16 * mm, 18 * mm, 30 * mm, 28 * mm]))
            story.append(Spacer(1, 18))

            doc = SimpleDocTemplate(file_path, pagesize=paginas, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
            doc.build(story)
            return file_path

        styles = getSampleStyleSheet()
        story = [Paragraph(titulo, styles['Title']), Spacer(1, 12)]

        filas_formateadas = []
        for fila in datos:
            filas_formateadas.append([
                Paragraph(str(celda), styles['BodyText']) if i == len(fila) - 1 else str(celda)
                for i, celda in enumerate(fila)
            ])

        tabla = Table(filas_formateadas, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0e7a4b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BOTTOMMARGIN', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
            ])
        )
        story.append(tabla)

        doc = SimpleDocTemplate(file_path, pagesize=paginas, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
        doc.build(story)
        return file_path

    def exportar_excel(self, tipo="movimientos", nombre_archivo="reporte_freshcontrol.xlsx", anio=None, mes=None):
        """Genera un Excel con movimientos o vencimientos."""
        file_path = self._ruta_reporte(nombre_archivo)
        wb = Workbook()
        ws = wb.active
        ws.title = tipo.title()

        if tipo == "vencidos_mensual":
            hoy = date.today()
            anio = int(anio or hoy.year)
            mes = int(mes or hoy.month)
            ws.title = "Vencidos del mes"
            ws.append(["Producto", "Cantidad vencida", "Valor estimado", "Fecha de vencimiento"])
            filas_mes = self.obtener_vencidos_del_mes(anio, mes)
            for fila in filas_mes:
                ws.append([fila[1], fila[2], float(fila[3] or 0), fila[4]])
            if ws.max_row == 1:
                ws.append(["Sin productos vencidos en el mes", 0, 0, "-"])
            else:
                ws.append([
                    "TOTAL",
                    sum(int(fila[2] or 0) for fila in filas_mes),
                    sum(float(fila[3] or 0) for fila in filas_mes),
                    "-",
                ])
        elif tipo == "vencimiento":
            ws.append(["ID", "Código", "Nombre", "Stock", "Vencimiento"])
            for item in self.obtener_productos_por_vencer(30):
                ws.append([item[0], item[1], item[2], item[3], item[4]])
        else:
            ws.append(["ID", "Producto", "Tipo", "Cantidad", "Fecha", "Detalle", "Código de barras", "Categoría", "Sector"])
            for item in self.historial_movimientos(50):
                ws.append([item[0], item[1], item[2], item[3], item[4], item[5], item[6] or "-", item[7] or "-", item[8] or "Sin sector"])

        header_fill = PatternFill("solid", fgColor="0E7A4B")
        header_font = Font(color="FFFFFF", bold=True)
        thin = Side(style="thin", color="D0D0D0")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for hoja in wb.worksheets:
            for cell in hoja[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.border = border
                cell.alignment = cell.alignment.copy(wrap_text=True)

            for row in hoja.iter_rows(min_row=2, max_row=hoja.max_row, min_col=1, max_col=hoja.max_column):
                for cell in row:
                    cell.border = border
                    cell.alignment = cell.alignment.copy(wrap_text=True)
                    if cell.value is None:
                        cell.value = ""

            for column_cells in hoja.columns:
                max_length = 0
                column = column_cells[0].column_letter
                for cell in column_cells:
                    try:
                        cell_value = cell.value if cell.value is not None else ""
                        max_length = max(max_length, len(str(cell_value)))
                    except Exception:
                        pass
                hoja.column_dimensions[column].width = min(max(max_length + 2, 12), 40)

            hoja.freeze_panes = "A2"
            hoja.auto_filter.ref = hoja.dimensions
        wb.save(file_path)
        return file_path