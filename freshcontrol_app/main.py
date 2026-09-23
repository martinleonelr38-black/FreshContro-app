import os
import sys

# Agregar la carpeta base al path para importar el gestor
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty

# Importar funciones del gestor de base de datos
from base_de_datos.gestor_bd import (
    inicializar_bd,
    registrar_usuario,
    verificar_credenciales,
    obtener_metricas_dashboard
)

# Cargar archivos KV
VISTAS_DIR = os.path.join(APP_DIR, "vistas")
Builder.load_file(os.path.join(VISTAS_DIR, "inicio_sesion.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "escaner.kv"))


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

        # Consultar credenciales en SQLite
        usuario_db = verificar_credenciales(usuario, password)

        if usuario_db:
            label_error.text = ""
            self.ids.usuario_field.text = ""
            self.ids.password_field.text = ""

            # Guardar el usuario en la app global
            app = MDApp.get_running_app()
            app.usuario_activo = dict(usuario_db)

            # Redirección según el ROL guardado en la BD
            rol = usuario_db["rol"].lower()
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

    def on_pre_enter(self, *args):
        app = MDApp.get_running_app()
        if app.usuario_activo:
            self.nombre_empleado = f"{app.usuario_activo.get('nombre', '')} {app.usuario_activo.get('apellido', '')}"

    def ir_a_escaner(self):
        self.manager.current = "escaner"

    def cerrar_sesion(self):
        MDApp.get_running_app().usuario_activo = {}
        self.manager.current = "inicio_sesion"


class PantallaPanelGerente(MDScreen):
    total_productos = NumericProperty(0)
    stock_bajo = NumericProperty(0)
    por_vencer = NumericProperty(0)
    vencidos = NumericProperty(0)
    nombre_gerente = StringProperty("Gerente")

    def on_pre_enter(self, *args):
        app = MDApp.get_running_app()
        if app.usuario_activo:
            self.nombre_gerente = f"{app.usuario_activo.get('nombre', '')} {app.usuario_activo.get('apellido', '')}"

        metricas = obtener_metricas_dashboard()
        self.total_productos = metricas["total_productos"]
        self.stock_bajo = metricas["stock_bajo"]
        self.por_vencer = metricas["por_vencer"]
        self.vencidos = metricas["vencidos"]

    def cerrar_sesion(self):
        MDApp.get_running_app().usuario_activo = {}
        self.manager.current = "inicio_sesion"


class PantallaEscaner(MDScreen):
    pass


class FreshControlApp(MDApp):
    usuario_activo = {}

    def build(self):
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