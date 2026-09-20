import os
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineIconListItem, IconLeftWidget
from kivy.lang import Builder

# Cargar cada vista una sola vez especificando la ruta exacta
VISTAS_DIR = os.path.join(os.path.dirname(__file__), "vistas")

# Usamos Builder.load_file para Registrar las reglas Kivy
Builder.load_file(os.path.join(VISTAS_DIR, "inicio_sesion.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "escaner.kv"))


class InicioSesionVista(MDScreen):
    def toggle_password_visibility(self, button, field):
        """Alterna visibilidad de contraseña con el ícono de ojo."""
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def iniciar_sesion(self):
        usuario = self.ids.usuario_field.text.strip()
        password = self.ids.password_field.text.strip()
        label_error = self.ids.mensaje_error

        # Control de campos vacíos
        if not usuario or not password:
            label_error.text = "Por favor ingrese usuario y contraseña"
            return

        # Control estricto de credenciales y roles
        if usuario == "gerente" and password == "1234":
            label_error.text = ""
            # Limpiar campos al entrar
            self.ids.usuario_field.text = ""
            self.ids.password_field.text = ""
            self.manager.current = "panel_gerente"
        elif usuario == "empleado" and password == "1234":
            label_error.text = ""
            self.ids.usuario_field.text = ""
            self.ids.password_field.text = ""
            self.manager.current = "panel_empleado"
        else:
            # Si los datos no coinciden exactamente, BLOQUEA el acceso y muestra el error
            label_error.text = "Usuario o contraseña incorrectos"


class RegistroGerenteVista(MDScreen):
    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def guardar_gerente(self):
        self.manager.current = "inicio_sesion"

    def ir_a_login(self):
        self.manager.current = "inicio_sesion"


class RegistroEmpleadoVista(MDScreen):
    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def guardar_empleado(self):
        self.manager.current = "inicio_sesion"

    def ir_a_login(self):
        self.manager.current = "inicio_sesion"


class PanelEmpleadoVista(MDScreen):
    def toggle_nav_drawer(self):
        pass

    def ir_a_escaner(self):
        self.manager.current = "escaner"

    def cerrar_sesion(self):
        self.manager.current = "inicio_sesion"


class PanelGerenteVista(MDScreen):
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


class EscanerVista(MDScreen):
    def procesar_codigo(self):
        self.manager.current = "panel_gerente"

    def volver(self):
        self.manager.current = "panel_gerente"


class FreshControlApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"

        sm = MDScreenManager()
        # Se instancian las pantallas asignando sus nombres únicos
        sm.add_widget(InicioSesionVista(name="inicio_sesion"))
        sm.add_widget(RegistroGerenteVista(name="registro_gerente"))
        sm.add_widget(RegistroEmpleadoVista(name="registro_empleado"))
        sm.add_widget(PanelEmpleadoVista(name="panel_empleado"))
        sm.add_widget(PanelGerenteVista(name="panel_gerente"))
        sm.add_widget(EscanerVista(name="escaner"))

        return sm


if __name__ == "__main__":
    FreshControlApp().run()