import os
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy.lang import Builder

# Definir la ruta directa a la carpeta vistas
VISTAS_DIR = os.path.join(os.path.dirname(__file__), "vistas")

# Cargar explícitamente cada vista una sola vez
Builder.load_file(os.path.join(VISTAS_DIR, "inicio_sesion.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "escaner.kv"))


# Usamos nombres de clase distintos al nombre del archivo para evitar el auto-load de Kivy
class PantallaInicioSesion(MDScreen):
    def toggle_password_visibility(self, button, field):
        """Alterna visibilidad de la contraseña con el ojito."""
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

        # Control y bloqueo de credenciales
        if usuario == "gerente" and password == "1234":
            label_error.text = ""
            self.ids.usuario_field.text = ""
            self.ids.password_field.text = ""
            self.manager.current = "panel_gerente"
        elif usuario == "empleado" and password == "1234":
            label_error.text = ""
            self.ids.usuario_field.text = ""
            self.ids.password_field.text = ""
            self.manager.current = "panel_empleado"
        else:
            # Bloqueo por contraseña/usuario incorrecto
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
        self.manager.current = "inicio_sesion"

    def ir_a_login(self):
        self.manager.current = "inicio_sesion"


class PantallaRegistroEmpleado(MDScreen):
    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def guardar_empleado(self):
        self.manager.current = "inicio_sesion"

    def ir_a_login(self):
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