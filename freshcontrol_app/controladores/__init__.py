# Agrupa los controladores del sistema.
# Sirve para importar las clases principales desde un único punto y mantener la app ordenada.
from .controlador_auth import ControladorAuth
from .controlador_inventario import ControladorInventario
from .controlador_escaner import ControladorEscaner
from .controlador_reportes import ControladorReportes

__all__ = [
    "ControladorAuth",
    "ControladorInventario",
    "ControladorEscaner",
    "ControladorReportes",
]