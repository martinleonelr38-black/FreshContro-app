# FreshContro-app
# Proyecto de inventario y control de vencimientos para FreshControl.
# Sirve como guía de instalación, compilación y funcionamiento general del sistema.
"Sistema Inteligente de Gestión y Control de Vencimientos"

## Compilar para Android

La compilación se realiza desde Ubuntu o WSL2; no ejecutes Buildozer desde
PowerShell ni desde `/mnt/c`, porque el acceso a archivos de Windows puede
volver la compilación muy lenta o causar problemas de permisos. Estos pasos
usan la carpeta actual del proyecto en Windows; si la moviste, ajusta la ruta
del comando `cp`.

```bash
# 1. Instalar herramientas del sistema (Ubuntu 22.04 o 24.04)
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git zip unzip \
	openjdk-17-jdk build-essential autoconf automake libtool pkg-config \
	zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo6 cmake \
	libffi-dev libssl-dev

# 2. Copiar la app desde Windows al filesystem de Ubuntu/WSL2
mkdir -p ~/proyectos
cp -a "/mnt/c/Users/PC/Documents/carpeta proyecto/versiones de FreshControl/v.1.0.2 solucionado los probelmas/FreshControl 0.1.1/freshcontrol_app" \
	~/proyectos/FreshControl
cd ~/proyectos/FreshControl

# 3. Instalar Buildozer en un entorno virtual
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install "Cython==0.29.36" buildozer

# 4. Compilar el APK de depuración
buildozer android debug

# 5. Ver el APK generado
ls -lh bin/*.apk
```

Si usas Ubuntu instalado directamente, omite el paso 2 y abre la terminal en
la carpeta `freshcontrol_app` del proyecto antes de crear el entorno virtual.

La primera compilación descarga Android SDK/NDK y puede tardar bastante; acepta
las licencias cuando se solicite y mantén una conexión estable. El APK de
depuración queda en `~/proyectos/FreshControl/bin/` y está configurado para
`arm64-v8a`. Para instalarlo desde Ubuntu, conecta el dispositivo con la
depuración USB habilitada y ejecuta `sudo apt install adb` y luego
`adb install -r bin/*.apk`.

El paquete no incluye `client_secret.json` ni la base de datos local de
Windows. FreshControl crea una base nueva en el teléfono. El acceso con Google
no está configurado para Android; necesita un cliente OAuth Android y un flujo
de redirección adecuados antes de habilitarlo.

## Funciones de inventario

- El escaneo consulta Open Food Facts para sugerir nombre y categoría cuando el código aún no existe en el inventario. Requiere conexión a Internet; si no hay ficha disponible, permite continuar con el alta manual.
- El acceso con Google en escritorio requiere un cliente OAuth de tipo aplicación de escritorio en `freshcontrol_app/client_secret.json`. Ese archivo no se incluye en el APK. Para Android se debe configurar un cliente OAuth Android y su flujo de redirección en Google Cloud antes de habilitar ese acceso.
- Al marcar un producto como congelado, la fecha ingresada se extiende por categoría: carnes 6 meses, pescado 3, lácteos 2, frutas/verduras 8 y otras categorías 3. Si no se ingresa una fecha, se usa la fecha actual como base.
- El reporte mensual muestra productos vencidos, unidades y valor estimado al precio registrado; el valor es una estimación, no un ajuste contable.
