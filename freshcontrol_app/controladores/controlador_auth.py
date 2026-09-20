from base_de_datos.gestor_bd import GestorBD

class ControladorAuth:
    def __init__(self):
        self.bd = GestorBD()

    def registrar_empleado(self, nombre, cargo, usuario, contrasena):
        """
        Registra un empleado o gerente en la base de datos.
        Retorna True si se guardó correctamente.
        """
        sql = """
            INSERT INTO empleados (nombre, cargo, usuario, contrasena)
            VALUES (?, ?, ?, ?)
        """
        return self.bd.ejecutar_comando(sql, (nombre, cargo, usuario, contrasena))

    def verificar_login(self, usuario, contrasena):
        """
        Valida las credenciales contra la tabla empleados.
        Retorna una tupla (id_empleado, nombre, cargo) si es correcto, o None si falla.
        """
        sql = """
            SELECT id_empleado, nombre, cargo 
            FROM empleados 
            WHERE usuario = ? AND contrasena = ?
        """
        resultados = self.bd.ejecutar_consulta(sql, (usuario, contrasena))
        if resultados:
            return resultados[0]  # Ejemplo: (1, 'Juan Perez', 'Gerente')
        return None