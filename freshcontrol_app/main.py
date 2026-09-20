import os
import sys

# Agregar ruta base para asegurar importaciones
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from base_de_datos.modelos import inicializar_tablas
from controladores.controlador_auth import ControladorAuth

class LoginScreen(MDScreen):
    pass

class RegistroGerenteScreen(MDScreen):
    pass

class RegistroEmpleadoScreen(MDScreen):
    pass

class PanelGerenteScreen(MDScreen):
    pass

class PanelEmpleadoScreen(MDScreen):
    pass

class FreshControlApp(MDApp):
    usuario_actual = None  # Guarda (id_empleado, nombre, cargo)

    def build(self):
        self.theme_cls.primary_palette = "Green"
        
        # Inicializar tablas de SQLite al iniciar
        inicializar_tablas()
        
        # Instanciar controlador de autenticación
        self.auth = ControladorAuth()

        # Cargar vistas KV
        vistas_dir = os.path.join(BASE_DIR, "vistas")
        kv_files = [
            "inicio_sesion.kv",
            "registro_gerente.kv",
            "registro_empleado.kv",
            "panel_gerente.kv",
            "panel_empleado.kv"
        ]

        for file_name in kv_files:
            file_path = os.path.join(vistas_dir, file_name)
            if os.path.exists(file_path):
                Builder.load_file(file_path)

        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(RegistroGerenteScreen(name='registro_gerente'))
        sm.add_widget(RegistroEmpleadoScreen(name='registro_empleado'))
        sm.add_widget(PanelGerenteScreen(name='panel_gerente'))
        sm.add_widget(PanelEmpleadoScreen(name='panel_empleado'))

        return sm

    def iniciar_sesion(self, usuario, contrasena):
        datos_usuario = self.auth.verificar_login(usuario, contrasena)
        if datos_usuario:
            self.usuario_actual = datos_usuario
            cargo = datos_usuario[2].lower()
            if "gerente" in cargo or "admin" in cargo:
                self.root.current = 'panel_gerente'
            else:
                self.root.current = 'panel_empleado'
            print(f"Bienvenido {datos_usuario[1]} ({datos_usuario[2]})")
        else:
            print("Error: Usuario o contraseña incorrectos")

    def registrar_usuario(self, nombre, cargo, usuario, contrasena):
        exito = self.auth.registrar_empleado(nombre, cargo, usuario, contrasena)
        if exito:
            print("Usuario registrado exitosamente.")
            self.root.current = 'login'
        else:
            print("Error al registrar el usuario.")

if __name__ == '__main__':
    FreshControlApp().run()