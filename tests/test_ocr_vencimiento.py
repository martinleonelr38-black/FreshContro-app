# Pruebas del OCR de vencimientos.
# Sirve para validar que la extracción de fechas sea precisa y rechace formatos inválidos.
import os
import sys
import unittest
from datetime import date

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "freshcontrol_app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from controladores.ocr_vencimiento import extraer_fecha_vencimiento


class TestOCRVencimiento(unittest.TestCase):
    def test_extrae_fecha_dia_primero_marcada(self):
        texto = "LOTE 04/05/2026 Vencimiento: 18/11/2026"
        self.assertEqual(
            extraer_fecha_vencimiento(texto, hoy=date(2026, 1, 1)),
            "2026-11-18",
        )

    def test_extrae_fecha_iso(self):
        self.assertEqual(
            extraer_fecha_vencimiento("Consumir antes de 2027-03-09", hoy=date(2026, 1, 1)),
            "2027-03-09",
        )

    def test_ignora_fechas_invalidas(self):
        self.assertIsNone(
            extraer_fecha_vencimiento("Vencimiento: 31/02/2027", hoy=date(2026, 1, 1))
        )


if __name__ == "__main__":
    unittest.main()