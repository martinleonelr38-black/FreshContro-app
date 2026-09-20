import os
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineIconListItem, IconLeftWidget
from kivy.lang import Builder

# Importar/Cargar los archivos .kv de la carpeta vistas
VISTAS_DIR = os.path.join(os.path.dirname(__file__), "vistas")

Builder.load_file(os.path.join(VISTAS_DIR, "inicio_sesion.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "escaner.kv"))


# ==========================================
# Pantalla: Inicio de Sesión
# ==========================================
class InicioSesionVista(MDScreen):
    def toggle_password_visibility(self, button, field):
        """Alterna la visibilidad del texto en el campo de contraseña."""
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def iniciar_sesion(self):
        usuario = self.ids.usuario_field.text.strip()
        password = self.ids.password_field.text.strip()
        label_error = self.ids.mensaje_error

        # Validación básica de campos vacíos
        if not usuario or not password:
            label_error.text = "Por favor ingrese usuario y contraseña"
            return

        # Control y derivación de roles (Simulación temporal de BD)
        if usuario == "gerente" and password == "1234":
            label_error.text = ""
            self.manager.current = "panel_gerente"
        elif usuario == "empleado" and password == "1234":
            label_error.text = ""
            self.manager.current = "panel_empleado"
        else:
            label_error.text = "Usuario o contraseña incorrectos"

    def ir_a_registro_gerente(self):
        self.manager.current = "registro_gerente"

    def ir_a_registro_empleado(self):
        self.manager.current = "registro_empleado"


# ==========================================
# Pantalla: Registro Gerente
# ==========================================
class RegistroGerenteVista(MDScreen):
    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def guardar_gerente(self):
        # Redireccionar al login tras guardar
        self.manager.current = "inicio_sesion"

    def ir_a_login(self):
        self.manager.current = "inicio_sesion"


# ==========================================
# Pantalla: Registro Empleado
# ==========================================
class RegistroEmpleadoVista(MDScreen):
    def toggle_password_visibility(self, button, field):
        field.password = not field.password
        button.icon = "eye" if not field.password else "eye-off"

    def guardar_empleado(self):
        self.manager.current = "inicio_sesion"

    def ir_a_login(self):
        self.manager.current = "inicio_sesion"


# ==========================================
# Pantalla: Panel Empleado
# ==========================================
class PanelEmpleadoVista(MDScreen):
    def toggle_nav_drawer(self):
        pass

    def registrar_entrada(self):
        pass

    def registrar_salida(self):
        pass

    def ir_a_escaner(self):
        self.manager.current = "escaner"

    def buscar_producto(self):
        pass

    def cerrar_sesion(self):
        self.manager.current = "inicio_sesion"


# ==========================================
# Pantalla: Panel Gerente
# ==========================================
class PanelGerenteVista(MDScreen):
    def toggle_nav_drawer(self):
        pass

    def ver_inventario(self):
        print("Navegando a Inventario...")

    def agregar_producto(self):
        print("Navegando a Agregar Producto...")

    def gestionar_empleados(self):
        print("Navegando a Gestión de Empleados...")

    def ver_reportes(self):
        self.manager.current = "escaner"

    def cerrar_sesion(self):
        self.manager.current = "inicio_sesion"


# ==========================================
# Pantalla: Escáner
# ==========================================
class EscanerVista(MDScreen):
    def procesar_codigo(self):
        self.manager.current = "panel_gerente"

    def volver(self):
        self.manager.current = "panel_gerente"


# ==========================================
# Aplicación Principal
# ==========================================
class FreshControlApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"

        sm = MDScreenManager()
        sm.add_widget(InicioSesionVista(name="inicio_sesion"))
        sm.add_widget(RegistroGerenteVista(name="registro_gerente"))
        sm.add_widget(RegistroEmpleadoVista(name="registro_empleado"))
        sm.add_widget(PanelEmpleadoVista(name="panel_empleado"))
        sm.add_widget(PanelGerenteVista(name="panel_gerente"))
        sm.add_widget(EscanerVista(name="escaner"))

        return sm


if __name__ == "__main__":
    FreshControlApp().run()