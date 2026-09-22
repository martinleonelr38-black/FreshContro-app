import os
import sys

# Agregar la carpeta base al path para evitar errores de importación
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy.lang import Builder

# Importar funciones de base de datos
from base_de_datos.gestor_bd import inicializar_bd, registrar_usuario, verificar_credenciales

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

        usuario_db = verificar_credenciales(usuario, password)

        if usuario_db:
            label_error.text = ""
            self.ids.usuario_field.text = ""
            self.ids.password_field.text = ""
            
            rol = usuario_db["rol"].lower()
            if rol == "gerente":
                self.manager.current = "panel_gerente"
            elif rol == "empleado":
                self.manager.current = "panel_empleado"
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
        label_error = self.ids.mensaje_error
        nombre = self.ids.nombre_field.text.strip()
        apellido = self.ids.apellido_field.text.strip()
        usuario = self.ids.usuario_field.text.strip()
        password = self.ids.password_field.text.strip()
        confirm_password = self.ids.confirm_password_field.text.strip()
        email = self.ids.email_field.text.strip()
        telefono = self.ids.telefono_field.text.strip()

        if not all([nombre, apellido, usuario, password, confirm_password, email, telefono]):
            label_error.text = "Por favor complete todos los datos"
            return

        if password != confirm_password:
            label_error.text = "Las contraseñas no coinciden"
            return

        exito, msg = registrar_usuario(
            nombre, apellido, usuario, password, email, telefono, cargo="Gerente General", rol="gerente"
        )

        if exito:
            label_error.text = ""
            self.limpiar_campos()
            self.manager.current = "inicio_sesion"
        else:
            label_error.text = msg

    def limpiar_campos(self):
        self.ids.nombre_field.text = ""
        self.ids.apellido_field.text = ""
        self.ids.usuario_field.text = ""
        self.ids.password_field.text = ""
        self.ids.confirm_password_field.text = ""
        self.ids.email_field.text = ""
        self.ids.telefono_field.text = ""
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
        label_error = self.ids.mensaje_error
        nombre = self.ids.nombre_field.text.strip()
        apellido = self.ids.apellido_field.text.strip()
        usuario = self.ids.usuario_field.text.strip()
        password = self.ids.password_field.text.strip()
        confirm_password = self.ids.confirm_password_field.text.strip()
        email = self.ids.email_field.text.strip()
        telefono = self.ids.telefono_field.text.strip()
        cargo = self.ids.cargo_field.text.strip()

        if not all([nombre, apellido, usuario, password, confirm_password, email, telefono, cargo]):
            label_error.text = "Por favor complete todos los datos"
            return

        if password != confirm_password:
            label_error.text = "Las contraseñas no coinciden"
            return

        exito, msg = registrar_usuario(
            nombre, apellido, usuario, password, email, telefono, cargo=cargo, rol="empleado"
        )

        if exito:
            label_error.text = ""
            self.limpiar_campos()
            self.manager.current = "inicio_sesion"
        else:
            label_error.text = msg

    def limpiar_campos(self):
        self.ids.nombre_field.text = ""
        self.ids.apellido_field.text = ""
        self.ids.usuario_field.text = ""
        self.ids.password_field.text = ""
        self.ids.confirm_password_field.text = ""
        self.ids.email_field.text = ""
        self.ids.telefono_field.text = ""
        self.ids.cargo_field.text = ""
        if hasattr(self.ids, 'mensaje_error'):
            self.ids.mensaje_error.text = ""

    def ir_a_login(self):
        self.limpiar_campos()
        self.manager.current = "inicio_sesion"


class PantallaPanelEmpleado(MDScreen):
    def toggle_nav_drawer(self):
        pass

    def ir_a_escaner(self):
        self.manager.current = "escaner"

    def cerrar_sesion(self):
        self.manager.current = "inicio_sesion"


class PantallaPanelGerente(MDScreen):
    def toggle_nav_drawer(self):
        pass

    def ver_inventario(self):
        pass

    def agregar_producto(self):
        pass

    def gestionar_empleados(self):
        pass

    def ver_reportes(self):
        self.manager.current = "escaner"

    def cerrar_sesion(self):
        self.manager.current = "inicio_sesion"


class PantallaEscaner(MDScreen):
    def procesar_codigo(self):
        self.manager.current = "panel_gerente"

    def volver(self):
        self.manager.current = "panel_gerente"


class FreshControlApp(MDApp):
    def build(self):
        inicializar_bd()

        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"

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