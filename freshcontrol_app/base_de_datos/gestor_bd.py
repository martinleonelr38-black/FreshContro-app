import sqlite3
import os

class GestorBD:
    def __init__(self, nombre_bd="freshcontrol.db"):
        ruta_base = os.path.dirname(os.path.abspath(__file__))
        self.ruta_bd = os.path.join(ruta_base, nombre_bd)

    def conectar(self):
        conn = sqlite3.connect(self.ruta_bd)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def ejecutar_comando(self, sql, parametros=()):
        try:
            with self.conectar() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, parametros)
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error SQL: {e}")
            return False

    def ejecutar_consulta(self, sql, parametros=()):
        try:
            with self.conectar() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, parametros)
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error SQL: {e}")
            return []