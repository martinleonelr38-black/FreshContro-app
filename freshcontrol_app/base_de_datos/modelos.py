# Inicialización de la base de datos.
if __package__:
    from .gestor_bd import inicializar_bd
else:
    from gestor_bd import inicializar_bd


def inicializar_tablas():
    inicializar_bd()
    print("Base de datos inicializada con éxito y relaciones conectadas correctamente.")

if __name__ == "__main__":
    inicializar_tablas()