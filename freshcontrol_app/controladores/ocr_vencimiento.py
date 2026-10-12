# Lógica de OCR para fechas de vencimiento.
# Sirve para detectar fechas en imágenes y sugerirlas automáticamente al registrar productos.
import re
import unicodedata
from datetime import date


_PATRON_ISO = re.compile(r"(?<!\d)(\d{4})[./-](\d{1,2})[./-](\d{1,2})(?!\d)")
_PATRON_DIA_PRIMERO = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})(?!\d)")
_MARCADORES_VENCIMIENTO = (
    "vence",
    "vencimiento",
    "caducidad",
    "expiry",
    "expiration",
    "best before",
    "use by",
)
_LISTENERS_OCR = []


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").casefold())
    return "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")


def extraer_fecha_vencimiento(texto, hoy=None):
    """Devuelve una fecha ISO sugerida a partir del texto de una etiqueta."""
    hoy = hoy or date.today()
    candidatos = []
    texto = str(texto or "")

    for patron, orden in ((_PATRON_ISO, "iso"), (_PATRON_DIA_PRIMERO, "dia")):
        for coincidencia in patron.finditer(texto):
            valores = [int(valor) for valor in coincidencia.groups()]
            if orden == "iso":
                anio, mes, dia = valores
            else:
                dia, mes, anio = valores
                if anio < 100:
                    anio += 2000
            try:
                fecha = date(anio, mes, dia)
            except ValueError:
                continue

            contexto = _normalizar(texto[max(0, coincidencia.start() - 45):coincidencia.end() + 20])
            marcada = any(marcador in contexto for marcador in _MARCADORES_VENCIMIENTO)
            candidatos.append((marcada, fecha))

    if not candidatos:
        return None

    marcados = [fecha for marcada, fecha in candidatos if marcada]
    fechas_futuras = [fecha for _, fecha in candidatos if fecha >= hoy]
    seleccion = marcados or fechas_futuras or [fecha for _, fecha in candidatos]
    return max(seleccion).isoformat()


def leer_fecha_en_imagen(ruta_imagen, al_completar):
    """Reconoce texto en una imagen Android y devuelve una fecha ISO sugerida."""
    try:
        from kivy.utils import platform

        if platform != "android":
            al_completar(None, "La lectura automática de fecha está disponible en Android.")
            return

        from jnius import PythonJavaClass, autoclass, java_method
        from kivy.clock import Clock

        bitmap = autoclass("android.graphics.BitmapFactory").decodeFile(ruta_imagen)
        if bitmap is None:
            raise ValueError("No se pudo abrir la fotografía.")

        InputImage = autoclass("com.google.mlkit.vision.common.InputImage")
        imagen = InputImage.fromBitmap(bitmap, 0)
        opciones = autoclass(
            "com.google.mlkit.vision.text.latin.TextRecognizerOptions"
        ).DEFAULT_OPTIONS
        reconocedor = autoclass("com.google.mlkit.vision.text.TextRecognition").getClient(opciones)
        tarea = reconocedor.process(imagen)

        class OCRCorrecto(PythonJavaClass):
            __javainterfaces__ = ["com/google/android/gms/tasks/OnSuccessListener"]
            __javacontext__ = "app"

            @java_method("(Ljava/lang/Object;)V")
            def onSuccess(self, resultado):
                texto = str(resultado.getText() or "")
                fecha = extraer_fecha_vencimiento(texto)
                mensaje = None if fecha else "No se detectó una fecha; puedes ingresarla manualmente."
                Clock.schedule_once(lambda _dt: al_completar(fecha, mensaje), 0)
                limpiar_listeners()

        class OCRFallido(PythonJavaClass):
            __javainterfaces__ = ["com/google/android/gms/tasks/OnFailureListener"]
            __javacontext__ = "app"

            @java_method("(Ljava/lang/Exception;)V")
            def onFailure(self, error):
                mensaje = str(error or "No se pudo leer la fotografía.")
                Clock.schedule_once(lambda _dt: al_completar(None, mensaje), 0)
                limpiar_listeners()

        correcto = OCRCorrecto()
        fallido = OCRFallido()
        referencias = (correcto, fallido)
        _LISTENERS_OCR.append(referencias)

        def limpiar_listeners():
            if referencias in _LISTENERS_OCR:
                _LISTENERS_OCR.remove(referencias)

        tarea.addOnSuccessListener(correcto)
        tarea.addOnFailureListener(fallido)
    except Exception as exc:
        al_completar(None, str(exc))