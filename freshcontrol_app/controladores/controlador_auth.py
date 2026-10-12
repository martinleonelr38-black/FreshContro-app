# Controlador de autenticación.
# Sirve para registrar usuarios y validar credenciales del login de empleados y gerentes.
from base_de_datos.gestor_bd import GestorBD, registrar_usuario, verificar_credenciales


class ControladorAuth:
    def __init__(self):
        self.bd = GestorBD()

    def registrar_usuario(self, nombre, apellido, usuario, password, email, telefono, cargo="Empleado", rol="empleado"):
        """Registra gerente o empleado usando la lógica central de la base de datos."""
        return registrar_usuario(nombre, apellido, usuario, password, email, telefono, cargo, rol)

    def verificar_login(self, usuario, password):
        """Valida usuario y contraseña en las tablas de gerente y empleado."""
        return verificar_credenciales(usuario, password)

    def registrar_empleado(self, nombre, cargo, usuario, contrasena):
        """Método legado para compatibilidad con versiones anteriores del proyecto."""
        return registrar_usuario(nombre, "", usuario, contrasena, "", "", cargo, "empleado")