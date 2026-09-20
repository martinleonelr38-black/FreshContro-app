import os
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy.lang import Builder

# Importar/Cargar los archivos .kv de la carpeta vistas
VISTAS_DIR = os.path.join(os.path.dirname(__file__), "vistas")

Builder.load_file(os.path.join(VISTAS_DIR, "inicio_sesion.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "registro_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_empleado.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "panel_gerente.kv"))
Builder.load_file(os.path.join(VISTAS_DIR, "escaner.kv"))


# Definición de Clases para cada Pantalla
class InicioSesionVista(MDScreen):
    def iniciar_sesion(self):
        # Lógica temporal de navegación
        self.manager.current = "panel_gerente"

    def ir_a_registro_gerente(self):
        self.manager.current = "registro_gerente"

    def ir_a_registro_empleado(self):
        self.manager.current = "registro_empleado"


class RegistroGerenteVista(MDScreen):
    def guardar_gerente(self):
        self.manager.current = "inicio_sesion"

    def ir_a_login(self):
        self.manager.current = "inicio_sesion"


class RegistroEmpleadoVista(MDScreen):
    def guardar_empleado(self):
        self.manager.current = "inicio_sesion"

    def ir_a_login(self):
        self.manager.current = "inicio_sesion"


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
        pass


class EscanerVista(MDScreen):
    def procesar_codigo(self):
        self.manager.current = "panel_empleado"

    def volver(self):
        self.manager.current = "inicio_sesion"


# Aplicación Principal
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