import os
import re
import shutil
import sys
from datetime import datetime

# Asegurar que la carpeta base de la app esté en el sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty, NumericProperty
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.pickers import MDDatePicker
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.textfield import MDTextField

from controladores.controlador_escaner import ControladorEscaner
from controladores.controlador_reportes import ControladorReportes

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


class LataIcon(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redibujar, size=self._redibujar)
        self._redibujar()

    def _redibujar(self, *_args):
        self.canvas.clear()
        x, y = self.pos
        width, height = self.size
        body_width = min(width * 0.42, dp(22))
        body_height = min(height * 0.68, dp(30))
        body_x = x + (width - body_width) / 2
        body_y = y + (height - body_height) / 2
        with self.canvas:
            Color(0.95, 0.45, 0.05, 1)
            RoundedRectangle(pos=(body_x, body_y), size=(body_width, body_height), radius=[dp(3)])
            Color(1, 0.68, 0.2, 1)
            Ellipse(pos=(body_x, body_y + body_height - dp(4)), size=(body_width, dp(8)))
            Color(0.8, 0.3, 0.02, 1)
            Line(ellipse=(body_x, body_y + body_height - dp(4), body_width, dp(8)), width=1.1)
            Line(points=[body_x + body_width * 0.25, body_y + body_height * 0.42, body_x + body_width * 0.75, body_y + body_height * 0.42], width=1.1)


Builder.load_file(os.path.join(VISTAS_DIR, "inicio_sesion.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "escaner.kv"))


def mostrar_dialogo_simple(title, text):
    dialog = MDDialog(
        title=title,
        text=text,
        buttons=[MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss())],
    )
    dialog.open()
    return dialog


def crear_campo_formulario(hint_text, **kwargs):
    return MDTextField(
        hint_text=hint_text,
        mode="rectangle",
        size_hint_y=None,
        height=dp(48),
        **kwargs,
    )


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

    def iniciar_sesion(self):
        usuario = self.ids.usuario_field.text.strip()
        password = self.ids.password_field.text.strip()
        label_error = self.ids.mensaje_error

        if not usuario or not password:
            label_error.text = "Por favor ingrese usuario y contraseña"
            return

        usuario_db = verificar_credenciales(usuario, password)

        if usuario_db:
            label_error.text = ""
            self.ids.usuario_field.text = ""
            self.ids.password_field.text = ""

            app = MDApp.get_running_app()
            app.usuario_activo = dict(usuario_db)

            rol = str(usuario_db["rol"]).lower()
            if rol == "gerente":
                self.manager.current = "panel_gerente"
            elif rol == "empleado":
                self.manager.current = "panel_empleado"
            else:
                label_error.text = f"Rol de usuario desconocido: {rol}"
        else:
            label_error.text = "Usuario o contraseña incorrectos"

    def ir_a_registro_gerente(self):
        if hasattr(self.ids, 'mensaje_error'):
            self.ids.mensaje_error.text = ""
        self.manager.current = "registro_gerente"

    def ir_a_registro_empleado(self):
        if hasattr(self.ids, 'mensaje_error'):
            self.ids.mensaje_error.text = ""
        self.manager.current = "registro_empleado"


class PantallaRegistroGerente(MDScreen):
    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def guardar_gerente(self):
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

        if self.ids.password_field.text.strip() != self.ids.confirm_password_field.text.strip():
            self.ids.confirm_password_field.error = True
            self.ids.confirm_password_field.helper_text = "Las contraseñas no coinciden"
            return

        exito, msg = registrar_usuario(
            self.ids.nombre_field.text.strip(),
            self.ids.apellido_field.text.strip(),
            self.ids.usuario_field.text.strip(),
            self.ids.password_field.text.strip(),
            self.ids.email_field.text.strip(),
            self.ids.telefono_field.text.strip(),
            cargo="Gerente General",
            rol="gerente"
        )

        if exito:
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

        if self.ids.password_field.text.strip() != self.ids.confirm_password_field.text.strip():
            self.ids.confirm_password_field.error = True
            self.ids.confirm_password_field.helper_text = "Las contraseñas no coinciden"
            return

        exito, msg = registrar_usuario(
            self.ids.nombre_field.text.strip(),
            self.ids.apellido_field.text.strip(),
            self.ids.usuario_field.text.strip(),
            self.ids.password_field.text.strip(),
            self.ids.email_field.text.strip(),
            self.ids.telefono_field.text.strip(),
            cargo=self.ids.cargo_field.text.strip(),
            rol="empleado"
        )

        if exito:
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
    drawer_open = BooleanProperty(False)
    drawer_width = NumericProperty(0)
    fecha_actual = StringProperty("")
    hora_actual = StringProperty("")
    resumen_movimientos = StringProperty("Todavía no hay movimientos registrados.")
    resumen_categorias = StringProperty("No hay categorías cargadas.")
    productos_lacteos = NumericProperty(0)
    productos_carnes = NumericProperty(0)
    productos_granos = NumericProperty(0)
    productos_enlatados = NumericProperty(0)
    productos_bebidas = NumericProperty(0)
    total_productos = NumericProperty(0)
    stock_bajo = NumericProperty(0)
    por_vencer = NumericProperty(0)
    vencidos = NumericProperty(0)

    def on_pre_enter(self, *args):
        """Carga los datos del usuario activo, actualiza fecha/hora e inventario."""
        app = MDApp.get_running_app()
        if app.usuario_activo:
            nombre_completo = f"{app.usuario_activo.get('nombre', '')} {app.usuario_activo.get('apellido', '')}".strip()
            self.nombre_empleado = nombre_completo if nombre_completo else "Empleado"
            self.avatar_path = ruta_avatar(app.usuario_activo.get("usuario"))
        
        self.actualizar_fecha_hora()
        self.actualizar_metricas()
        self.actualizar_resumenes()

    def actualizar_fecha_hora(self):
        """Calcula la fecha y hora exacta actual del sistema."""
        ahora = datetime.now()
        self.fecha_actual = ahora.strftime("%d/%m/%Y")
        self.hora_actual = ahora.strftime("%I:%M %p")

    def abrir_calendario(self):
        """Abre el selector de fechas precargado con el día actual."""
        ahora = datetime.now()
        date_dialog = MDDatePicker(
            year=ahora.year,
            month=ahora.month,
            day=ahora.day
        )
        date_dialog.bind(on_save=self.al_seleccionar_fecha)
        date_dialog.open()

    def al_seleccionar_fecha(self, instance, value, date_range):
        """Asigna la fecha seleccionada en el picker a la variable de pantalla."""
        self.fecha_actual = value.strftime("%d/%m/%Y")

    def registrar_entrada(self):
        self._abrir_dialogo_movimiento("entrada")

    def registrar_salida(self):
        self._abrir_dialogo_movimiento("salida")

    def agregar_producto(self):
        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
            size_hint_y=None,
            height=dp(5 * 48 + 4 * 10 + 24),
        )
        campos = {
            "codigo": crear_campo_formulario("Código de barras"),
            "nombre": crear_campo_formulario("Nombre del producto"),
            "categoria": crear_campo_formulario("Categoría"),
            "cantidad": crear_campo_formulario("Cantidad", input_filter="int"),
            "fecha": crear_campo_formulario("Fecha de vencimiento (YYYY-MM-DD)"),
        }
        for campo in campos.values():
            layout.add_widget(campo)

        def guardar(instance):
            try:
                codigo = campos["codigo"].text.strip()
                nombre = campos["nombre"].text.strip()
                categoria = campos["categoria"].text.strip()
                cantidad = int(campos["cantidad"].text.strip() or 0)
                fecha = campos["fecha"].text.strip() or datetime.now().strftime("%Y-%m-%d")
                if not codigo or not nombre or not categoria:
                    mostrar_dialogo_simple("Datos incompletos", "Código, nombre y categoría son obligatorios.")
                    return
                GestorBD().ejecutar_comando(
                    "INSERT INTO productos (codigo_barras, nombre, categoria, cantidad_stock, fecha_vencimiento) VALUES (?, ?, ?, ?, ?)",
                    (codigo, nombre, categoria, cantidad, fecha),
                )
                self.actualizar_metricas()
                self.actualizar_resumenes()
                mostrar_dialogo_simple("Producto agregado", f"{nombre} fue agregado correctamente.")
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
        gestor = GestorBD()
        filas = gestor.listar_movimientos(10)
        if not filas:
            texto = "Todavía no hay movimientos en el historial."
        else:
            texto = "\n".join(
                f"{row[5]} | {row[2]} | {row[3]} {row[1]} x{row[4]} | {row[6]}"
                for row in filas
            )
        mostrar_dialogo_simple("Historial de movimientos", texto)

    def actualizar_resumenes(self):
        gestor = GestorBD()
        movimientos = gestor.listar_movimientos(5)
        if movimientos:
            self.resumen_movimientos = "\n".join(
                f"{row[5]}  |  {row[3].title()}  |  {row[1]}  |  {row[4]} unidades"
                for row in movimientos
            )
        else:
            self.resumen_movimientos = "Todavía no hay movimientos registrados."

        categorias = gestor.listar_productos_por_categoria()
        self.productos_lacteos = 0
        self.productos_carnes = 0
        self.productos_granos = 0
        self.productos_enlatados = 0
        self.productos_bebidas = 0
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
        except Exception as e:
            print(f"Error cargando métricas en panel empleado: {e}")

    def toggle_nav_drawer(self):
        self.drawer_open = not self.drawer_open
        Animation.cancel_all(self, "drawer_width")
        Animation(drawer_width=dp(238) if self.drawer_open else 0, duration=0.2).start(self)

    def ir_a_escaner(self):
        if "escaner" in self.manager.screen_names:
            pantalla_escaner = self.manager.get_screen("escaner")
            pantalla_escaner.pantalla_origen = "panel_empleado"
            self.manager.current = "escaner"

    def buscar_producto(self):
        gestor = GestorBD()
        rows = gestor.ejecutar_consulta("SELECT nombre, categoria, cantidad_stock, fecha_vencimiento FROM productos ORDER BY nombre LIMIT 20")
        if not rows:
            texto = "No hay productos cargados actualmente."
        else:
            texto = "\n".join(
                f"{nombre} | {categoria} | stock: {stock} | vence: {fecha}"
                for nombre, categoria, stock, fecha in rows
            )
        mostrar_dialogo_simple("Inventario disponible", texto)

    def ver_inventario(self):
        self.buscar_producto()

    def mostrar_cuenta(self):
        usuario = MDApp.get_running_app().usuario_activo or {}
        avatar = self.avatar_path or ruta_avatar(usuario.get("usuario"))
        layout = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(14), size_hint_y=None, height=dp(360))

        imagen_wrap = BoxLayout(size_hint=(None, None), size=(dp(120), dp(120)), pos_hint={"center_x": 0.5})
        imagen_wrap.add_widget(
            Image(
                source=avatar or "",
                size_hint=(1, 1),
                allow_stretch=True,
                keep_ratio=True,
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
                MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss()),
            ],
        )
        dialog.open()

    def seleccionar_imagen(self):
        usuario = (MDApp.get_running_app().usuario_activo or {}).get("usuario", "empleado")
        selector = FileChooserListView(
            path=os.path.expanduser("~"),
            filters=["*.png", "*.jpg", "*.jpeg", "*.webp"],
            size_hint_y=None,
            height=dp(330),
        )
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
    drawer_open = BooleanProperty(False)
    drawer_width = NumericProperty(0)
    fecha_actual = StringProperty("")
    hora_actual = StringProperty("")
    total_productos = NumericProperty(0)
    stock_bajo = NumericProperty(0)
    por_vencer = NumericProperty(0)
    vencidos = NumericProperty(0)
    resumen_alertas = StringProperty("No hay alertas críticas.")
    resumen_movimientos = StringProperty("Todavía no hay movimientos registrados.")
    resumen_categorias = StringProperty("No hay categorías cargadas.")

    def on_pre_enter(self, *args):
        app = MDApp.get_running_app()
        if app.usuario_activo:
            nombre_completo = f"{app.usuario_activo.get('nombre', '')} {app.usuario_activo.get('apellido', '')}".strip()
            self.nombre_gerente = nombre_completo if nombre_completo else "Gerente"
            self.avatar_path = ruta_avatar(app.usuario_activo.get("usuario"))

        ahora = datetime.now()
        self.fecha_actual = ahora.strftime("%d/%m/%Y")
        self.hora_actual = ahora.strftime("%I:%M %p")

        self.actualizar_metricas()
        self.actualizar_resumenes()

    def actualizar_metricas(self):
        try:
            metricas = obtener_metricas_dashboard()
            self.total_productos = metricas.get("total_productos", 0)
            self.stock_bajo = metricas.get("stock_bajo", 0)
            self.por_vencer = metricas.get("por_vencer", 0)
            self.vencidos = metricas.get("vencidos", 0)
        except Exception as e:
            print(f"Error cargando métricas en panel gerente: {e}")

    def actualizar_resumenes(self):
        gestor = GestorBD()
        alertas = gestor.obtener_notificaciones_gerente(7)
        if alertas:
            self.resumen_alertas = "\n".join(
                f"{tipo}: {detalle}" for tipo, detalle, _, _, _ in alertas[:5]
            )
        else:
            self.resumen_alertas = "No hay alertas críticas."

        movimientos = gestor.listar_movimientos(5)
        if movimientos:
            self.resumen_movimientos = "\n".join(
                f"{row[5]}  |  {row[3].title()}  |  {row[1]}  |  {row[4]} unidades"
                for row in movimientos
            )
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
        Animation(drawer_width=dp(246) if self.drawer_open else 0, duration=0.2).start(self)

    def ver_inventario(self):
        gestor = GestorBD()
        rows = gestor.ejecutar_consulta("SELECT nombre, categoria, cantidad_stock, fecha_vencimiento, pasillo FROM productos ORDER BY nombre ASC")
        if not rows:
            texto = "No existen productos registrados."
        else:
            texto = "\n".join(
                f"{nombre} | {categoria} | stock: {stock} | vence: {fecha} | pasillo: {pasillo}"
                for nombre, categoria, stock, fecha, pasillo in rows
            )
        mostrar_dialogo_simple("Inventario completo", texto)

    def ver_alertas(self):
        mostrar_dialogo_simple("Alertas críticas", self.resumen_alertas)

    def ver_movimientos(self):
        gestor = GestorBD()
        filas = gestor.listar_movimientos(20)
        texto = "\n".join(f"{row[5]} | {row[3].title()} | {row[1]} | {row[4]} unidades" for row in filas)
        mostrar_dialogo_simple("Movimientos recientes", texto or "No hay movimientos registrados.")

    def ver_categorias(self):
        mostrar_dialogo_simple("Resumen del inventario", self.resumen_categorias)

    def mostrar_cuenta(self):
        usuario = MDApp.get_running_app().usuario_activo or {}
        avatar = self.avatar_path or ruta_avatar(usuario.get("usuario"))
        layout = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(14), size_hint_y=None, height=dp(360))

        imagen_wrap = BoxLayout(size_hint=(None, None), size=(dp(120), dp(120)), pos_hint={"center_x": 0.5})
        imagen_wrap.add_widget(
            Image(
                source=avatar or "",
                size_hint=(1, 1),
                allow_stretch=True,
                keep_ratio=True,
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
                MDFlatButton(text="Cerrar", on_release=lambda instance: dialog.dismiss()),
            ],
        )
        dialog.open()

    def seleccionar_imagen(self):
        usuario = (MDApp.get_running_app().usuario_activo or {}).get("usuario", "gerente")
        selector = FileChooserListView(
            path=os.path.expanduser("~"),
            filters=["*.png", "*.jpg", "*.jpeg", "*.webp"],
            size_hint_y=None,
            height=dp(330),
        )
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

    def agregar_producto(self):
        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
            size_hint_y=None,
            height=dp(6 * 48 + 5 * 10 + 24),
        )
        campos = {
            "codigo": crear_campo_formulario("Código de barras"),
            "nombre": crear_campo_formulario("Nombre del producto"),
            "categoria": crear_campo_formulario("Categoría"),
            "cantidad": crear_campo_formulario("Cantidad", input_filter="int"),
            "fecha": crear_campo_formulario("Fecha de vencimiento (YYYY-MM-DD)"),
            "pasillo": crear_campo_formulario("Pasillo o ubicación"),
        }
        for campo in campos.values():
            layout.add_widget(campo)

        def guardar(instance):
            try:
                gestor = GestorBD()
                codigo = campos["codigo"].text.strip()
                nombre = campos["nombre"].text.strip()
                categoria = campos["categoria"].text.strip()
                cantidad = int(campos["cantidad"].text.strip() or 0)
                fecha = campos["fecha"].text.strip() or datetime.now().strftime("%Y-%m-%d")
                pasillo = campos["pasillo"].text.strip() or "A"
                if not codigo or not nombre or not categoria:
                    mostrar_dialogo_simple("Datos incompletos", "Código, nombre y categoría son obligatorios.")
                    return
                gestor.ejecutar_comando(
                    "INSERT INTO productos (codigo_barras, nombre, categoria, cantidad_stock, fecha_vencimiento, pasillo, imagen) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (codigo, nombre, categoria, cantidad, fecha, pasillo, ""),
                )
                self.actualizar_metricas()
                mostrar_dialogo_simple("Producto agregado", f"{nombre} fue agregado correctamente en el pasillo {pasillo}.")
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
        try:
            reporte = ControladorReportes()
            pdf_path = reporte.exportar_pdf(tipo="movimientos", nombre_archivo="reporte_movimientos.pdf")
            excel_path = reporte.exportar_excel(tipo="movimientos", nombre_archivo="reporte_movimientos.xlsx")
            mostrar_dialogo_simple(
                "Reportes generados",
                f"PDF: {pdf_path}\nExcel: {excel_path}",
            )
        except Exception as exc:
            mostrar_dialogo_simple("Error al generar reportes", str(exc))

    def gestionar_proveedores(self):
        gestor = GestorBD()
        rows = gestor.listar_proveedores()
        if not rows:
            texto = "No existen proveedores registrados."
        else:
            texto = "\n".join(f"{nombre} | {telefono} | {correo}" for _, nombre, telefono, correo in rows)
        mostrar_dialogo_simple("Proveedores", texto)

    def escanear_codigo(self):
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
        Window.bind(on_key_down=self._on_keyboard_down)
        print("[ESCANER] Pantalla activa. Listo para recibir lectura por USB o simulación.")

    def on_leave(self, *args):
        Window.unbind(on_key_down=self._on_keyboard_down)

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

            if dias_restantes > 0:
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
            self.ids.lbl_dias_restantes.text = "Sin producto seleccionado"
            self.producto_actual = None

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

    def calcular_dias_restantes(self, fecha_vencimiento_str):
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
        Window.fullscreen = False
        Window.size = (1100, 700)
        Window.minimum_width = 900
        Window.minimum_height = 600
        Window.clearcolor = (0.95, 0.96, 0.96, 1)

        inicializar_bd()

        sm = MDScreenManager()
        sm.add_widget(PantallaInicioSesion(name="inicio_sesion"))
        sm.add_widget(PantallaRegistroGerente(name="registro_gerente"))
        sm.add_widget(PantallaRegistroEmpleado(name="registro_empleado"))
        sm.add_widget(PantallaPanelEmpleado(name="panel_empleado"))
        sm.add_widget(PantallaPanelGerente(name="panel_gerente"))
        sm.add_widget(PantallaEscaner(name="escaner"))

        return sm


if __name__ == "__main__":
    FreshControlApp().run()