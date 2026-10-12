# Configuración de compilación para Android.
# Sirve para definir el nombre, dependencias, permisos y empaquetado de la app con Buildozer.
[app]
title = FreshControl
package.name = freshcontrol
package.domain = org.freshcontrol
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,webp,ttf,otf,atlas,txt
source.exclude_dirs = __pycache__, reportes
source.exclude_patterns = client_secret.json, *.db
version = 0.1.1
requirements = python3,kivy==2.2.1,kivymd==1.1.1,plyer==2.1.0,requests==2.31.0,reportlab==4.0.4,openpyxl==3.1.2,pyjnius
orientation = portrait
fullscreen = 0
android.api = 35
android.minapi = 23
android.ndk = 25b
android.ndk_api = 23
android.archs = arm64-v8a
android.permissions = CAMERA, INTERNET
android.gradle_dependencies = com.google.android.gms:play-services-code-scanner:16.1.0,com.google.mlkit:text-recognition:16.0.1
android.accept_sdk_license = True
p4a.bootstrap = sdl2
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 1
