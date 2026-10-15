# Archivo principal de la app.
# Sirve para arrancar la aplicación Kivy, cargar todas las vistas y coordinar la lógica general.
# Punto de entrada: inicia Kivy, carga las vistas y coordina pantallas, controladores y base de datos.
import os
import re
import json
import secrets
import shutil
import sys
import threading
import unicodedata
import uuid
import webbrowser
from datetime import date, datetime
from urllib.parse import urlencode

# Asegurar que la carpeta base de la app esté en el sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty, NumericProperty, ListProperty
from kivy.uix.image import Image
from kivy.uix.label import Label as KivyLabel
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton, MDRectangleFlatIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.fitimage import FitImage
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.pickers import MDDatePicker
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.textfield import MDTextField

from controladores.controlador_escaner import ControladorEscaner
from controladores.controlador_inventario import ControladorInventario
from controladores.controlador_reportes import ControladorReportes
from controladores.ocr_vencimiento import leer_fecha_en_imagen

from base_de_datos.gestor_bd import (
    GestorBD,
    inicializar_bd,
    registrar_usuario,
    verificar_credenciales,
    obtener_metricas_dashboard,
)

# Cargar archivos KV de la carpeta vistas
VISTAS_DIR = os.path.join(APP_DIR, "vistas")
AVATARES_DIR = os.path.join(APP_DIR, "recursos", "imagenes_empleados")
os.makedirs(AVATARES_DIR, exist_ok=True)
CATEGORIAS_PRODUCTO = ("Lácteos", "Carnes", "Enlatados", "Bebidas", "Granos", "Pastas", "Otros")

# SEGURIDAD DEL REGISTRO DE GERENTES
# Reemplaza el texto de abajo por la clave maestra privada del Analista.
CLAVE_MAESTRA_ANALISTA = "Admin_System_"
ARCHIVO_SEGURIDAD_REGISTRO_GERENTE = os.path.join(APP_DIR, "seguridad_registro_gerente.json")

def _leer_estado_registro_gerente():
    try:
        with open(ARCHIVO_SEGURIDAD_REGISTRO_GERENTE, "r", encoding="utf-8") as archivo:
            estado = json.load(archivo)
        return {"intentos": max(0, int(estado.get("intentos", 0))), "bloqueado": bool(estado.get("bloqueado", False))}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"intentos": 0, "bloqueado": False}

def _guardar_estado_registro_gerente(intentos, bloqueado):
    temporal = ARCHIVO_SEGURIDAD_REGISTRO_GERENTE + ".tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump({"intentos": int(intentos), "bloqueado": bool(bloqueado)}, archivo)
    os.replace(temporal, ARCHIVO_SEGURIDAD_REGISTRO_GERENTE)

def existe_gerente_registrado():
    gestor = GestorBD()
    for tabla in ("usuarios", "empleados"):
        try:
            filas = gestor.ejecutar_consulta(
                f"SELECT 1 FROM {tabla} WHERE lower(trim(rol)) = ? LIMIT 1", ("gerente",)
            )
            if filas:
                return True
        except Exception:
            continue
    return False


def normalizar_texto_busqueda(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn").casefold().strip()


def _luminancia_relativa(color):
    canales = []
    for canal in color[:3]:
        canal = max(0, min(1, float(canal)))
        canales.append(canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4)
    return 0.2126 * canales[0] + 0.7152 * canales[1] + 0.0722 * canales[2]


def _contraste(color_a, color_b):
    luminancia_a = _luminancia_relativa(color_a)
    luminancia_b = _luminancia_relativa(color_b)
    clara, oscura = max(luminancia_a, luminancia_b), min(luminancia_a, luminancia_b)
    return (clara + 0.05) / (oscura + 0.05)




def ajustar_textos_modo_oscuro(pantalla, es_oscuro):
    """Mantiene el texto legible sin recolorear iconos, botones ni tarjetas."""
    try:
        from kivy.uix.label import Label as KivyLabel
    except Exception:
        KivyLabel = ()
    try:
        from kivymd.uix.label import MDLabel
    except Exception:
        MDLabel = ()

    def fondos_ancestros(widget):
        colores = []
        actual = getattr(widget, "parent", None)
        # Protección contra ciclos inesperados en la cadena de padres de Kivy.
        visitados = set()
        while actual is not None and id(actual) not in visitados:
            visitados.add(id(actual))
            for atributo in ("md_bg_color", "background_color", "bg_color"):
                try:
                    valor = getattr(actual, atributo, None)
                    if valor is not None and len(valor) >= 3:
                        color = tuple(float(c) for c in valor)
                        alpha = color[3] if len(color) > 3 else 1.0
                        if alpha > 0.15:
                            colores.append(color)
                except Exception:
                    pass
            actual = getattr(actual, "parent", None)
        return colores

    for widget in pantalla.walk():
        clase = widget.__class__.__name__
        es_etiqueta = ((MDLabel and isinstance(widget, MDLabel)) or
                       (KivyLabel and isinstance(widget, KivyLabel)))
        if not es_etiqueta or "Icon" in clase or "Button" in clase:
            continue
        try:
            fondos = fondos_ancestros(widget)
            if not hasattr(widget, "_freshcontrol_color_texto_original"):
                widget._freshcontrol_color_texto_original = tuple(widget.color)

            # Si el texto está dentro de una tarjeta clara, usar texto oscuro aunque
            # la pantalla general esté en modo oscuro. Así no quedan letras blancas
            # sobre tarjetas blancas, y se conservan los colores de los paneles.
            luminancias = [_luminancia_relativa(c) for c in fondos]
            hay_fondo_claro = any(lum > 0.48 for lum in luminancias)
            hay_fondo_oscuro = any(lum < 0.18 for lum in luminancias)

            if es_oscuro:
                if hay_fondo_claro:
                    widget.color = (0.10, 0.12, 0.13, 1)
                elif hay_fondo_oscuro or not fondos:
                    widget.color = (0.94, 0.96, 0.97, 1)
            else:
                # En modo claro, restaurar el color original de cada etiqueta.
                widget.color = widget._freshcontrol_color_texto_original
        except Exception:
            pass


def aplicar_contraste_vistas(tema):
    """Cambia solo el fondo general; conserva colores originales de iconos, botones y mini paneles."""
    app = MDApp.get_running_app()
    administrador_pantallas = getattr(app, "root", None) if app else None
    if not administrador_pantallas:
        return

    es_oscuro = tema == "Dark"
    fondo_pantalla = (0.08, 0.09, 0.1, 1) if es_oscuro else (0.90, 0.92, 0.92, 1)

    # Solo se modifica el fondo base de cada panel. No recorrer ni recolorear
    # los widgets internos: sus tarjetas, mini paneles, iconos y botones
    # deben conservar los colores definidos originalmente en los archivos KV.
    for nombre_pantalla in ("panel_empleado", "panel_gerente"):
        try:
            pantalla = administrador_pantallas.get_screen(nombre_pantalla)
        except Exception:
            continue

        try:
            pantalla.md_bg_color = fondo_pantalla
        except Exception:
            pass

        ajustar_textos_modo_oscuro(pantalla, es_oscuro)


class CajaLecheIcon(Widget):
    """Icono vectorial dibujado con canvas: caja de leche con pico superior."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redibujar, size=self._redibujar)
        self._redibujar()

    def _redibujar(self, *_args):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        # Mantener proporciones aunque cambie el tamaño del widget.
        unit = min(w / 24.0, h / 24.0)
        bw, bh = 12 * unit, 15 * unit
        bx, by = x + (w - bw) / 2, y + (h - bh) / 2 - 1 * unit
        with self.canvas:
            # Frente de la caja
            Color(0.10, 0.62, 0.78, 1)
            from kivy.graphics import Mesh
            Mesh(vertices=[
                bx, by, 0, 0,
                bx + bw, by, 0, 0,
                bx + bw, by + bh, 0, 0,
                bx, by + bh, 0, 0,
            ], indices=[0, 1, 2, 0, 2, 3], mode='triangles')
            # Cara lateral para dar volumen
            Color(0.05, 0.43, 0.59, 1)
            Mesh(vertices=[
                bx + bw, by, 0, 0,
                bx + bw + 2 * unit, by + 1.5 * unit, 0, 0,
                bx + bw + 2 * unit, by + bh - 1.5 * unit, 0, 0,
                bx + bw, by + bh, 0, 0,
            ], indices=[0, 1, 2, 0, 2, 3], mode='triangles')
            # Pico/techo de cartón
            Color(0.16, 0.72, 0.84, 1)
            Mesh(vertices=[
                bx, by + bh, 0, 0,
                bx + 2.2 * unit, by + bh + 3.2 * unit, 0, 0,
                bx + bw - 1.2 * unit, by + bh + 3.2 * unit, 0, 0,
                bx + bw, by + bh, 0, 0,
            ], indices=[0, 1, 2, 0, 2, 3], mode='triangles')
            Color(0.04, 0.31, 0.40, 1)
            Line(points=[
                bx, by, bx + bw, by, bx + bw, by + bh,
                bx + bw - 1.2 * unit, by + bh + 3.2 * unit,
                bx + 2.2 * unit, by + bh + 3.2 * unit,
                bx, by + bh, bx, by,
            ], close=False, width=max(0.8, 0.8 * unit))
            # Etiqueta clara al frente
            Color(0.88, 0.97, 0.98, 1)
            RoundedRectangle(pos=(bx + 2.2 * unit, by + 4 * unit), size=(bw - 4.4 * unit, 4.5 * unit), radius=[1 * unit])
            Color(0.05, 0.43, 0.59, 1)
            Line(points=[bx + 4 * unit, by + 6.2 * unit, bx + bw - 4 * unit, by + 6.2 * unit], width=max(0.7, 0.8 * unit))


class LataIcon(Widget):
    """Icono vectorial de lata cilíndrica con tapa y bordes visibles."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redibujar, size=self._redibujar)
        self._redibujar()

    def _redibujar(self, *_args):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        unit = min(w / 24.0, h / 24.0)
        bw, bh = 12 * unit, 15 * unit
        bx, by = x + (w - bw) / 2, y + (h - bh) / 2
        with self.canvas:
            # Cuerpo metálico de la lata
            Color(0.73, 0.39, 0.13, 1)
            RoundedRectangle(pos=(bx, by + 2 * unit), size=(bw, bh - 4 * unit), radius=[1.5 * unit])
            # Luz en el lateral
            Color(0.91, 0.61, 0.30, 1)
            Line(points=[bx + 2 * unit, by + 4 * unit, bx + 2 * unit, by + bh - 4 * unit], width=max(1, 1.1 * unit))
            # Borde inferior
            Color(0.40, 0.24, 0.13, 1)
            Ellipse(pos=(bx, by), size=(bw, 4 * unit))
            Color(0.86, 0.72, 0.53, 1)
            Ellipse(pos=(bx + 0.5 * unit, by + 0.6 * unit), size=(bw - unit, 2.5 * unit))
            # Tapa superior y sus aros
            Color(0.84, 0.78, 0.66, 1)
            Ellipse(pos=(bx, by + bh - 4 * unit), size=(bw, 5 * unit))
            Color(0.39, 0.35, 0.30, 1)
            Line(ellipse=(bx + 1.2 * unit, by + bh - 3.2 * unit, bw - 2.4 * unit, 3 * unit), width=max(0.7, 0.8 * unit))
            Line(ellipse=(bx + 2.5 * unit, by + bh - 2.8 * unit, bw - 5 * unit, 2 * unit), width=max(0.6, 0.7 * unit))


# Carga de vistas KV
for archivo_kv in [
    "inicio_sesion.kv",
    "registro_gerente.kv",
    "registro_empleado.kv",
    "panel_empleado.kv",
    "panel_gerente.kv",
    "escaner.kv",
]:
    ruta_kv = os.path.join(VISTAS_DIR, archivo_kv)
    if os.path.exists(ruta_kv):
        Builder.load_file(ruta_kv)


def mostrar_dialogo_simple(title, text):
    dialog = MDDialog(
        title=title,
        text=text,
        buttons=[MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss())],
    )
    dialog.open()
    return dialog

def color_categoria_producto(categoria):
    """Devuelve un color consistente para cada categoría del inventario."""
    nombre = normalizar_texto_busqueda(str(categoria or "")).strip()
    paleta = {
        "lacteos": ((0.89, 0.96, 0.90, 1), (0.08, 0.42, 0.20, 1)),
        "carnes": ((1.00, 0.90, 0.90, 1), (0.70, 0.12, 0.12, 1)),
        "granos": ((1.00, 0.94, 0.80, 1), (0.58, 0.35, 0.00, 1)),
        "enlatados": ((0.88, 0.94, 1.00, 1), (0.08, 0.32, 0.68, 1)),
        "bebidas": ((0.86, 0.96, 0.94, 1), (0.04, 0.42, 0.38, 1)),
        "pastas": ((1.00, 0.91, 0.82, 1), (0.66, 0.30, 0.08, 1)),
        "frutas": ((1.00, 0.91, 0.78, 1), (0.55, 0.31, 0.10, 1)),
        "otros": ((0.93, 0.90, 1.00, 1), (0.38, 0.20, 0.62, 1)),
        "general": ((0.92, 0.94, 0.95, 1), (0.25, 0.30, 0.34, 1)),
        "sin categoria": ((0.94, 0.94, 0.94, 1), (0.30, 0.30, 0.30, 1)),
    }
    return paleta.get(nombre, ((0.91, 0.95, 0.92, 1), (0.08, 0.38, 0.22, 1)))


def mostrar_inventario_visual(titulo, limite=None, permitir_busqueda=False, permitir_aviso=False):
    gestor = GestorBD()
    columnas = {
        fila[1] for fila in gestor.ejecutar_consulta("PRAGMA table_info(productos)")
    }
    expresion_sector = "pasillo" if "pasillo" in columnas else "'Sin sector'"
    expresion_imagen = "imagen" if "imagen" in columnas else "''"
    orden = (
        "nombre COLLATE NOCASE"
        if permitir_busqueda
        else "categoria COLLATE NOCASE, nombre COLLATE NOCASE"
    )
    sql = f"""
        SELECT nombre, codigo_barras, categoria, cantidad_stock,
               fecha_vencimiento, {expresion_sector}, {expresion_imagen}
        FROM productos
        ORDER BY {orden}
    """
    parametros = ()
    if limite is not None:
        sql += " LIMIT ?"
        parametros = (limite,)
    productos = gestor.ejecutar_consulta(sql, parametros)
    if not productos and not permitir_busqueda:
        mostrar_dialogo_simple(titulo, "No hay productos registrados.")
        return

    categorias_globales = [
        str(categoria or "").strip()
        for categoria, *_ in gestor.ejecutar_consulta(
            "SELECT DISTINCT categoria FROM productos WHERE categoria IS NOT NULL AND TRIM(categoria) != '' ORDER BY categoria COLLATE NOCASE"
        )
    ]
    categorias_globales = list(dict.fromkeys(
        (*CATEGORIAS_PRODUCTO, *(categoria for categoria in categorias_globales if categoria))
    ))

    contenido = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10), size_hint_y=None)
    contenido.bind(minimum_height=contenido.setter("height"))
    filas_busqueda = []
    categoria_actual = None

    def agregar_etiqueta_adaptable(contenedor, texto, **opciones):
        opciones.setdefault("size_hint_y", None)
        etiqueta = MDLabel(text=texto, valign="middle", **opciones)
        etiqueta.bind(width=lambda widget, ancho: setattr(widget, "text_size", (ancho, None)))
        etiqueta.bind(texture_size=lambda widget, tamano: setattr(widget, "height", tamano[1] + dp(6)))
        contenedor.add_widget(etiqueta)
        return etiqueta

    for nombre, codigo, categoria, stock, vencimiento, sector, imagen in productos:
        categoria = categoria or "Sin categoría"
        if not permitir_busqueda and categoria != categoria_actual:
            categoria_actual = categoria
            fondo_categoria, texto_categoria = color_categoria_producto(categoria_actual)
            encabezado_categoria = MDCard(
                size_hint_y=None,
                height=dp(34),
                padding=[dp(10), dp(4)],
                radius=[7],
                elevation=0,
                md_bg_color=fondo_categoria,
            )
            agregar_etiqueta_adaptable(
                encabezado_categoria,
                f"CATEGORÍA  ·  {categoria_actual.upper()}",
                bold=True,
                font_style="Caption",
                theme_text_color="Custom",
                text_color=texto_categoria,
                height=dp(24),
            )
            contenido.add_widget(encabezado_categoria)

        if vencimiento:
            try:
                texto_fecha = str(vencimiento).strip()[:10]
                formatos_fecha = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
                fecha = None
                for formato in formatos_fecha:
                    try:
                        fecha = datetime.strptime(texto_fecha, formato).date()
                        break
                    except ValueError:
                        continue
                if fecha is None:
                    raise ValueError("Formato de fecha no reconocido")
                dias = (fecha - date.today()).days
                if dias < 0:
                    texto_estado = f"Vencido hace {abs(dias)} día(s)"
                    color_estado = (0.78, 0.12, 0.12, 1)
                    color_fila = (1, 0.94, 0.93, 1)
                elif dias == 0:
                    texto_estado = "Vence hoy"
                    color_estado = (0.85, 0.42, 0.05, 1)
                    color_fila = (1, 0.97, 0.89, 1)
                else:
                    texto_estado = (
                        f"Por vencer en {dias} día(s)"
                        if dias <= 7
                        else f"Vigente · quedan {dias} día(s)"
                    )
                    color_estado = (0.12, 0.48, 0.28, 1) if dias > 7 else (0.85, 0.42, 0.05, 1)
                    color_fila = (0.94, 0.98, 0.94, 1) if dias > 7 else (1, 0.97, 0.89, 1)
                texto_fecha = f"Vence: {fecha.strftime('%d/%m/%Y')}  ·  {texto_estado}"
            except ValueError:
                texto_fecha = f"Vencimiento: {vencimiento} | Fecha no válida"
                color_estado = (0.45, 0.45, 0.45, 1)
                color_fila = (0.97, 0.97, 0.97, 1)
        else:
            texto_fecha = "Sin fecha de vencimiento"
            color_estado = (0.45, 0.45, 0.45, 1)
            color_fila = (0.97, 0.97, 0.97, 1)

        fila = MDCard(
            orientation="horizontal",
            spacing=dp(12),
            padding=dp(8),
            radius=[8],
            elevation=0,
            md_bg_color=color_fila,
            size_hint_y=None,
        )
        fila.bind(minimum_height=fila.setter("height"))
        miniatura = MDCard(
            size_hint=(None, None),
            size=(dp(72), dp(72)),
            radius=[6],
            elevation=0,
            md_bg_color=(1, 1, 1, 0.8),
        )
        ruta_imagen = str(imagen or "").strip()
        if ruta_imagen and not os.path.isabs(ruta_imagen):
            ruta_imagen = os.path.join(APP_DIR, ruta_imagen)
        if ruta_imagen and os.path.isfile(ruta_imagen):
            miniatura.add_widget(
                Image(source=ruta_imagen, allow_stretch=True, keep_ratio=True)
            )
        else:
            miniatura.add_widget(
                MDLabel(
                    text="Sin imagen",
                    halign="center",
                    valign="middle",
                    font_style="Caption",
                    theme_text_color="Hint",
                )
            )
        fila.add_widget(miniatura)

        datos = BoxLayout(orientation="vertical", spacing=dp(3), size_hint_y=None)
        datos.bind(minimum_height=datos.setter("height"))
        agregar_etiqueta_adaptable(
            datos,
            nombre,
            bold=True,
            font_style="Subtitle2",
            theme_text_color="Custom",
            text_color=(0.12, 0.17, 0.14, 1),
        )
        agregar_etiqueta_adaptable(
            datos,
            (
                f"Categoría: {categoria}  ·  Código: {codigo or '-'}  ·  Stock: {stock or 0}  ·  Sector: {sector or 'Sin sector'}"
                if permitir_busqueda
                else f"Código: {codigo or '-'}  ·  Stock: {stock or 0}  ·  Sector: {sector or 'Sin sector'}"
            ),
            font_style="Caption",
            theme_text_color="Custom",
            text_color=(0.32, 0.37, 0.34, 1),
        )
        agregar_etiqueta_adaptable(
            datos,
            texto_fecha,
            font_style="Caption",
            theme_text_color="Custom",
            text_color=color_estado,
        )
        fila.add_widget(datos)
        if permitir_aviso and vencimiento:
            try:
                fecha_producto = datetime.strptime(str(vencimiento)[:10], "%Y-%m-%d").date()
                dias_restantes = (fecha_producto - date.today()).days
                if 0 < dias_restantes <= 21:
                    fila.add_widget(MDIconButton(
                        icon="email-outline",
                        tooltip_text="Preparar aviso de venta al jefe",
                        on_release=lambda _button, p=nombre, f=fecha_producto, s=stock: preparar_aviso_venta(p, f, s),
                    ))
            except ValueError:
                pass
        if permitir_busqueda:
            filas_busqueda.append((
                normalizar_texto_busqueda(nombre),
                normalizar_texto_busqueda(categoria),
                normalizar_texto_busqueda(codigo),
                int(stock or 0),
                fila,
            ))
        else:
            contenido.add_widget(fila)

    scroll = ScrollView(
        size_hint_y=None,
        height=dp(420) if permitir_busqueda else min(dp(500), max(dp(180), contenido.height + dp(20))),
    )
    scroll.add_widget(contenido)
    contenido_dialogo = scroll
    if permitir_busqueda:
        campo_busqueda = MDTextField(
            hint_text="Nombre, código de barras o categoría",
            mode="rectangle",
            size_hint_y=None,
            height=dp(48),
        )
        # Selector de categorías: iconos Material Design reales (no emojis),
        # con colores suaves por categoría. El filtro conserva los nombres originales.
        iconos_categorias = {
            "todas": "view-grid",
            "lacteos": "package-variant",  # Caja de leche
            "carnes": "food-steak",
            "enlatados": "food-can",  # Lata de conserva
            "bebidas": "bottle-soda",
            "granos": "barley",
            "pastas": "pasta",
            "otros": "package-variant",
            "frutas": "food-apple",
            "general": "package-variant",
        }
        # Colores moderados (aprox. 50% menos intensos), manteniendo buen contraste.
        # Frutas usa durazno suave y Otros celeste.
        colores_selector = {
            # Paleta moderna, algo desaturada, con contraste legible.
            "todas": ((0.12, 0.38, 0.29, 1), (1, 1, 1, 1)),
            "lacteos": ((0.42, 0.68, 0.49, 1), (1, 1, 1, 1)),
            "carnes": ((0.73, 0.34, 0.37, 1), (1, 1, 1, 1)),
            "enlatados": ((0.34, 0.52, 0.75, 1), (1, 1, 1, 1)),
            "bebidas": ((0.25, 0.59, 0.56, 1), (1, 1, 1, 1)),
            "granos": ((0.83, 0.68, 0.34, 1), (0.20, 0.16, 0.08, 1)),
            "pastas": ((0.83, 0.52, 0.33, 1), (1, 1, 1, 1)),
            "otros": ((0.47, 0.70, 0.82, 1), (0.06, 0.18, 0.25, 1)),
            "frutas": ((0.91, 0.73, 0.47, 1), (0.28, 0.18, 0.08, 1)),
            "general": ((0.43, 0.47, 0.51, 1), (1, 1, 1, 1)),
        }

        def clave_categoria_selector(nombre):
            return normalizar_texto_busqueda(str(nombre or "")).strip().lower()

        class OpcionCategoria(SpinnerOption):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.size_hint_y = None
                self.height = dp(42)
                self.background_normal = ""
                self.background_down = ""
                self.background_color = (0, 0, 0, 0)
                self.halign = "left"
                self.padding = (dp(14), 0)
                # Fondo redondeado separado del borde de cada opción.
                with self.canvas.before:
                    self._fondo_color = Color(0.9, 0.9, 0.9, 1)
                    self._fondo_redondeado = RoundedRectangle(
                        pos=self.pos, size=self.size, radius=[dp(12)]
                    )
                self.bind(pos=self._actualizar_fondo_redondeado,
                          size=self._actualizar_fondo_redondeado)
                self._icono_categoria = MDIcon(
                    icon="package-variant",
                    size_hint=(None, None),
                    size=(dp(22), dp(22)),
                    theme_text_color="Custom",
                )
                self._etiqueta_categoria = KivyLabel(
                    text="",
                    halign="left",
                    valign="middle",
                    color=(0.15, 0.25, 0.20, 1),
                    font_size="14sp",
                )
                self.add_widget(self._icono_categoria)
                self.add_widget(self._etiqueta_categoria)
                self.bind(text=self.aplicar_estilo_categoria, pos=self._ubicar_contenido_opcion,
                          size=self._ubicar_contenido_opcion)
                self.aplicar_estilo_categoria()
                self._ubicar_contenido_opcion()

            def _actualizar_fondo_redondeado(self, *_args):
                self._fondo_redondeado.pos = (self.x + dp(3), self.y + dp(2))
                self._fondo_redondeado.size = (max(0, self.width - dp(6)), max(0, self.height - dp(4)))

            def _ubicar_contenido_opcion(self, *_args):
                self._icono_categoria.pos = (self.x + dp(14), self.y + (self.height - dp(22)) / 2)
                self._etiqueta_categoria.pos = (self.x + dp(46), self.y)
                self._etiqueta_categoria.size = (max(dp(50), self.width - dp(54)), self.height)

            def aplicar_estilo_categoria(self, *_args):
                nombre = str(self.text or "").strip()
                clave = clave_categoria_selector(nombre)
                fondo, tinta = colores_selector.get(
                    clave, ((0.94, 0.96, 0.95, 1), (0.15, 0.25, 0.20, 1))
                )
                self._fondo_color.rgba = fondo
                # El botón queda transparente; el fondo visible es el rectángulo redondeado.
                self.background_color = (0, 0, 0, 0)
                self.color = (0, 0, 0, 0)
                self._icono_categoria.icon = iconos_categorias.get(clave, "package-variant")
                self._icono_categoria.text_color = tinta
                self._etiqueta_categoria.text = nombre
                self._etiqueta_categoria.color = tinta

        class SelectorCategorias(Spinner):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.background_normal = ""
                self.background_down = ""
                self.background_color = colores_selector["todas"][0]
                self.color = colores_selector["todas"][1]
                self.option_cls = OpcionCategoria
                self.bind(text=self.actualizar_color_seleccion)

            def actualizar_color_seleccion(self, _instance, texto):
                clave = clave_categoria_selector(texto)
                fondo, tinta = colores_selector.get(
                    clave, ((0.10, 0.38, 0.25, 1), (1, 1, 1, 1))
                )
                self.background_color = fondo
                self.color = tinta

        nombres_categorias_selector = ["Todas", *categorias_globales]
        categoria_spinner = SelectorCategorias(
            text="Todas",
            values=nombres_categorias_selector,
            size_hint=(1, None),
            height=dp(40),
        )
        panel_busqueda = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(520),
        )
        panel_busqueda.add_widget(MDLabel(text="Buscar por nombre, código o categoría", font_style="Caption", theme_text_color="Secondary"))
        panel_busqueda.add_widget(categoria_spinner)
        panel_busqueda.add_widget(campo_busqueda)
        panel_busqueda.add_widget(scroll)

        def filtrar_productos(_campo, *_args):
            prefijo = normalizar_texto_busqueda(campo_busqueda.text)
            categoria_seleccionada = categoria_spinner.text.strip()
            categoria_filtro = (
                normalizar_texto_busqueda(categoria_seleccionada)
                if categoria_seleccionada and categoria_seleccionada != "Todas"
                else ""
            )
            coincidencias = [
                (stock, fila) for nombre, categoria, codigo, stock, fila in filas_busqueda
                if (not prefijo or prefijo in nombre or prefijo in codigo or prefijo in categoria)
                and (not categoria_filtro or categoria == categoria_filtro)
            ]
            contenido.clear_widgets()
            productos_en_stock = [(stock, fila) for stock, fila in coincidencias if stock > 0]
            if productos_en_stock:
                for _stock, fila in productos_en_stock:
                    contenido.add_widget(fila)
            else:
                contenido.add_widget(
                    MDLabel(
                        text=(
                            f"No está en stock en la categoría {categoria_seleccionada}."
                            if categoria_filtro
                            else "No está en stock ningún producto que coincida con la búsqueda."
                        ),
                        size_hint_y=None,
                        height=dp(54),
                        halign="center",
                        valign="middle",
                    )
                )

        campo_busqueda.bind(text=filtrar_productos)
        categoria_spinner.bind(text=filtrar_productos)
        filtrar_productos(campo_busqueda, campo_busqueda.text)
        contenido_dialogo = panel_busqueda

    dialog = MDDialog(
        title=titulo,
        type="custom",
        content_cls=contenido_dialogo,
        buttons=[MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss())],
    )
    dialog.open()


def mostrar_movimientos_visual(titulo):
    movimientos = GestorBD().listar_movimientos(None)
    contenido = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
    contenido.bind(minimum_height=contenido.setter("height"))
    scroll = ScrollView(size_hint_y=None, height=dp(410))
    scroll.add_widget(contenido)
    campo_busqueda = MDTextField(
        hint_text="Producto, categoría, tipo, código o detalle",
        mode="rectangle",
        size_hint_y=None,
        height=dp(48),
    )
    tipos = sorted({str(fila[3]).title() for fila in movimientos})
    tipo_spinner = Spinner(
        text="Todos",
        values=["Todos", *tipos],
        size_hint=(1, None),
        height=dp(40),
    )

    def filtrar_movimientos(_widget, *_args):
        termino = normalizar_texto_busqueda(campo_busqueda.text)
        tipo_seleccionado = normalizar_texto_busqueda(tipo_spinner.text)
        contenido.clear_widgets()
        coincidencias = [
            fila for fila in movimientos
            if (not termino or termino in normalizar_texto_busqueda(" ".join(str(valor or "") for valor in fila[1:])))
            and (tipo_seleccionado == "todos" or normalizar_texto_busqueda(fila[3]) == tipo_seleccionado)
        ]
        if not coincidencias:
            contenido.add_widget(MDLabel(
                text="No hay movimientos que coincidan con esa búsqueda.",
                size_hint_y=None,
                height=dp(48),
                halign="center",
                valign="middle",
            ))
            return
        for fila in coincidencias:
            contenido.add_widget(MDLabel(
                text=(
                    f"{fila[1]} · {fila[2] or 'Sin categoría'}\n"
                    f"{fila[3].title()} {fila[4]} · {fila[5]} · Código: {fila[7] or '-'} · "
                    f"Sector: {fila[8] or 'Sin sector'} · {fila[6] or '-'}"
                ),
                size_hint_y=None,
                height=dp(62),
                valign="middle",
                text_size=(Window.width * 0.68, None),
            ))

    campo_busqueda.bind(text=filtrar_movimientos)
    tipo_spinner.bind(text=filtrar_movimientos)
    filtrar_movimientos(campo_busqueda)
    panel = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8), size_hint_y=None, height=dp(520))
    panel.add_widget(tipo_spinner)
    panel.add_widget(campo_busqueda)
    panel.add_widget(scroll)
    dialog = MDDialog(
        title=titulo,
        type="custom",
        content_cls=panel,
        buttons=[MDFlatButton(text="Cerrar", on_release=lambda _button: dialog.dismiss())],
    )
    dialog.open()


def preparar_aviso_venta(nombre, vencimiento, stock):
    dias = (vencimiento - date.today()).days
    asunto = f"Oferta sugerida: {nombre} próximo a vencer"
    cuerpo = (
        f"Sugiero ofrecer el producto {nombre} antes de su vencimiento. "
        f"Stock disponible: {stock or 0}. Fecha de vencimiento: {vencimiento:%d/%m/%Y} "
        f"(faltan {dias} días)."
    )
    if platform == "android":
        try:
            from jnius import autoclass

            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            intent = Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:"))
            intent.putExtra(Intent.EXTRA_SUBJECT, asunto)
            intent.putExtra(Intent.EXTRA_TEXT, cuerpo)
            autoclass("org.kivy.android.PythonActivity").mActivity.startActivity(intent)
            return
        except Exception:
            pass
    webbrowser.open("mailto:?" + urlencode({"subject": asunto, "body": cuerpo}))


def iniciar_captura_foto_producto(on_complete):
    if platform != "android":
        carpeta_fotos = os.path.join(MDApp.get_running_app().user_data_dir, "imagenes_productos")
        os.makedirs(carpeta_fotos, exist_ok=True)
        selector = FileChooserListView(
            path=os.path.expanduser("~/Pictures"),
            filters=["*.png", "*.jpg", "*.jpeg", "*.webp"],
            multiselect=False,
        )
        selector.bind(on_submit=lambda *_args: usar_foto())
        contenido = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(360))
        contenido.add_widget(selector)
        dialog = MDDialog(
            title="Adjuntar foto del producto",
            type="custom",
            content_cls=contenido,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda _button: dialog.dismiss()),
                MDRaisedButton(text="Usar imagen", on_release=lambda _button: usar_foto()),
            ],
        )

        def usar_foto(*_args):
            if not selector.selection:
                return
            origen = selector.selection[0]
            extension = os.path.splitext(origen)[1].lower()
            destino = os.path.join(carpeta_fotos, f"producto_{uuid.uuid4().hex}{extension}")
            try:
                shutil.copy2(origen, destino)
                dialog.dismiss()
                on_complete(destino)
            except OSError as exc:
                on_complete(None, str(exc))

        dialog.open()
        return

    try:
        from android import activity as android_activity
        from jnius import autoclass
        from kivy.clock import Clock

        app = MDApp.get_running_app()
        carpeta = os.path.join(app.user_data_dir, "imagenes_productos")
        os.makedirs(carpeta, exist_ok=True)
        destino = os.path.join(carpeta, f"producto_{uuid.uuid4().hex}.jpg")
        codigo_solicitud = 0xFC01
        actividad = autoclass("org.kivy.android.PythonActivity").mActivity
        intent = autoclass("android.content.Intent")(
            autoclass("android.provider.MediaStore").ACTION_IMAGE_CAPTURE
        )

        def resultado_camara(codigo, resultado, datos):
            if codigo != codigo_solicitud:
                return
            android_activity.unbind(on_activity_result=resultado_camara)
            if resultado != -1 or datos is None:
                Clock.schedule_once(lambda _dt: on_complete(None), 0)
                return
            try:
                extras = datos.getExtras()
                bitmap = extras.get("data") if extras else None
                if bitmap is None:
                    raise ValueError("La cámara no devolvió una imagen.")
                salida = autoclass("java.io.FileOutputStream")(destino)
                formato = autoclass("android.graphics.Bitmap$CompressFormat").JPEG
                bitmap.compress(formato, 90, salida)
                salida.flush()
                salida.close()
                Clock.schedule_once(lambda _dt: on_complete(destino), 0)
            except Exception as exc:
                mensaje_error = str(exc)
                Clock.schedule_once(
                    lambda _dt, mensaje=mensaje_error: on_complete(None, mensaje), 0
                )

        android_activity.bind(on_activity_result=resultado_camara)
        actividad.startActivityForResult(intent, codigo_solicitud)
    except Exception as exc:
        on_complete(None, str(exc))


def crear_campo_formulario(hint_text, **kwargs):
    return MDTextField(
        hint_text=hint_text,
        mode="rectangle",
        size_hint_y=None,
        height=dp(48),
        **kwargs,
    )


def aplicar_color_texto_selector(selector):
    color_texto = (0.08, 0.08, 0.08, 1)

    def colorear_fila(_selector, fila, _padre):
        for widget in fila.walk():
            if isinstance(widget, KivyLabel):
                widget.color = color_texto

    selector.bind(on_entry_added=colorear_fila)
    selector.bind(on_subentry_to_entry=colorear_fila)
    for widget in selector.walk():
        if isinstance(widget, KivyLabel):
            widget.color = color_texto


def ruta_avatar(usuario):
    nombre_seguro = re.sub(r"[^a-zA-Z0-9_-]", "_", str(usuario or "empleado"))
    for extension in (".png", ".jpg", ".jpeg", ".webp"):
        ruta = os.path.join(AVATARES_DIR, nombre_seguro + extension)
        if os.path.exists(ruta):
            return ruta
    return ""


def guardar_avatar(usuario, ruta_origen):
    nombre_seguro = re.sub(r"[^a-zA-Z0-9_-]", "_", str(usuario or "empleado"))
    extension = os.path.splitext(ruta_origen)[1].lower()
    if extension not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Selecciona una imagen PNG, JPG o WEBP.")
    for otra_extension in (".png", ".jpg", ".jpeg", ".webp"):
        ruta_anterior = os.path.join(AVATARES_DIR, nombre_seguro + otra_extension)
        if os.path.exists(ruta_anterior):
            os.remove(ruta_anterior)
    destino = os.path.join(AVATARES_DIR, nombre_seguro + extension)
    shutil.copy2(ruta_origen, destino)
    return destino


class PantallaInicioSesion(MDScreen):
    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def _mostrar_desbloqueo_gerente(self):
        contenido = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(8),
            size_hint_y=None,
            height=dp(150),
        )
        usuario_gerente = MDTextField(hint_text="Usuario del gerente", mode="rectangle")
        password_gerente = MDTextField(
            hint_text="Contraseña del gerente",
            password=True,
            mode="rectangle",
        )
        mensaje = MDLabel(
            text="Inicia sesión con una cuenta gerente para desbloquear el sistema.",
            size_hint_y=None,
            height=dp(38),
            font_style="Caption",
            theme_text_color="Secondary",
        )
        contenido.add_widget(usuario_gerente)
        contenido.add_widget(password_gerente)
        contenido.add_widget(mensaje)

        def desbloquear(_boton):
            gerente = verificar_credenciales(
                usuario_gerente.text.strip(),
                password_gerente.text.strip(),
            )
            rol = gerente["rol"] if gerente and hasattr(gerente, "keys") else (
                gerente[8] if gerente else ""
            )
            if not gerente or str(rol).strip().lower() != "gerente":
                mensaje.text = "Credenciales de gerente incorrectas."
                mensaje.theme_text_color = "Custom"
                mensaje.text_color = (0.8, 0.2, 0.2, 1)
                return

            GestorBD().reiniciar_estado_acceso()
            self.ids.usuario_field.text = usuario_gerente.text.strip()
            self.ids.password_field.text = password_gerente.text.strip()
            dialog.dismiss()
            self.iniciar_sesion()

        dialog = MDDialog(
            title="Sistema bloqueado",
            type="custom",
            content_cls=contenido,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda _button: dialog.dismiss()),
                MDRaisedButton(text="Desbloquear", on_release=desbloquear),
            ],
        )
        dialog.open()

    def iniciar_sesion(self):
        usuario = self.ids.usuario_field.text.strip()
        password = self.ids.password_field.text.strip()
        label_error = self.ids.mensaje_error

        gestor = GestorBD()
        intentos_fallidos, bloqueado = gestor.obtener_estado_acceso()
        if bloqueado:
            label_error.text = "Sistema bloqueado. Se requiere autorización del gerente."
            self._mostrar_desbloqueo_gerente()
            return

        if not usuario or not password:
            label_error.text = "Por favor ingrese usuario y contraseña"
            return

        usuario_db = verificar_credenciales(usuario, password)

        if usuario_db:
            gestor.reiniciar_estado_acceso()
            label_error.text = ""
            self.ids.usuario_field.text = ""
            self.ids.password_field.text = ""

            app = MDApp.get_running_app()
            
            # Conversión segura de sqlite3.Row o tupla a diccionario estándar
            if hasattr(usuario_db, "keys"):
                app.usuario_activo = {key: usuario_db[key] for key in usuario_db.keys()}
            elif isinstance(usuario_db, dict):
                app.usuario_activo = dict(usuario_db)
            else:
                app.usuario_activo = {
                    "id": usuario_db[0],
                    "nombre": usuario_db[1],
                    "apellido": usuario_db[2],
                    "usuario": usuario_db[3],
                    "email": usuario_db[5],
                    "telefono": usuario_db[6],
                    "cargo": usuario_db[7],
                    "rol": str(usuario_db[8]).strip().lower()
                }

            rol = str(app.usuario_activo.get("rol", "")).lower().strip()
            if rol == "gerente":
                self.manager.current = "panel_gerente"
            elif rol == "empleado":
                self.manager.current = "panel_empleado"
            else:
                label_error.text = f"Rol de usuario desconocido: {rol}"
        else:
            intentos_fallidos, bloqueado = gestor.registrar_fallo_acceso()
            if bloqueado:
                label_error.text = "Sistema bloqueado tras 5 intentos. Solo el gerente puede desbloquearlo."
                self._mostrar_desbloqueo_gerente()
            else:
                label_error.text = (
                    f"Usuario o contraseña incorrectos. Intento {intentos_fallidos} de 5."
                )

    def iniciar_sesion_google(self):
        _intentos, bloqueado = GestorBD().obtener_estado_acceso()
        if bloqueado:
            self.ids.mensaje_error.text = "Sistema bloqueado. Se requiere autorización del gerente."
            self._mostrar_desbloqueo_gerente()
            return
        if platform == "android":
            self.ids.mensaje_error.text = "Configura un cliente OAuth móvil de Google para habilitar este acceso en Android."
            return
        archivo_credenciales = os.path.join(APP_DIR, "client_secret.json")
        if not os.path.isfile(archivo_credenciales):
            self.ids.mensaje_error.text = "No se encontró freshcontrol_app/client_secret.json."
            return

        self.ids.mensaje_error.text = "Abriendo autenticación segura de Google..."

        def autenticar():
            try:
                from google.auth.transport.requests import AuthorizedSession
                from google_auth_oauthlib.flow import InstalledAppFlow
                from kivy.clock import Clock

                flujo = InstalledAppFlow.from_client_secrets_file(
                    archivo_credenciales,
                    ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
                )
                credenciales = flujo.run_local_server(port=0, open_browser=True)
                respuesta = AuthorizedSession(credenciales).get(
                    "https://www.googleapis.com/oauth2/v2/userinfo", timeout=10
                )
                respuesta.raise_for_status()
                perfil = respuesta.json()
                if not perfil.get("verified_email") or not perfil.get("email"):
                    raise ValueError("Google no devolvió un correo verificado.")
                Clock.schedule_once(lambda _dt: self._completar_login_google(perfil), 0)
            except Exception as exc:
                from kivy.clock import Clock
                mensaje = str(exc)
                Clock.schedule_once(
                    lambda _dt: setattr(self.ids.mensaje_error, "text", f"No se pudo iniciar con Google: {mensaje}"),
                    0,
                )

        threading.Thread(target=autenticar, daemon=True).start()

    def _completar_login_google(self, perfil):
        email = perfil["email"].strip().lower()
        gestor = GestorBD()
        cuenta = gestor.ejecutar_consulta(
            "SELECT id_usuario AS id, nombre, apellido, usuario, email, telefono, cargo, rol "
            "FROM usuarios WHERE lower(email) = ? UNION ALL "
            "SELECT id_empleado AS id, nombre, apellido, usuario, email, telefono, cargo, rol "
            "FROM empleados WHERE lower(email) = ? LIMIT 1",
            (email, email),
        )
        if not cuenta:
            base_usuario = re.sub(r"[^a-zA-Z0-9_.-]", "_", email.split("@", 1)[0]) or "google"
            usuario = base_usuario
            sufijo = 1
            while gestor.ejecutar_consulta(
                "SELECT 1 FROM usuarios WHERE usuario = ? UNION SELECT 1 FROM empleados WHERE usuario = ? LIMIT 1",
                (usuario, usuario),
            ):
                sufijo += 1
                usuario = f"{base_usuario}_{sufijo}"
            nombre = perfil.get("given_name") or email.split("@", 1)[0]
            exito, mensaje = registrar_usuario(
                nombre, perfil.get("family_name", ""), usuario,
                secrets.token_urlsafe(32), email, "", cargo="Empleado", rol="empleado",
            )
            if not exito:
                self.ids.mensaje_error.text = mensaje
                return
            cuenta = gestor.ejecutar_consulta(
                "SELECT id_empleado AS id, nombre, apellido, usuario, email, telefono, cargo, rol "
                "FROM empleados WHERE lower(email) = ? LIMIT 1", (email,),
            )
        self.ids.mensaje_error.text = ""
        app = MDApp.get_running_app()
        columnas = ("id", "nombre", "apellido", "usuario", "email", "telefono", "cargo", "rol")
        app.usuario_activo = dict(zip(columnas, cuenta[0]))
        destino = "panel_gerente" if str(app.usuario_activo.get("rol", "")).lower() == "gerente" else "panel_empleado"
        self.manager.current = destino

    def _mostrar_autorizacion_gerente(self):
        contenido = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10), size_hint_y=None, height=dp(180))
        campo_usuario = MDTextField(hint_text="Usuario del gerente registrado", mode="rectangle")
        campo_clave = MDTextField(hint_text="Contraseña del gerente", password=True, mode="rectangle")
        mensaje = MDLabel(text="Se necesita autorización del gerente para registrar otra cuenta gerente.", font_style="Caption", size_hint_y=None, height=dp(45), theme_text_color="Secondary")
        contenido.add_widget(campo_usuario); contenido.add_widget(campo_clave); contenido.add_widget(mensaje)
        dialog = None
        def comprobar(_boton):
            usuario, clave = campo_usuario.text.strip(), campo_clave.text
            if not usuario or not clave:
                mensaje.text = "Completa el usuario y la contraseña."; return
            cuenta = verificar_credenciales(usuario, clave)
            rol = ""
            if cuenta:
                if hasattr(cuenta, "keys"):
                    rol = cuenta["rol"] if "rol" in cuenta.keys() else ""
                elif isinstance(cuenta, dict):
                    rol = cuenta.get("rol", "")
                elif len(cuenta) > 8:
                    rol = cuenta[8]
            if cuenta and str(rol).strip().lower() == "gerente":
                _guardar_estado_registro_gerente(0, False)
                dialog.dismiss()
                MDApp.get_running_app().autorizacion_nuevo_gerente = True
                self.manager.current = "registro_gerente"
                return
            estado = _leer_estado_registro_gerente()
            intentos = min(5, estado["intentos"] + 1)
            bloqueado = intentos >= 5
            _guardar_estado_registro_gerente(intentos, bloqueado)
            if bloqueado:
                dialog.dismiss()
                # No abrir un segundo diálogo encima del primero: eso deja el fondo oscurecido.
                self._mostrar_clave_maestra_analista()
            else:
                mensaje.text = f"Credenciales incorrectas. Intento {intentos} de 5."
                mensaje.theme_text_color = "Custom"; mensaje.text_color = (0.8, 0.2, 0.2, 1)
                campo_clave.text = ""
        dialog = MDDialog(title="Autorización del gerente", type="custom", content_cls=contenido, buttons=[
            MDFlatButton(text="Cancelar", on_release=lambda _b: dialog.dismiss()),
            MDRaisedButton(text="Verificar", on_release=comprobar),
        ])
        dialog.open()

    def _mostrar_clave_maestra_analista(self):
        contenido = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10), size_hint_y=None, height=dp(125))
        campo = MDTextField(hint_text="Clave maestra del Analista de Sistemas", password=True, mode="rectangle")
        mensaje = MDLabel(text="Registro bloqueado. Solo el Analista de Sistemas puede autorizarlo.", font_style="Caption", size_hint_y=None, height=dp(40), theme_text_color="Secondary")
        contenido.add_widget(campo); contenido.add_widget(mensaje)
        dialog = None
        def comprobar(_boton):
            if not CLAVE_MAESTRA_ANALISTA or CLAVE_MAESTRA_ANALISTA == "CAMBIAR_POR_TU_CLAVE_MAESTRA":
                mensaje.text = "Configura CLAVE_MAESTRA_ANALISTA en main.py antes de usar esta opción."
                mensaje.theme_text_color = "Custom"; mensaje.text_color = (0.8, 0.2, 0.2, 1); return
            if secrets.compare_digest(campo.text, CLAVE_MAESTRA_ANALISTA):
                _guardar_estado_registro_gerente(0, False)
                dialog.dismiss()
                app = MDApp.get_running_app()
                app.autorizacion_nuevo_gerente = True
                dialogo_exito = mostrar_dialogo_simple(
                    "Acceso de registro permitido",
                    "Completa tus datos correspondientes.",
                )
                # La pantalla se abre únicamente cuando se cierra el mensaje de autorización.
                dialogo_exito.bind(
                    on_dismiss=lambda *_args: setattr(self.manager, "current", "registro_gerente")
                )
            else:
                mensaje.text = "Clave maestra incorrecta. El bloqueo continúa activo."
                mensaje.theme_text_color = "Custom"; mensaje.text_color = (0.8, 0.2, 0.2, 1); campo.text = ""
        dialog = MDDialog(title="Intervención del Analista de Sistemas", type="custom", content_cls=contenido, buttons=[
            MDFlatButton(text="Cancelar", on_release=lambda _b: dialog.dismiss()),
            MDRaisedButton(text="Autorizar", on_release=comprobar),
        ])
        dialog.open()

    def ir_a_registro_gerente(self):
        if hasattr(self.ids, "mensaje_error"):
            self.ids.mensaje_error.text = ""
        # El primer gerente se registra sin autorización previa.
        if not existe_gerente_registrado():
            self.manager.current = "registro_gerente"
            return
        estado = _leer_estado_registro_gerente()
        if estado["bloqueado"] or estado["intentos"] >= 5:
            _guardar_estado_registro_gerente(5, True)
            self._mostrar_clave_maestra_analista()
        else:
            self._mostrar_autorizacion_gerente()

    def ir_a_registro_empleado(self):
        if hasattr(self.ids, 'mensaje_error'):
            self.ids.mensaje_error.text = ""
        self.manager.current = "registro_empleado"


class PantallaRegistroGerente(MDScreen):
    def on_pre_enter(self, *args):
        app = MDApp.get_running_app()
        if existe_gerente_registrado() and not getattr(app, "autorizacion_nuevo_gerente", False):
            mostrar_dialogo_simple("Registro protegido", "Para registrar otro gerente, vuelve al inicio y completa la autorización.")
            self.manager.current = "inicio_sesion"
            return
        # La autorización se conserva durante el formulario y se consume al guardar.

    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def guardar_gerente(self):
        app = MDApp.get_running_app()
        if existe_gerente_registrado() and not getattr(app, "autorizacion_nuevo_gerente", False):
            mostrar_dialogo_simple("Registro protegido", "Se requiere autorización del gerente o del Analista de Sistemas.")
            self.manager.current = "inicio_sesion"
            return

        campos = [
            self.ids.nombre_field,
            self.ids.apellido_field,
            self.ids.usuario_field,
            self.ids.password_field,
            self.ids.confirm_password_field,
            self.ids.email_field,
            self.ids.telefono_field
        ]

        for campo in campos:
            campo.error = False
            campo.helper_text = ""

        if hasattr(self.ids, 'mensaje_error'):
            self.ids.mensaje_error.text = ""

        hay_vacios = False
        for campo in campos:
            if not campo.text.strip():
                campo.error = True
                campo.helper_text = "Este campo es obligatorio"
                hay_vacios = True

        if hay_vacios:
            return

        usuario = self.ids.usuario_field.text.strip()
        password = self.ids.password_field.text.strip()

        if password != self.ids.confirm_password_field.text.strip():
            self.ids.confirm_password_field.error = True
            self.ids.confirm_password_field.helper_text = "Las contraseñas no coinciden"
            return

        exito, msg = registrar_usuario(
            self.ids.nombre_field.text.strip(),
            self.ids.apellido_field.text.strip(),
            usuario,
            password,
            self.ids.email_field.text.strip(),
            self.ids.telefono_field.text.strip(),
            cargo="Gerente General",
            rol="gerente"
        )

        if exito:
            app.autorizacion_nuevo_gerente = False
            usuario_db = verificar_credenciales(usuario, password)
            if usuario_db:
                app = MDApp.get_running_app()
                if hasattr(usuario_db, "keys"):
                    app.usuario_activo = {key: usuario_db[key] for key in usuario_db.keys()}
                else:
                    app.usuario_activo = dict(usuario_db)
                self.limpiar_campos()
                self.manager.current = "panel_gerente"
            else:
                self.limpiar_campos()
                self.manager.current = "inicio_sesion"
        else:
            if hasattr(self.ids, 'mensaje_error'):
                self.ids.mensaje_error.text = msg

    def limpiar_campos(self):
        campos = [
            self.ids.nombre_field,
            self.ids.apellido_field,
            self.ids.usuario_field,
            self.ids.password_field,
            self.ids.confirm_password_field,
            self.ids.email_field,
            self.ids.telefono_field
        ]
        for campo in campos:
            campo.text = ""
            campo.error = False
            campo.helper_text = ""

        if hasattr(self.ids, 'mensaje_error'):
            self.ids.mensaje_error.text = ""

    def ir_a_login(self):
        app = MDApp.get_running_app()
        app.autorizacion_nuevo_gerente = False
        self.limpiar_campos()
        self.manager.current = "inicio_sesion"


class PantallaRegistroEmpleado(MDScreen):
    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def guardar_empleado(self):
        campos = [
            self.ids.nombre_field,
            self.ids.apellido_field,
            self.ids.usuario_field,
            self.ids.password_field,
            self.ids.confirm_password_field,
            self.ids.email_field,
            self.ids.telefono_field,
            self.ids.cargo_field
        ]

        for campo in campos:
            campo.error = False
            campo.helper_text = ""

        if hasattr(self.ids, 'mensaje_error'):
            self.ids.mensaje_error.text = ""

        hay_vacios = False
        for campo in campos:
            if not campo.text.strip():
                campo.error = True
                campo.helper_text = "Este campo es obligatorio"
                hay_vacios = True

        if hay_vacios:
            return

        usuario = self.ids.usuario_field.text.strip()
        password = self.ids.password_field.text.strip()

        if password != self.ids.confirm_password_field.text.strip():
            self.ids.confirm_password_field.error = True
            self.ids.confirm_password_field.helper_text = "Las contraseñas no coinciden"
            return

        exito, msg = registrar_usuario(
            self.ids.nombre_field.text.strip(),
            self.ids.apellido_field.text.strip(),
            usuario,
            password,
            self.ids.email_field.text.strip(),
            self.ids.telefono_field.text.strip(),
            cargo=self.ids.cargo_field.text.strip(),
            rol="empleado"
        )

        if exito:
            usuario_db = verificar_credenciales(usuario, password)
            if usuario_db:
                app = MDApp.get_running_app()
                if hasattr(usuario_db, "keys"):
                    app.usuario_activo = {key: usuario_db[key] for key in usuario_db.keys()}
                else:
                    app.usuario_activo = dict(usuario_db)
                self.limpiar_campos()
                self.manager.current = "panel_empleado"
            else:
                self.limpiar_campos()
                self.manager.current = "inicio_sesion"
        else:
            if hasattr(self.ids, 'mensaje_error'):
                self.ids.mensaje_error.text = msg

    def limpiar_campos(self):
        campos = [
            self.ids.nombre_field,
            self.ids.apellido_field,
            self.ids.usuario_field,
            self.ids.password_field,
            self.ids.confirm_password_field,
            self.ids.email_field,
            self.ids.telefono_field,
            self.ids.cargo_field
        ]
        for campo in campos:
            campo.text = ""
            campo.error = False
            campo.helper_text = ""

        if hasattr(self.ids, 'mensaje_error'):
            self.ids.mensaje_error.text = ""

    def ir_a_login(self):
        self.limpiar_campos()
        self.manager.current = "inicio_sesion"


class PantallaPanelEmpleado(MDScreen):
    nombre_empleado = StringProperty("Empleado")
    avatar_path = StringProperty("")
    drawer_open = BooleanProperty(True)
    drawer_width = NumericProperty(dp(250))
    fecha_actual = StringProperty("")
    hora_actual = StringProperty("")
    resumen_movimientos = StringProperty("Todavía no hay movimientos registrados.")
    resumen_categorias = StringProperty("No hay categorías cargadas.")
    productos_lacteos = NumericProperty(0)
    productos_carnes = NumericProperty(0)
    productos_granos = NumericProperty(0)
    productos_enlatados = NumericProperty(0)
    productos_bebidas = NumericProperty(0)
    productos_pastas = NumericProperty(0)
    productos_frutas = NumericProperty(0)
    productos_general = NumericProperty(0)
    total_productos = NumericProperty(0)
    stock_bajo = NumericProperty(0)
    por_vencer = NumericProperty(0)
    vencidos = NumericProperty(0)
    notificaciones_vencidos = NumericProperty(0)
    _evento_reloj = None

    def on_pre_enter(self, *args):
        app = MDApp.get_running_app()
        if app.usuario_activo:
            nombre_completo = f"{app.usuario_activo.get('nombre', '')} {app.usuario_activo.get('apellido', '')}".strip()
            self.nombre_empleado = nombre_completo if nombre_completo else "Empleado"
            self.avatar_path = ruta_avatar(app.usuario_activo.get("usuario"))
        
        self.actualizar_fecha_hora()
        if self._evento_reloj is None:
            from kivy.clock import Clock

            self._evento_reloj = Clock.schedule_interval(self.actualizar_fecha_hora, 1)
        self.actualizar_metricas()
        self.actualizar_resumenes()
        # Aplicar el tema después de que KV y los widgets dinámicos estén visibles.
        # Esto evita que el texto del panel empleado quede blanco sobre superficies claras.
        Clock.schedule_once(
            lambda _dt: aplicar_contraste_vistas(MDApp.get_running_app().theme_cls.theme_style),
            0.15,
        )

    def on_leave(self, *args):
        if self._evento_reloj is not None:
            self._evento_reloj.cancel()
            self._evento_reloj = None

    def actualizar_fecha_hora(self, *_args):
        ahora = datetime.now()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        self.fecha_actual = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"
        self.hora_actual = ahora.strftime("%I:%M:%S %p")

    def abrir_calendario(self):
        ahora = datetime.now()
        date_dialog = MDDatePicker(
            year=ahora.year,
            month=ahora.month,
            day=ahora.day
        )
        date_dialog.bind(on_save=self.al_seleccionar_fecha)
        date_dialog.open()

    def al_seleccionar_fecha(self, instance, value, date_range):
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        self.fecha_actual = f"{value.day} de {meses[value.month - 1]} de {value.year}"

    def registrar_entrada(self):
        self._abrir_dialogo_movimiento("entrada")

    def registrar_salida(self):
        self._abrir_dialogo_movimiento("salida")

    def agregar_producto(self, datos_iniciales=None):
        datos_iniciales = datos_iniciales or {}
        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
            size_hint_y=None,
            height=dp(7 * 48 + 7 * 10 + 66),
        )
        imagen_path = {"value": ""}
        campos = {
            "codigo": crear_campo_formulario("Código de barras"),
            "nombre": crear_campo_formulario("Nombre del producto"),
            "cantidad": crear_campo_formulario("Cantidad", input_filter="int"),
            "fecha": crear_campo_formulario("Fecha de vencimiento (YYYY-MM-DD)"),
            "ubicacion": crear_campo_formulario("Ubicación (Heladera, Alacena, Freezer o Bodega)"),
        }
        for campo in campos.values():
            layout.add_widget(campo)

        categoria_label = MDLabel(text="Categoría", font_style="Caption", theme_text_color="Secondary", size_hint_y=None, height=dp(20))
        categoria_spinner = Spinner(
            text="Granos",
            values=sorted({"Lácteos", "Carnes", "Enlatados", "Bebidas", "Granos", "Pastas", "Otros", datos_iniciales.get("categoria", "Otros")}),
            size_hint_y=None,
            height=dp(42),
            background_color=(0.94, 0.97, 0.96, 1),
            color=(0.08, 0.12, 0.12, 1),
        )
        layout.add_widget(categoria_label)
        layout.add_widget(categoria_spinner)
        conservacion_spinner = Spinner(
            text="Refrigerado",
            values=["Refrigerado", "Congelado"],
            size_hint_y=None,
            height=dp(42),
        )
        layout.add_widget(MDLabel(text="Conservación", font_style="Caption", size_hint_y=None, height=dp(20)))
        layout.add_widget(conservacion_spinner)

        campos["codigo"].text = str(datos_iniciales.get("codigo", ""))
        campos["nombre"].text = str(datos_iniciales.get("nombre", ""))
        categoria_spinner.text = str(datos_iniciales.get("categoria", "Granos"))

        foto_estado = MDLabel(text="Foto del producto: sin tomar", font_style="Caption")

        def tomar_foto(instance):
            foto_estado.text = "Abriendo cámara..."

            def foto_lista(ruta, error=None):
                if ruta:
                    imagen_path["value"] = ruta
                    foto_estado.text = "Foto capturada y lista para guardar"

                    def completar_fecha(fecha, mensaje=None):
                        if fecha:
                            campos["fecha"].text = fecha
                            foto_estado.text = f"Foto guardada; vencimiento sugerido: {fecha}. Confirma la fecha."
                        elif mensaje:
                            foto_estado.text = f"Foto guardada; {mensaje}"

                    leer_fecha_en_imagen(ruta, completar_fecha)
                else:
                    foto_estado.text = "No se guardó la foto"
                    if error:
                        mostrar_dialogo_simple("Error de cámara", error)

            iniciar_captura_foto_producto(foto_lista)

        layout.add_widget(MDRaisedButton(
            text="Tomar foto del producto",
            icon="camera",
            size_hint_y=None,
            height=dp(42),
            on_release=tomar_foto,
        ))
        layout.add_widget(foto_estado)

        def guardar(instance):
            try:
                codigo = campos["codigo"].text.strip()
                nombre = campos["nombre"].text.strip()
                categoria = categoria_spinner.text.strip() or "Otros"
                cantidad = int(campos["cantidad"].text.strip() or 0)
                fecha_base = campos["fecha"].text.strip()
                if fecha_base:
                    date.fromisoformat(fecha_base)
                congelado = conservacion_spinner.text == "Congelado"
                if not codigo or not nombre:
                    mostrar_dialogo_simple("Datos incompletos", "Código y nombre del producto son obligatorios.")
                    return
                if cantidad <= 0 or (not fecha_base and not congelado):
                    mostrar_dialogo_simple("Datos incompletos", "Indica una cantidad mayor que cero y una fecha de vencimiento (salvo que el producto sea congelado).")
                    return
                fecha_congelacion = date.today().isoformat() if congelado else None
                fecha = fecha_base or None
                if congelado:
                    base_calculo = fecha or date.today().isoformat()
                    fecha = ControladorInventario.calcular_vencimiento_congelado(base_calculo, categoria)
                ubicacion = campos["ubicacion"].text.strip() or ("Freezer" if congelado else "Heladera")
                GestorBD().ejecutar_comando(
                    "INSERT INTO productos (codigo_barras, nombre, categoria, cantidad_stock, fecha_vencimiento, "
                    "pasillo, imagen, congelado, fecha_congelacion, fecha_ingreso) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (codigo, nombre, categoria, cantidad, fecha, ubicacion, imagen_path["value"], int(congelado), fecha_congelacion, date.today().isoformat()),
                )
                self.actualizar_metricas()
                self.actualizar_resumenes()
                extra = f" Vencimiento extendido hasta {fecha}." if congelado else ""
                mostrar_dialogo_simple("Producto agregado", f"{nombre} fue agregado correctamente en la categoría {categoria}, ubicación {ubicacion}.{extra}")
                dialog.dismiss()
            except Exception as exc:
                mostrar_dialogo_simple("Error", f"No se pudo guardar el producto: {exc}")

        dialog = MDDialog(
            title="Registrar producto",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(text="Guardar", on_release=guardar),
            ],
        )
        dialog.open()

    def _abrir_dialogo_movimiento(self, tipo):
        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
            size_hint_y=None,
            height=dp(2 * 48 + 10 + 24),
        )
        codigo_field = crear_campo_formulario("Código de barras o nombre del producto")
        cantidad_field = crear_campo_formulario("Cantidad", input_filter="int")
        layout.add_widget(codigo_field)
        layout.add_widget(cantidad_field)

        def guardar(instance):
            try:
                codigo = codigo_field.text.strip()
                cantidad = int(cantidad_field.text.strip() or 0)
                if not codigo or cantidad <= 0:
                    mostrar_dialogo_simple("Validación", "Debes indicar un producto y una cantidad válida.")
                    return

                gestor = GestorBD()
                producto = gestor.ejecutar_consulta(
                    "SELECT id_producto, nombre, cantidad_stock FROM productos WHERE codigo_barras = ? OR nombre LIKE ? LIMIT 1",
                    (codigo, f"%{codigo}%"),
                )

                if not producto:
                    mostrar_dialogo_simple("Producto no encontrado", "El producto no existe en el inventario.")
                    dialog.dismiss()
                    return

                id_producto, nombre, stock_actual = producto[0]
                stock_actual = int(stock_actual or 0)
                if tipo == "salida" and stock_actual < cantidad:
                    mostrar_dialogo_simple("Stock insuficiente", f"No hay suficiente stock para {nombre}.")
                    dialog.dismiss()
                    return

                nuevo_stock = stock_actual + cantidad if tipo == "entrada" else stock_actual - cantidad
                app = MDApp.get_running_app()
                id_usuario = (app.usuario_activo or {}).get("id", 1)
                exito, mensaje = gestor.registrar_movimiento(
                    id_producto,
                    id_usuario,
                    tipo,
                    cantidad,
                    f"Registro manual desde empleado: {tipo}",
                )
                if not exito:
                    mostrar_dialogo_simple("Error", mensaje)
                    return
                self.actualizar_metricas()
                self.actualizar_resumenes()
                mostrar_dialogo_simple("Movimiento registrado", f"{tipo.title()} de {cantidad} unidad(es) de {nombre}. Stock final: {nuevo_stock}.")
                dialog.dismiss()
            except Exception as exc:
                mostrar_dialogo_simple("Error", f"No se pudo registrar el movimiento: {exc}")
                dialog.dismiss()

        dialog = MDDialog(
            title=f"Registrar {tipo}",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(text="Guardar", on_release=guardar),
            ],
        )
        dialog.open()

    def mostrar_historial(self):
        mostrar_movimientos_visual("Historial de movimientos")

    def ver_alertas(self):
        """Muestra las alertas del inventario desde el panel del empleado."""
        gestor = GestorBD()
        gestor.sincronizar_alertas(30)
        alertas = gestor.listar_alertas()
        contenido = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10), size_hint_y=None)
        contenido.bind(minimum_height=contenido.setter("height"))

        if not alertas:
            contenido.add_widget(MDLabel(
                text="No hay productos vencidos, próximos a vencer ni con stock bajo.",
                size_hint_y=None,
                height=dp(48),
            ))

        for id_alerta, _id_producto, nombre, tipo, mensaje, fecha, leido in alertas:
            fila = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(64))
            fila.add_widget(MDLabel(
                text=f"{tipo} · {nombre}\n{mensaje} · {fecha}",
                valign="middle",
            ))
            if not leido:
                fila.add_widget(MDFlatButton(
                    text="Marcar leída",
                    size_hint_x=None,
                    width=dp(112),
                    on_release=lambda _button, alerta_id=id_alerta: (
                        gestor.marcar_alerta_leida(alerta_id),
                        dialog.dismiss(),
                        self.actualizar_metricas(),
                        self.ver_alertas(),
                    ),
                ))
            contenido.add_widget(fila)

        scroll = ScrollView(size_hint_y=None, height=min(dp(430), dp(64 * max(len(alertas), 1))))
        scroll.add_widget(contenido)
        dialog = MDDialog(
            title="Notificaciones del inventario",
            type="custom",
            content_cls=scroll,
            buttons=[MDFlatButton(text="Cerrar", on_release=lambda _button: dialog.dismiss())],
        )
        dialog.open()

    def actualizar_resumenes(self):
        gestor = GestorBD()
        movimientos = gestor.listar_movimientos(5)
        if movimientos:
            lineas_movimientos = []
            for row in movimientos:
                tipo = str(row[3]).strip().lower()
                color = "2E9B50" if tipo == "entrada" else "E53935" if tipo == "salida" else "607D8B"
                fecha = str(row[5])
                lineas_movimientos.append(
                    f"[color={color}]{fecha}[/color] | "
                    f"[color={color}]{tipo.title()}[/color] | {row[1]} x{row[4]}"
                )
            self.resumen_movimientos = "\n".join(lineas_movimientos)
        else:
            self.resumen_movimientos = "Todavía no hay movimientos registrados."

        categorias = gestor.listar_productos_por_categoria()
        self.productos_lacteos = 0
        self.productos_carnes = 0
        self.productos_granos = 0
        self.productos_enlatados = 0
        self.productos_bebidas = 0
        self.productos_pastas = 0
        self.productos_frutas = 0
        self.productos_general = 0
        for categoria, total, _ in categorias:
            categoria_normalizada = str(categoria or "").strip().lower()
            if categoria_normalizada in ("lacteos", "lácteos"):
                self.productos_lacteos = total
            elif categoria_normalizada == "carnes":
                self.productos_carnes = total
            elif categoria_normalizada == "granos":
                self.productos_granos = total
            elif categoria_normalizada in ("enlatados", "enlatado"):
                self.productos_enlatados = total
            elif categoria_normalizada == "bebidas":
                self.productos_bebidas = total
            elif categoria_normalizada == "pastas":
                self.productos_pastas = total
            elif categoria_normalizada == "frutas":
                self.productos_frutas = total
            elif categoria_normalizada == "general":
                self.productos_general = total
        if categorias:
            self.resumen_categorias = "   ".join(f"{categoria or 'Sin categoría'}: {total}" for categoria, total, _ in categorias[:5])
        else:
            self.resumen_categorias = "No hay categorías cargadas."

    def actualizar_metricas(self):
        try:
            metricas = obtener_metricas_dashboard()
            self.total_productos = metricas.get("total_productos", 0)
            self.stock_bajo = metricas.get("stock_bajo", 0)
            self.por_vencer = metricas.get("por_vencer", 0)
            self.vencidos = metricas.get("vencidos", 0)
            gestor = GestorBD()
            gestor.sincronizar_alertas(30)
            alertas_pendientes = gestor.listar_alertas(1000)
            self.notificaciones_vencidos = sum(1 for alerta in alertas_pendientes if not bool(alerta[6]))
        except Exception as e:
            print(f"Error cargando métricas en panel empleado: {e}")

    def toggle_nav_drawer(self):
        self.drawer_open = not self.drawer_open
        Animation.cancel_all(self, "drawer_width")
        Animation(drawer_width=dp(260) if self.drawer_open else 0, duration=0.2).start(self)

    def ir_a_escaner(self):
        if "escaner" in self.manager.screen_names:
            pantalla_escaner = self.manager.get_screen("escaner")
            pantalla_escaner.pantalla_origen = "panel_empleado"
            self.manager.current = "escaner"

    def buscar_producto(self):
        mostrar_inventario_visual("Buscar producto", permitir_busqueda=True)

    def ver_inventario(self):
        self.buscar_producto()

    def mostrar_cuenta(self):
        usuario = MDApp.get_running_app().usuario_activo or {}
        avatar = self.avatar_path or ruta_avatar(usuario.get("usuario"))
        layout = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(14), size_hint_y=None, height=dp(360))

        imagen_wrap = BoxLayout(size_hint=(None, None), size=(dp(120), dp(120)), pos_hint={"center_x": 0.5})
        imagen_wrap.add_widget(
            FitImage(
                source=avatar or "",
                size_hint=(1, 1),
                allow_stretch=True,
                keep_ratio=True,
                radius=[dp(60)],
                opacity=1 if avatar else 0,
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            )
        )
        if not avatar:
            imagen_wrap.add_widget(
                MDLabel(
                    text="👤",
                    halign="center",
                    valign="middle",
                    font_style="H2",
                    theme_text_color="Custom",
                    text_color=(0.2, 0.6, 0.4, 1),
                    size_hint=(1, 1),
                )
            )

        info = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(150))
        info.add_widget(MDLabel(text=f"{usuario.get('nombre', '')} {usuario.get('apellido', '')}".strip() or "Sin nombre", font_style="H6", bold=True, halign="center"))
        info.add_widget(MDLabel(text=f"Usuario: {usuario.get('usuario', '')}", font_style="Body2", theme_text_color="Secondary"))
        info.add_widget(MDLabel(text=f"Cargo: {usuario.get('cargo', 'Empleado')}", font_style="Body2", theme_text_color="Secondary"))
        info.add_widget(MDLabel(text=f"Correo: {usuario.get('email', '')}", font_style="Body2", theme_text_color="Secondary"))
        info.add_widget(MDLabel(text=f"Teléfono: {usuario.get('telefono', '')}", font_style="Body2", theme_text_color="Secondary"))

        layout.add_widget(imagen_wrap)
        layout.add_widget(info)
        dialog = MDDialog(
            title="Mi cuenta",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cambiar imagen", on_release=lambda instance: (dialog.dismiss(), self.seleccionar_imagen())),
                MDFlatButton(text="Configuración", on_release=lambda instance: (dialog.dismiss(), self.abrir_configuracion())),
                MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss()),
            ],
        )
        dialog.open()

    def abrir_configuracion(self):
        app = MDApp.get_running_app()
        usuario_actual = app.usuario_activo or {}

        layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12), size_hint_y=None, height=dp(320))
        campo_nombre = crear_campo_formulario("Nombre")
        campo_nombre.text = str(usuario_actual.get("nombre", ""))
        campo_apellido = crear_campo_formulario("Apellido")
        campo_apellido.text = str(usuario_actual.get("apellido", ""))
        campo_telefono = crear_campo_formulario("Teléfono")
        campo_telefono.text = str(usuario_actual.get("telefono", ""))
        campo_email = crear_campo_formulario("Correo Electrónico")
        campo_email.text = str(usuario_actual.get("email", ""))
        campos_configuracion = (campo_nombre, campo_apellido, campo_telefono, campo_email)

        def aplicar_colores_configuracion(tema):
            es_oscuro = tema == "Dark"
            color_texto = (1, 1, 1, 1) if es_oscuro else (0.08, 0.08, 0.08, 1)
            color_pista = (0.72, 0.75, 0.78, 1) if es_oscuro else (0.38, 0.38, 0.38, 1)
            color_linea = (0.55, 0.75, 0.62, 1) if es_oscuro else (0.25, 0.45, 0.32, 1)
            for campo in campos_configuracion:
                campo.text_color_normal = color_texto
                campo.text_color_focus = color_texto
                campo.hint_text_color_normal = color_pista
                campo.hint_text_color_focus = color_pista
                campo.line_color_normal = color_pista
                campo.line_color_focus = color_linea
            etiqueta_tema.text_color = color_texto

        layout.add_widget(campo_nombre)
        layout.add_widget(campo_apellido)
        layout.add_widget(campo_telefono)
        layout.add_widget(campo_email)

        tema_box = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(40))
        etiqueta_tema = MDLabel(
            text="Tema de la aplicación:",
            font_style="Subtitle2",
            theme_text_color="Custom",
        )
        tema_box.add_widget(etiqueta_tema)
        btn_claro = MDRaisedButton(text="Claro", md_bg_color=(0.1, 0.6, 0.3, 1))
        btn_oscuro = MDRaisedButton(text="Oscuro", md_bg_color=(0.2, 0.2, 0.25, 1))

        def cambiar_tema(tema):
            app.theme_cls.theme_style = tema
            aplicar_colores_configuracion(tema)
            Clock.schedule_once(lambda _dt: aplicar_contraste_vistas(tema), 0)
            mostrar_dialogo_simple("Tema", f"Tema cambiado a {tema}.")

        btn_claro.bind(on_release=lambda x: cambiar_tema("Light"))
        btn_oscuro.bind(on_release=lambda x: cambiar_tema("Dark"))
        tema_box.add_widget(btn_claro)
        tema_box.add_widget(btn_oscuro)
        layout.add_widget(tema_box)

        def guardar_cambios(instance):
            nom = campo_nombre.text.strip()
            ape = campo_apellido.text.strip()
            tel = campo_telefono.text.strip()
            ema = campo_email.text.strip()
            try:
                GestorBD().ejecutar_comando(
                    "UPDATE empleados SET nombre=?, apellido=?, telefono=?, email=? WHERE usuario=?",
                    (nom, ape, tel, ema, usuario_actual.get("usuario")),
                )
                app.usuario_activo["nombre"] = nom
                app.usuario_activo["apellido"] = ape
                app.usuario_activo["telefono"] = tel
                app.usuario_activo["email"] = ema
                self.nombre_empleado = f"{nom} {ape}".strip()
                dialog.dismiss()
                mostrar_dialogo_simple("Configuración guardada", "Datos del empleado y tema actualizados con éxito.")
            except Exception as e:
                mostrar_dialogo_simple("Error", f"No se pudo guardar la configuración: {e}")

        dialog = MDDialog(
            title="Configuración de Empleado (Perfil y Tema)",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(text="Guardar cambios", on_release=guardar_cambios),
            ],
        )
        aplicar_colores_configuracion(app.theme_cls.theme_style)
        dialog.open()

    def seleccionar_imagen(self):
        usuario = (MDApp.get_running_app().usuario_activo or {}).get("usuario", "empleado")
        selector = FileChooserListView(
            path=os.path.expanduser("~"),
            filters=["*.png", "*.jpg", "*.jpeg", "*.webp"],
            size_hint_y=None,
            height=dp(330),
        )
        aplicar_color_texto_selector(selector)
        layout = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(370))
        layout.add_widget(selector)

        def guardar_seleccion(instance):
            if not selector.selection:
                mostrar_dialogo_simple("Imagen", "Selecciona una imagen primero.")
                return
            try:
                self.avatar_path = guardar_avatar(usuario, selector.selection[0])
                dialog.dismiss()
                mostrar_dialogo_simple("Imagen actualizada", "La imagen del empleado se guardó correctamente.")
            except Exception as exc:
                mostrar_dialogo_simple("Error de imagen", str(exc))

        dialog = MDDialog(
            title="Seleccionar imagen del empleado",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(text="Usar imagen", on_release=guardar_seleccion),
            ],
        )
        dialog.open()

    def cerrar_sesion(self):
        MDApp.get_running_app().usuario_activo = {}
        self.manager.current = "inicio_sesion"


class PantallaPanelGerente(MDScreen):
    nombre_gerente = StringProperty("Gerente")
    avatar_path = StringProperty("")
    drawer_open = BooleanProperty(True)
    drawer_width = NumericProperty(dp(250))
    fecha_actual = StringProperty("")
    hora_actual = StringProperty("")
    total_productos = NumericProperty(0)
    stock_bajo = NumericProperty(0)
    por_vencer = NumericProperty(0)
    vencidos = NumericProperty(0)
    notificaciones_vencidos = NumericProperty(0)
    resumen_vencimiento = StringProperty("No hay productos por vencer en los próximos 7 días.")
    resumen_alertas = StringProperty("No hay alertas críticas.")
    resumen_movimientos = StringProperty("Todavía no hay movimientos registrados.")
    resumen_categorias = StringProperty("No hay categorías cargadas.")
    _evento_reloj = None

    def on_pre_enter(self, *args):
        app = MDApp.get_running_app()
        if app.usuario_activo:
            nombre_completo = f"{app.usuario_activo.get('nombre', '')} {app.usuario_activo.get('apellido', '')}".strip()
            self.nombre_gerente = nombre_completo if nombre_completo else "Gerente"
            self.avatar_path = ruta_avatar(app.usuario_activo.get("usuario"))

        self.actualizar_fecha_hora()
        if self._evento_reloj is None:
            from kivy.clock import Clock

            self._evento_reloj = Clock.schedule_interval(self.actualizar_fecha_hora, 1)

        self.actualizar_metricas()
        self.actualizar_resumenes()
        # Reaplicar también en gerente para mantener el contraste consistente.
        Clock.schedule_once(
            lambda _dt: aplicar_contraste_vistas(MDApp.get_running_app().theme_cls.theme_style),
            0.15,
        )

    def on_leave(self, *args):
        if self._evento_reloj is not None:
            self._evento_reloj.cancel()
            self._evento_reloj = None

    def actualizar_fecha_hora(self, *_args):
        ahora = datetime.now()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        self.fecha_actual = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"
        self.hora_actual = ahora.strftime("%I:%M:%S %p")

    def actualizar_metricas(self):
        try:
            metricas = obtener_metricas_dashboard()
            self.total_productos = metricas.get("total_productos", 0)
            self.stock_bajo = metricas.get("stock_bajo", 0)
            self.por_vencer = metricas.get("por_vencer", 0)
            self.vencidos = metricas.get("vencidos", 0)
            gestor = GestorBD()
            gestor.sincronizar_alertas(30)
            alertas_pendientes = gestor.listar_alertas(1000)
            self.notificaciones_vencidos = sum(1 for alerta in alertas_pendientes if not bool(alerta[6]))
        except Exception as e:
            print(f"Error cargando métricas en panel gerente: {e}")

    def actualizar_resumenes(self):
        gestor = GestorBD()
        alertas = gestor.obtener_notificaciones_gerente(7)

        vencimientos = [
            detalle for tipo, detalle, _, _, _ in alertas if tipo == "Vencimiento"
        ]
        criticas = [
            detalle for tipo, detalle, _, _, _ in alertas if tipo == "Stock bajo"
        ]
        stock_reducido = [
            detalle for tipo, detalle, _, _, _ in alertas if tipo == "Stock reducido"
        ]
        resumen_criticas = criticas + [f"Stock reducido: {detalle}" for detalle in stock_reducido]

        if vencimientos:
            self.resumen_vencimiento = "\n".join(vencimientos[:5])
        else:
            self.resumen_vencimiento = "No hay productos por vencer en los próximos 7 días."

        if resumen_criticas:
            self.resumen_alertas = "\n".join(resumen_criticas[:5])
        else:
            self.resumen_alertas = "No hay alertas críticas."

        movimientos = gestor.listar_movimientos(5)
        if movimientos:
            lineas_movimientos = []
            for row in movimientos:
                tipo = str(row[3]).strip().lower()
                color = "2E9B50" if tipo == "entrada" else "E53935" if tipo == "salida" else "607D8B"
                fecha = str(row[5])
                lineas_movimientos.append(
                    f"[color={color}]{fecha}[/color] | Sector {row[8]} | "
                    f"[color={color}]{tipo.title()}[/color] {row[1]} | {row[4]} u. | Código: {row[7] or '-'}"
                )
            self.resumen_movimientos = "\n".join(lineas_movimientos)
        else:
            self.resumen_movimientos = "Todavía no hay movimientos registrados."

        categorias = gestor.listar_productos_por_categoria()
        if categorias:
            self.resumen_categorias = "   ".join(f"{categoria or 'Sin categoría'}: {total}" for categoria, total, _ in categorias[:5])
        else:
            self.resumen_categorias = "No hay categorías cargadas."

    def toggle_nav_drawer(self):
        self.drawer_open = not self.drawer_open
        Animation.cancel_all(self, "drawer_width")
        Animation(drawer_width=dp(250) if self.drawer_open else 0, duration=0.2).start(self)

    def ver_inventario(self):
        mostrar_inventario_visual("Buscar producto", permitir_busqueda=True, permitir_aviso=True)

    def gestionar_productos_vencidos(self):
        gestor = GestorBD()
        productos = gestor.listar_productos_vencidos()
        contenido = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(300))

        def confirmar_eliminacion(id_producto=None):
            es_todo = id_producto is None
            cantidad = len(productos) if es_todo else 1
            mensaje = (
                f"Se pondrá a cero el stock de {cantidad} productos vencidos. Los productos y sus códigos se conservarán."
                if es_todo
                else "Se pondrá a cero el stock vencido. El producto, su código y su historial se conservarán."
            )

            def eliminar(instance):
                try:
                    app = MDApp.get_running_app()
                    id_usuario = (app.usuario_activo or {}).get("id", 1)
                    retirados = gestor.retirar_stock_vencido(id_producto, id_usuario)
                    confirmacion.dismiss()
                    dialog.dismiss()
                    self.actualizar_metricas()
                    self.actualizar_resumenes()
                    mostrar_dialogo_simple("Stock retirado", f"Se puso a cero el stock de {retirados} productos vencidos.")
                except Exception as exc:
                    confirmacion.dismiss()
                    mostrar_dialogo_simple("Error", f"No se pudieron eliminar los productos: {exc}")

            confirmacion = MDDialog(
                title="Confirmar eliminación",
                text=mensaje,
                buttons=[
                    MDFlatButton(text="Cancelar", on_release=lambda instance: confirmacion.dismiss()),
                    MDRaisedButton(text="Eliminar", on_release=eliminar, md_bg_color=(0.8, 0.1, 0.1, 1)),
                ],
            )
            confirmacion.open()

        if productos:
            filas = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
            filas.bind(minimum_height=filas.setter("height"))
            for id_producto, nombre, stock, fecha in productos:
                fila = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
                fila.add_widget(
                    MDLabel(
                        text=f"{nombre} | stock: {stock} | venció: {fecha}",
                        font_style="Caption",
                        size_hint_x=0.78,
                    )
                )
                fila.add_widget(
                    MDFlatButton(
                        text="Retirar stock",
                        size_hint_x=0.22,
                        on_release=lambda instance, product_id=id_producto: confirmar_eliminacion(product_id),
                    )
                )
                filas.add_widget(fila)
            scroll = ScrollView(size_hint=(1, 1))
            scroll.add_widget(filas)
            contenido.add_widget(scroll)
            botones = [
                MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(
                    text=f"Retirar todo el stock ({len(productos)})",
                    md_bg_color=(0.8, 0.1, 0.1, 1),
                    on_release=lambda instance: confirmar_eliminacion(),
                ),
            ]
        else:
            contenido.add_widget(MDLabel(text="No hay productos vencidos.", halign="center"))
            botones = [MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss())]

        dialog = MDDialog(
            title="Productos vencidos",
            type="custom",
            content_cls=contenido,
            buttons=botones,
        )
        dialog.open()

    def ver_alertas(self):
        gestor = GestorBD()
        gestor.sincronizar_alertas(30)
        alertas = gestor.listar_alertas()
        contenido = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10), size_hint_y=None)
        contenido.bind(minimum_height=contenido.setter("height"))

        if not alertas:
            contenido.add_widget(MDLabel(
                text="No hay productos vencidos, próximos a vencer ni con stock bajo.",
                size_hint_y=None,
                height=dp(48),
            ))
        for id_alerta, _id_producto, nombre, tipo, mensaje, fecha, leido in alertas:
            fila = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(64))
            texto = f"{tipo} · {nombre}\n{mensaje} · {fecha}"
            fila.add_widget(MDLabel(text=texto, valign="middle"))
            if not leido:
                fila.add_widget(MDFlatButton(
                    text="Marcar leída",
                    size_hint_x=None,
                    width=dp(112),
                    on_release=lambda _button, alerta_id=id_alerta: (
                        gestor.marcar_alerta_leida(alerta_id), dialog.dismiss(), self.ver_alertas()
                    ),
                ))
            contenido.add_widget(fila)

        scroll = ScrollView(size_hint_y=None, height=min(dp(430), dp(64 * max(len(alertas), 1))))
        scroll.add_widget(contenido)

        dialog = MDDialog(
            title="Alertas",
            type="custom",
            content_cls=scroll,
            buttons=[MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss())],
        )
        dialog.open()

    def ver_movimientos(self):
        mostrar_movimientos_visual("Movimientos recientes")

    def ver_categorias(self):
        mostrar_dialogo_simple("Resumen del inventario", self.resumen_categorias)

    def mostrar_cuenta(self):
        usuario = MDApp.get_running_app().usuario_activo or {}
        avatar = self.avatar_path or ruta_avatar(usuario.get("usuario"))
        layout = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(14), size_hint_y=None, height=dp(360))

        imagen_wrap = BoxLayout(size_hint=(None, None), size=(dp(120), dp(120)), pos_hint={"center_x": 0.5})
        imagen_wrap.add_widget(
            FitImage(
                source=avatar or "",
                size_hint=(1, 1),
                allow_stretch=True,
                keep_ratio=True,
                radius=[dp(60)],
                opacity=1 if avatar else 0,
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            )
        )
        if not avatar:
            imagen_wrap.add_widget(
                MDLabel(
                    text="👤",
                    halign="center",
                    valign="middle",
                    font_style="H2",
                    theme_text_color="Custom",
                    text_color=(0.2, 0.6, 0.4, 1),
                    size_hint=(1, 1),
                )
            )

        info = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(150))
        info.add_widget(MDLabel(text=f"{usuario.get('nombre', '')} {usuario.get('apellido', '')}".strip() or "Sin nombre", font_style="H6", bold=True, halign="center"))
        info.add_widget(MDLabel(text=f"Usuario: {usuario.get('usuario', '')}", font_style="Body2", theme_text_color="Secondary"))
        info.add_widget(MDLabel(text=f"Cargo: {usuario.get('cargo', 'Gerente')}", font_style="Body2", theme_text_color="Secondary"))
        info.add_widget(MDLabel(text=f"Correo: {usuario.get('email', '')}", font_style="Body2", theme_text_color="Secondary"))
        info.add_widget(MDLabel(text=f"Teléfono: {usuario.get('telefono', '')}", font_style="Body2", theme_text_color="Secondary"))

        layout.add_widget(imagen_wrap)
        layout.add_widget(info)

        dialog = MDDialog(
            title="Mi cuenta",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cambiar imagen", on_release=lambda instance: (dialog.dismiss(), self.seleccionar_imagen())),
                MDFlatButton(text="Configuración", on_release=lambda instance: (dialog.dismiss(), self.abrir_configuracion())),
                MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss()),
            ],
        )
        dialog.open()

    def abrir_configuracion(self):
        app = MDApp.get_running_app()
        usuario_actual = app.usuario_activo or {}

        layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12), size_hint_y=None, height=dp(320))
        campo_nombre = crear_campo_formulario("Nombre")
        campo_nombre.text = str(usuario_actual.get("nombre", ""))
        campo_apellido = crear_campo_formulario("Apellido")
        campo_apellido.text = str(usuario_actual.get("apellido", ""))
        campo_telefono = crear_campo_formulario("Teléfono")
        campo_telefono.text = str(usuario_actual.get("telefono", ""))
        campo_email = crear_campo_formulario("Correo Electrónico")
        campo_email.text = str(usuario_actual.get("email", ""))
        campos_configuracion = (campo_nombre, campo_apellido, campo_telefono, campo_email)

        def aplicar_colores_configuracion(tema):
            es_oscuro = tema == "Dark"
            color_texto = (1, 1, 1, 1) if es_oscuro else (0.08, 0.08, 0.08, 1)
            color_pista = (0.72, 0.75, 0.78, 1) if es_oscuro else (0.38, 0.38, 0.38, 1)
            color_linea = (0.55, 0.75, 0.62, 1) if es_oscuro else (0.25, 0.45, 0.32, 1)
            for campo in campos_configuracion:
                campo.text_color_normal = color_texto
                campo.text_color_focus = color_texto
                campo.hint_text_color_normal = color_pista
                campo.hint_text_color_focus = color_pista
                campo.line_color_normal = color_pista
                campo.line_color_focus = color_linea
            etiqueta_tema.text_color = color_texto

        layout.add_widget(campo_nombre)
        layout.add_widget(campo_apellido)
        layout.add_widget(campo_telefono)
        layout.add_widget(campo_email)

        tema_box = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(40))
        etiqueta_tema = MDLabel(
            text="Tema de la aplicación:",
            font_style="Subtitle2",
            theme_text_color="Custom",
        )
        tema_box.add_widget(etiqueta_tema)
        btn_claro = MDRaisedButton(text="Claro", md_bg_color=(0.1, 0.6, 0.3, 1))
        btn_oscuro = MDRaisedButton(text="Oscuro", md_bg_color=(0.2, 0.2, 0.25, 1))

        def cambiar_tema(tema):
            app.theme_cls.theme_style = tema
            aplicar_colores_configuracion(tema)
            Clock.schedule_once(lambda _dt: aplicar_contraste_vistas(tema), 0)
            mostrar_dialogo_simple("Tema", f"Tema cambiado a {tema}.")

        btn_claro.bind(on_release=lambda x: cambiar_tema("Light"))
        btn_oscuro.bind(on_release=lambda x: cambiar_tema("Dark"))
        tema_box.add_widget(btn_claro)
        tema_box.add_widget(btn_oscuro)
        layout.add_widget(tema_box)

        def guardar_cambios(instance):
            nom = campo_nombre.text.strip()
            ape = campo_apellido.text.strip()
            tel = campo_telefono.text.strip()
            ema = campo_email.text.strip()
            try:
                GestorBD().ejecutar_comando(
                    "UPDATE empleados SET nombre=?, apellido=?, telefono=?, email=? WHERE usuario=?",
                    (nom, ape, tel, ema, usuario_actual.get("usuario")),
                )
                app.usuario_activo["nombre"] = nom
                app.usuario_activo["apellido"] = ape
                app.usuario_activo["telefono"] = tel
                app.usuario_activo["email"] = ema
                self.nombre_gerente = f"{nom} {ape}".strip()
                dialog.dismiss()
                mostrar_dialogo_simple("Configuración guardada", "Datos del Gerente y tema actualizados con éxito.")
            except Exception as e:
                mostrar_dialogo_simple("Error", f"No se pudo guardar la configuración: {e}")

        dialog = MDDialog(
            title="Configuración de Gerente (Perfil y Tema)",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(text="Guardar cambios", on_release=guardar_cambios),
            ],
        )
        aplicar_colores_configuracion(app.theme_cls.theme_style)
        dialog.open()

    def seleccionar_imagen(self):
        usuario = (MDApp.get_running_app().usuario_activo or {}).get("usuario", "gerente")
        selector = FileChooserListView(
            path=os.path.expanduser("~"),
            filters=["*.png", "*.jpg", "*.jpeg", "*.webp"],
            size_hint_y=None,
            height=dp(330),
        )
        aplicar_color_texto_selector(selector)
        layout = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(370))
        layout.add_widget(selector)

        def guardar_seleccion(instance):
            if not selector.selection:
                mostrar_dialogo_simple("Imagen", "Selecciona una imagen primero.")
                return
            try:
                self.avatar_path = guardar_avatar(usuario, selector.selection[0])
                dialog.dismiss()
                mostrar_dialogo_simple("Imagen actualizada", "La imagen del gerente se guardó correctamente.")
            except Exception as exc:
                mostrar_dialogo_simple("Error de imagen", str(exc))

        dialog = MDDialog(
            title="Seleccionar imagen del gerente",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(text="Usar imagen", on_release=guardar_seleccion),
            ],
        )
        dialog.open()

    def agregar_producto(self, datos_iniciales=None):
        datos_iniciales = datos_iniciales or {}
        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
            size_hint_y=None,
            height=dp(7 * 48 + 7 * 10 + 66),
        )
        imagen_path = {"value": ""}
        campos = {
            "codigo": crear_campo_formulario("Código de barras"),
            "nombre": crear_campo_formulario("Nombre del producto"),
            "cantidad": crear_campo_formulario("Cantidad", input_filter="int"),
            "fecha": crear_campo_formulario("Fecha de vencimiento (YYYY-MM-DD)"),
            "pasillo": crear_campo_formulario("Pasillo o ubicación"),
        }
        for campo in campos.values():
            layout.add_widget(campo)

        categoria_label = MDLabel(text="Categoría", font_style="Caption", theme_text_color="Secondary", size_hint_y=None, height=dp(20))
        categoria_spinner = Spinner(
            text="Granos",
            values=sorted({"Lácteos", "Carnes", "Enlatados", "Bebidas", "Granos", "Pastas", "Otros", datos_iniciales.get("categoria", "Otros")}),
            size_hint_y=None,
            height=dp(42),
            background_color=(0.94, 0.97, 0.96, 1),
            color=(0.08, 0.12, 0.12, 1),
        )
        layout.add_widget(categoria_label)
        layout.add_widget(categoria_spinner)
        conservacion_spinner = Spinner(
            text="Refrigerado",
            values=["Refrigerado", "Congelado"],
            size_hint_y=None,
            height=dp(42),
        )
        layout.add_widget(MDLabel(text="Conservación", font_style="Caption", size_hint_y=None, height=dp(20)))
        layout.add_widget(conservacion_spinner)
        campos["codigo"].text = str(datos_iniciales.get("codigo", ""))
        campos["nombre"].text = str(datos_iniciales.get("nombre", ""))
        categoria_spinner.text = str(datos_iniciales.get("categoria", "Granos"))

        foto_estado = MDLabel(text="Foto del producto: sin tomar", font_style="Caption")

        def tomar_foto(instance):
            foto_estado.text = "Abriendo cámara..."

            def foto_lista(ruta, error=None):
                if ruta:
                    imagen_path["value"] = ruta
                    foto_estado.text = "Foto capturada y lista para guardar"

                    def completar_fecha(fecha, mensaje=None):
                        if fecha:
                            campos["fecha"].text = fecha
                            foto_estado.text = f"Foto guardada; vencimiento sugerido: {fecha}. Confirma la fecha."
                        elif mensaje:
                            foto_estado.text = f"Foto guardada; {mensaje}"

                    leer_fecha_en_imagen(ruta, completar_fecha)
                else:
                    foto_estado.text = "No se guardó la foto"
                    if error:
                        mostrar_dialogo_simple("Error de cámara", error)

            iniciar_captura_foto_producto(foto_lista)

        layout.add_widget(MDRaisedButton(
            text="Tomar foto del producto",
            icon="camera",
            size_hint_y=None,
            height=dp(42),
            on_release=tomar_foto,
        ))
        layout.add_widget(foto_estado)

        def guardar(instance):
            try:
                gestor = GestorBD()
                codigo = campos["codigo"].text.strip()
                nombre = campos["nombre"].text.strip()
                categoria = categoria_spinner.text.strip() or "Otros"
                cantidad = int(campos["cantidad"].text.strip() or 0)
                fecha_base = campos["fecha"].text.strip()
                if fecha_base:
                    date.fromisoformat(fecha_base)
                pasillo = campos["pasillo"].text.strip() or "A"
                congelado = conservacion_spinner.text == "Congelado"
                if not codigo or not nombre:
                    mostrar_dialogo_simple("Datos incompletos", "Código y nombre del producto son obligatorios.")
                    return
                if cantidad <= 0 or (not fecha_base and not congelado):
                    mostrar_dialogo_simple("Datos incompletos", "Indica una cantidad mayor que cero y una fecha de vencimiento (salvo que el producto sea congelado).")
                    return
                fecha_congelacion = date.today().isoformat() if congelado else None
                fecha = fecha_base or None
                if congelado:
                    fecha = ControladorInventario.calcular_vencimiento_congelado(
                        fecha or date.today().isoformat(), categoria
                    )
                    if pasillo == "A":
                        pasillo = "Freezer"
                gestor.ejecutar_comando(
                    "INSERT INTO productos (codigo_barras, nombre, categoria, cantidad_stock, fecha_vencimiento, "
                    "pasillo, imagen, congelado, fecha_congelacion, fecha_ingreso) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (codigo, nombre, categoria, cantidad, fecha, pasillo, imagen_path["value"], int(congelado), fecha_congelacion, date.today().isoformat()),
                )
                self.actualizar_metricas()
                self.actualizar_resumenes()
                extra = f" Vencimiento extendido hasta {fecha}." if congelado else ""
                mostrar_dialogo_simple("Producto agregado", f"{nombre} fue agregado correctamente en la categoría {categoria} y ubicación {pasillo}.{extra}")
                dialog.dismiss()
            except Exception as exc:
                mostrar_dialogo_simple("Error", f"No se pudo guardar el producto: {exc}")
                dialog.dismiss()

        dialog = MDDialog(
            title="Agregar producto",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(text="Guardar", on_release=guardar),
            ],
        )
        dialog.open()

    def gestionar_empleados(self):
        gestor = GestorBD()
        rows = gestor.ejecutar_consulta("SELECT nombre, apellido, cargo, usuario FROM empleados ORDER BY nombre ASC")
        if not rows:
            texto = "No hay empleados registrados."
            mostrar_dialogo_simple("Empleados", texto)
            return

        contenido = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10), size_hint_y=None)
        contenido.height = dp(80 * len(rows))
        for nombre, apellido, cargo, usuario in rows:
            fila = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(70))
            fila.add_widget(Image(source=ruta_avatar(usuario), size_hint_x=None, width=dp(58), allow_stretch=True, keep_ratio=True))
            fila.add_widget(MDLabel(
                text=f"{nombre} {apellido}\n{cargo or 'Empleado'}\nUsuario: {usuario}",
                font_style="Body2",
                valign="middle",
            ))
            contenido.add_widget(fila)

        scroll = ScrollView(size_hint_y=None, height=min(dp(360), dp(80 * len(rows))))
        scroll.add_widget(contenido)
        dialog = MDDialog(
            title="Empleados registrados",
            type="custom",
            content_cls=scroll,
            buttons=[MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss())],
        )
        dialog.open()

    def ver_reportes(self):
        layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10), size_hint_y=None, height=dp(260))
        btn_pdf = MDRaisedButton(text="Crear y Descargar Reporte PDF", md_bg_color=(0.05, 0.4, 0.2, 1), size_hint_x=1)
        btn_excel = MDRaisedButton(text="Crear y Descargar Archivo Excel", md_bg_color=(0.1, 0.5, 0.3, 1), size_hint_x=1)
        btn_pdf_mes = MDRaisedButton(text="Vencidos del mes en PDF", md_bg_color=(0.05, 0.4, 0.2, 1), size_hint_x=1)
        btn_excel_mes = MDRaisedButton(text="Vencidos del mes en Excel", md_bg_color=(0.1, 0.5, 0.3, 1), size_hint_x=1)
        
        btn_pdf.bind(on_release=lambda x: (dialog.dismiss(), self.crear_reporte_pdf()))
        btn_excel.bind(on_release=lambda x: (dialog.dismiss(), self.crear_reporte_excel()))
        btn_pdf_mes.bind(on_release=lambda x: (dialog.dismiss(), self.crear_reporte_vencidos_mes("pdf")))
        btn_excel_mes.bind(on_release=lambda x: (dialog.dismiss(), self.crear_reporte_vencidos_mes("excel")))
        
        layout.add_widget(btn_pdf)
        layout.add_widget(btn_excel)
        layout.add_widget(btn_pdf_mes)
        layout.add_widget(btn_excel_mes)

        dialog = MDDialog(
            title="Módulo de Reportes de Inventario",
            text="Genera reportes con historial completo, bajas y productos con su pasillo y stock.",
            type="custom",
            content_cls=layout,
            buttons=[MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss())],
        )
        dialog.open()

    def crear_reporte_pdf(self):
        try:
            reporte = ControladorReportes()
            nombre = f"reporte_general_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = reporte.exportar_pdf(tipo="movimientos", nombre_archivo=nombre)
            mostrar_dialogo_simple(
                "Reporte PDF creado con éxito",
                f"El reporte con historial, bajas y productos se descargó en tu PC:\n\n{pdf_path}\n\n(Listo para consultar o transferir al celular)",
            )
        except Exception as exc:
            mostrar_dialogo_simple("Error al generar PDF", str(exc))

    def crear_reporte_excel(self):
        try:
            reporte = ControladorReportes()
            nombre = f"reporte_general_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            excel_path = reporte.exportar_excel(tipo="movimientos", nombre_archivo=nombre)
            mostrar_dialogo_simple(
                "Archivo Excel creado con éxito",
                f"El archivo Excel con balances, historial y productos se descargó en tu PC:\n\n{excel_path}",
            )
        except Exception as exc:
            mostrar_dialogo_simple("Error al generar Excel", str(exc))

    def crear_reporte_vencidos_mes(self, formato):
        try:
            reporte = ControladorReportes()
            sufijo = datetime.now().strftime("%Y_%m")
            if formato == "pdf":
                nombre = f"vencidos_{sufijo}.pdf"
                ruta = reporte.exportar_pdf("vencidos_mensual", nombre)
            else:
                nombre = f"vencidos_{sufijo}.xlsx"
                ruta = reporte.exportar_excel("vencidos_mensual", nombre)
            mostrar_dialogo_simple("Reporte mensual creado", f"El reporte de productos vencidos de {datetime.now():%m/%Y} incluye cantidades y valor estimado.\n\n{ruta}")
        except Exception as exc:
            mostrar_dialogo_simple("Error al generar reporte mensual", str(exc))

    def ver_graficos(self):
        gestor = GestorBD()
        try:
            bajas = gestor.ejecutar_consulta(
                "SELECT p.nombre, SUM(m.cantidad) FROM movimientos m JOIN productos p ON m.id_producto = p.id_producto WHERE m.tipo_movimiento = 'salida' GROUP BY p.nombre ORDER BY SUM(m.cantidad) DESC LIMIT 5"
            )
        except Exception:
            try:
                bajas = gestor.ejecutar_consulta(
                    "SELECT p.nombre, SUM(m.cantidad) FROM movimientos m JOIN productos p ON m.id_producto = p.id_producto WHERE m.tipo = 'salida' GROUP BY p.nombre ORDER BY SUM(m.cantidad) DESC LIMIT 5"
                )
            except Exception:
                bajas = []

        vencidos_res = gestor.ejecutar_consulta(
            "SELECT nombre, cantidad_stock, fecha_vencimiento FROM productos WHERE date(fecha_vencimiento) <= date('now') LIMIT 5"
        )
        almacen_res = gestor.ejecutar_consulta(
            "SELECT categoria, SUM(cantidad_stock) FROM productos GROUP BY categoria"
        )

        texto_grafico = "=== BALANCES Y GRÁFICOS DE ALMACÉN ===\n\n"
        texto_grafico += "📉 PRODUCTOS CON MAYOR BAJA / SALIDAS:\n"
        if bajas:
            for nombre, cant in bajas:
                texto_grafico += f"  • {nombre}: -{cant} unidades\n"
        else:
            texto_grafico += "  (No hay bajas registradas aún)\n"

        texto_grafico += "\n⚠️ PRODUCTOS VENCIDOS:\n"
        if vencidos_res:
            for nom, stock, f_venc in vencidos_res:
                texto_grafico += f"  • {nom}: {stock} un. (Venció: {f_venc})\n"
        else:
            texto_grafico += "  (No hay productos vencidos actualmente)\n"

        texto_grafico += "\n📦 STOCK EN ALMACÉN POR CATEGORÍA:\n"
        if almacen_res:
            for cat, total in almacen_res:
                texto_grafico += f"  • {cat or 'General'}: {total} unidades\n"
        else:
            texto_grafico += "  (Almacén vacío)\n"

        layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10), size_hint_y=None, height=dp(260))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(MDLabel(text=texto_grafico, font_style="Caption", markup=True))
        layout.add_widget(scroll)

        btn_excel_graficos = MDRaisedButton(
            text="Descargar Balances y Gráficos en Excel (.xlsx)",
            md_bg_color=(0.1, 0.5, 0.3, 1),
            size_hint_x=1
        )
        btn_excel_graficos.bind(on_release=lambda x: (dialog.dismiss(), self.crear_reporte_excel()))
        layout.add_widget(btn_excel_graficos)

        dialog = MDDialog(
            title="Gráficos y Estadísticas de Inventario",
            type="custom",
            content_cls=layout,
            buttons=[MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss())],
        )
        dialog.open()

    def gestionar_proveedores(self):
        layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12), size_hint_y=None, height=dp(6 * 48 + 5 * 10 + 24))
        campos = {
            "nombre": crear_campo_formulario("Nombre del Proveedor"),
            "telefono": crear_campo_formulario("Teléfono"),
            "correo": crear_campo_formulario("Correo Electrónico"),
            "producto": crear_campo_formulario("Producto que trae"),
            "cantidad": crear_campo_formulario("Cantidad para el stock", input_filter="int"),
            "precio": crear_campo_formulario("Precio del producto", input_filter="float"),
        }
        for campo in campos.values(): 
            layout.add_widget(campo)

        def guardar_proveedor(instance):
            try:
                nombre = campos["nombre"].text.strip()
                telefono = campos["telefono"].text.strip()
                correo = campos["correo"].text.strip()
                producto = campos["producto"].text.strip()
                cantidad = int(campos["cantidad"].text.strip() or 0)
                precio_texto = campos["precio"].text.strip().replace(",", ".")

                if not nombre or not producto or cantidad <= 0 or not precio_texto:
                    mostrar_dialogo_simple("Datos incompletos", "Nombre, producto, cantidad y precio son obligatorios.")
                    return
                precio = float(precio_texto)
                if precio < 0:
                    mostrar_dialogo_simple("Precio no válido", "El precio no puede ser negativo.")
                    return

                gestor = GestorBD()
                gestor.registrar_suministro_proveedor(nombre, telefono, correo, producto, cantidad, precio)

                self.actualizar_metricas()
                self.actualizar_resumenes()
                mostrar_dialogo_simple("Proveedor Registrado", f"Proveedor {nombre} guardado. Stock de '{producto}': +{cantidad}; precio: {precio:.2f}.")
                dialog.dismiss()
            except Exception as exc:
                mostrar_dialogo_simple("Error", f"No se pudo registrar el proveedor: {exc}")

        dialog = MDDialog(
            title="Registrar Proveedor y Stock", 
            type="custom", 
            content_cls=layout, 
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(text="Guardar Proveedor", on_release=guardar_proveedor)
            ]
        )
        dialog.open()

    def escaner_codigo(self):
        if "escaner" in self.manager.screen_names:
            pantalla_escaner = self.manager.get_screen("escaner")
            pantalla_escaner.pantalla_origen = "panel_gerente"
            self.manager.current = "escaner"

    def cerrar_sesion(self):
        MDApp.get_running_app().usuario_activo = {}
        self.manager.current = "inicio_sesion"


class PantallaEscaner(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controlador = ControladorEscaner()
        self.producto_actual = None
        self.codigo_escaneado_buffer = ""
        self.pantalla_origen = "panel_empleado"

    def on_enter(self, *args):
        if platform != "android":
            Window.bind(on_key_down=self._on_keyboard_down)
        print("[ESCANER] Pantalla activa.")

    def on_leave(self, *args):
        if platform != "android":
            Window.unbind(on_key_down=self._on_keyboard_down)
        self._codigo_consulta_actual = None

    def escanear_con_camara(self):
        if platform != "android":
            mostrar_dialogo_simple("Escáner de cámara", "El escaneo con cámara está disponible en la versión Android.")
            return

        try:
            from jnius import PythonJavaClass, autoclass, java_method
            from kivy.clock import Clock

            actividad = autoclass("org.kivy.android.PythonActivity").mActivity
            cliente = autoclass(
                "com.google.mlkit.vision.codescanner.GmsBarcodeScanning"
            ).getClient(actividad)
            tarea = cliente.startScan()
            pantalla = self

            class EscaneoCorrecto(PythonJavaClass):
                __javainterfaces__ = ["com/google/android/gms/tasks/OnSuccessListener"]
                __javacontext__ = "app"

                @java_method("(Ljava/lang/Object;)V")
                def onSuccess(self, resultado):
                    codigo = str(resultado.getRawValue() or "").strip()
                    if codigo:
                        Clock.schedule_once(lambda _dt: pantalla.procesar_codigo(codigo), 0)
                    else:
                        Clock.schedule_once(
                            lambda _dt: mostrar_dialogo_simple("Escáner", "No se leyó ningún código."),
                            0,
                        )

            class EscaneoFallido(PythonJavaClass):
                __javainterfaces__ = ["com/google/android/gms/tasks/OnFailureListener"]
                __javacontext__ = "app"

                @java_method("(Ljava/lang/Exception;)V")
                def onFailure(self, error):
                    mensaje = str(error or "No se pudo abrir la cámara.")
                    Clock.schedule_once(
                        lambda _dt: mostrar_dialogo_simple("Error de escáner", mensaje),
                        0,
                    )

            self._scanner_listeners = (EscaneoCorrecto(), EscaneoFallido())
            tarea.addOnSuccessListener(self._scanner_listeners[0])
            tarea.addOnFailureListener(self._scanner_listeners[1])
        except Exception as exc:
            mostrar_dialogo_simple("Error de escáner", f"No se pudo iniciar el escáner: {exc}")

    def _on_keyboard_down(self, window, key, scancode, codepoint, modifier):
        if codepoint == "enter" or key == 13:
            if self.codigo_escaneado_buffer.strip():
                codigo_final = self.codigo_escaneado_buffer.strip()
                print(f"[USB] Código completo recibido: {codigo_final}")
                self.procesar_codigo(codigo_final)
                self.codigo_escaneado_buffer = ""
        elif codepoint:
            self.codigo_escaneado_buffer += codepoint
        return True

    def volver(self):
        if self.manager is not None:
            destino = getattr(self, "pantalla_origen", "panel_empleado")
            if destino in self.manager.screen_names:
                self.manager.current = destino
            elif "panel_empleado" in self.manager.screen_names:
                self.manager.current = "panel_empleado"
            elif "panel_gerente" in self.manager.screen_names:
                self.manager.current = "panel_gerente"

    def procesar_codigo(self, codigo_barras="7791234567890"):
        print(f"[ESCANER] Procesando código de barras: {codigo_barras}")
        resultado = self.controlador.procesar_codigo(codigo_barras)

        if resultado:
            self._codigo_consulta_actual = None
            id_prod, barcode, nombre, categoria, stock, unidad, fecha_vencimiento, pasillo = resultado
            self.producto_actual = resultado
            dias_restantes = self.calcular_dias_restantes(fecha_vencimiento)
            cantidad = int(stock or 0)
            unidad_texto = str(unidad or "unidad(es)")

            self.ids.lbl_nombre.text = f"[b]{nombre}[/b]"
            self.ids.lbl_unidades.text = f"{cantidad} unidades"
            self.ids.lbl_individuales.text = f"{cantidad} {unidad_texto}"
            self.ids.lbl_tipo.text = str(categoria or "-")
            self.ids.lbl_fecha.text = str(fecha_vencimiento or "-")
            self.ids.lbl_ubicacion.text = f"Pasillo {pasillo or '-'}"

            if dias_restantes is None:
                self.ids.lbl_dias_restantes.text = "Sin fecha de vencimiento"
                self.ids.lbl_dias_restantes.text_color = (0.45, 0.45, 0.45, 1)
            elif dias_restantes > 0:
                self.ids.lbl_dias_restantes.text = f"Días para vencer: {dias_restantes} días"
                self.ids.lbl_dias_restantes.text_color = (0.3, 0.8, 0.4, 1)
            elif dias_restantes == 0:
                self.ids.lbl_dias_restantes.text = "¡Vence HOY!"
                self.ids.lbl_dias_restantes.text_color = (0.9, 0.6, 0.1, 1)
            else:
                self.ids.lbl_dias_restantes.text = f"¡VENCIDO hace {-dias_restantes} días!"
                self.ids.lbl_dias_restantes.text_color = (0.9, 0.2, 0.2, 1)
        else:
            self.ids.lbl_nombre.text = "Producto no encontrado"
            self.ids.lbl_unidades.text = "0 unidades"
            self.ids.lbl_individuales.text = "0 unidad(es)"
            self.ids.lbl_tipo.text = "-"
            self.ids.lbl_fecha.text = "-"
            self.ids.lbl_ubicacion.text = "Pasillo -"
            self.ids.lbl_dias_restantes.text = "Buscando datos del código..."
            self.producto_actual = None
            from kivy.clock import Clock
            self._codigo_consulta_actual = codigo_barras

            def consultar_datos():
                datos = self.controlador.buscar_datos_publicos(codigo_barras)

                def completar(_dt):
                    if self.manager.current == "escaner" and self._codigo_consulta_actual == codigo_barras:
                        self._ofrecer_alta_escaneada(codigo_barras, datos)

                Clock.schedule_once(completar, 0)

            threading.Thread(target=consultar_datos, daemon=True).start()

    def _ofrecer_alta_escaneada(self, codigo, datos):
        panel = self.manager.get_screen(self.pantalla_origen)
        valores = datos or {"codigo": codigo}
        detalle = (
            f"Encontramos {datos['nombre']} ({datos['categoria']}). Completa stock, vencimiento y ubicación."
            if datos
            else "El código no tiene ficha pública. Puedes registrar el producto manualmente."
        )
        dialog = MDDialog(
            title="Registrar producto escaneado",
            text=detalle,
            buttons=[
                MDFlatButton(text="Ahora no", on_release=lambda _button: dialog.dismiss()),
                MDRaisedButton(
                    text="Completar registro",
                    on_release=lambda _button: (dialog.dismiss(), panel.agregar_producto(valores)),
                ),
            ],
        )
        dialog.open()

    def editar_producto(self):
        if not self.producto_actual:
            mostrar_dialogo_simple("Editar producto", "Primero escanea un producto válido.")
            return

        _, codigo, nombre, categoria, stock, unidad, fecha_vencimiento, pasillo = self.producto_actual
        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
            size_hint_y=None,
            height=dp(5 * 48 + 4 * 10 + 24),
        )
        campos = {
            "nombre": crear_campo_formulario("Nombre del producto"),
            "categoria": crear_campo_formulario("Categoría"),
            "cantidad": crear_campo_formulario("Total de unidades", input_filter="int"),
            "unidad": crear_campo_formulario("Unidad individual"),
            "pasillo": crear_campo_formulario("Ubicación o pasillo del almacén"),
        }
        valores = {
            "nombre": nombre or "",
            "categoria": categoria or "",
            "cantidad": str(stock or 0),
            "unidad": unidad or "unidad(es)",
            "pasillo": pasillo or "A",
        }
        for clave, campo in campos.items():
            campo.text = valores[clave]
            layout.add_widget(campo)

        def guardar(instance):
            try:
                nombre_nuevo = campos["nombre"].text.strip()
                categoria_nueva = campos["categoria"].text.strip()
                cantidad_nueva = int(campos["cantidad"].text.strip() or 0)
                unidad_nueva = campos["unidad"].text.strip() or "unidad(es)"
                pasillo_nuevo = campos["pasillo"].text.strip() or "A"
                if not nombre_nuevo or cantidad_nueva < 0:
                    mostrar_dialogo_simple("Datos inválidos", "Indica un nombre y una cantidad válida.")
                    return
                exito = GestorBD().ejecutar_comando(
                    "UPDATE productos SET nombre = ?, categoria = ?, cantidad_stock = ?, unidad_medida = ?, pasillo = ? WHERE codigo_barras = ?",
                    (nombre_nuevo, categoria_nueva, cantidad_nueva, unidad_nueva, pasillo_nuevo, codigo),
                )
                if not exito:
                    mostrar_dialogo_simple("Error", "No se pudieron guardar los cambios.")
                    return
                dialog.dismiss()
                self.procesar_codigo(codigo)
                mostrar_dialogo_simple("Producto actualizado", "Los datos del producto se guardaron correctamente.")
            except ValueError:
                mostrar_dialogo_simple("Datos inválidos", "La cantidad debe ser un número entero.")
            except Exception as exc:
                mostrar_dialogo_simple("Error", f"No se pudo editar el producto: {exc}")

        dialog = MDDialog(
            title="Editar producto y ubicación",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda instance: dialog.dismiss()),
                MDRaisedButton(text="Guardar cambios", on_release=guardar),
            ],
        )
        dialog.open()

    def quitar_fecha_vencimiento(self):
        if not self.producto_actual or not self.producto_actual[6]:
            mostrar_dialogo_simple("Vencimiento", "El producto no tiene una fecha de vencimiento guardada.")
            return
        id_producto = self.producto_actual[0]
        codigo = self.producto_actual[1]
        confirmacion = MDDialog(
            title="Quitar fecha de vencimiento",
            text="Se borrará solo la fecha; el producto, stock, foto y código se conservarán.",
            buttons=[
                MDFlatButton(text="Cancelar", on_release=lambda _button: confirmacion.dismiss()),
                MDRaisedButton(
                    text="Quitar fecha",
                    on_release=lambda _button: self._confirmar_quitar_fecha(confirmacion, id_producto, codigo),
                ),
            ],
        )
        confirmacion.open()

    def _confirmar_quitar_fecha(self, dialog, id_producto, codigo):
        try:
            ControladorInventario().quitar_fecha_vencimiento(id_producto)
            dialog.dismiss()
            self.procesar_codigo(codigo)
            mostrar_dialogo_simple("Fecha eliminada", "Se conservó el producto con su stock y demás datos.")
        except Exception as exc:
            mostrar_dialogo_simple("Error", f"No se pudo quitar la fecha: {exc}")

    def calcular_dias_restantes(self, fecha_vencimiento_str):
        if not fecha_vencimiento_str:
            return None
        try:
            f_venc = datetime.strptime(str(fecha_vencimiento_str), "%Y-%m-%d")
            hoy = datetime.now()
            diferencia = f_venc - hoy
            return diferencia.days + 1
        except Exception as e:
            print(f"[ERROR FECHA] No se pudo parsear la fecha: {e}")
            return 0

    def guardar_almacen(self):
        if self.producto_actual:
            id_producto = self.producto_actual[0]
            id_empleado_actual = 1

            exito, mensaje = self.controlador.registrar_movimiento(
                id_producto=id_producto,
                tipo_movimiento="entrada",
                cantidad=1,
                id_empleado=id_empleado_actual,
            )

            if exito:
                self.ids.lbl_nombre.text = "[b]¡Guardado al almacén![/b]"
                print(f"[ÉXITO] {mensaje}")
            else:
                print(f"[ERROR] {mensaje}")
        else:
            print("[AVISO] No hay ningún producto cargado para guardar.")


class FreshControlApp(MDApp):
    usuario_activo = {}

    def build(self):
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"
        if platform != "android":
            Window.size = (1280, 800)
        Window.softinput_mode = "below_target"

        try:
            inicializar_bd()
        except Exception as e:
            print(f"Aviso al inicializar la base de datos: {e}")

        sm = MDScreenManager()
        sm.add_widget(PantallaInicioSesion(name="inicio_sesion"))
        sm.add_widget(PantallaRegistroGerente(name="registro_gerente"))
        sm.add_widget(PantallaRegistroEmpleado(name="registro_empleado"))
        sm.add_widget(PantallaPanelGerente(name="panel_gerente"))
        sm.add_widget(PantallaPanelEmpleado(name="panel_empleado"))
        sm.add_widget(PantallaEscaner(name="escaner"))
        Clock.schedule_once(lambda _dt: aplicar_contraste_vistas(self.theme_cls.theme_style), 0)
        return sm


if __name__ == "__main__":
    FreshControlApp().run()