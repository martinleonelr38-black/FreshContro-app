# Inicializa el paquete de base de datos.
# Sirve para exportar funciones de acceso a datos sin duplicar imports en el resto de la app.
from .gestor_bd import inicializar_bd, registrar_usuario, verificar_credenciales

__all__ = ["inicializar_bd", "registrar_usuario", "verificar_credenciales"]