# -*- coding: utf-8 -*-
"""Áurea Asistente Local · carpetas de la aplicación según el sistema (Windows o Mac).

Los datos de trabajo (base de datos, copias inmutables, temporales) van a la carpeta de
datos de la aplicación del usuario, nunca a una carpeta sincronizada con la nube. Los
resultados se guardan por defecto en «~/Áurea Asistente», fuera de Documentos y Escritorio,
que en muchos equipos están sincronizados con iCloud u OneDrive."""
import os
import subprocess
import sys

ES_WINDOWS = sys.platform.startswith("win")
ES_MAC = sys.platform == "darwin"
APP = os.path.dirname(os.path.abspath(__file__))
NOMBRE = "Áurea Asistente Local"


def _datos():
    if os.environ.get("AUREA_DATOS"):
        return os.environ["AUREA_DATOS"]
    if ES_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(base, "AureaAsistente")
    if ES_MAC:
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "AureaAsistente")
    return os.path.join(os.path.expanduser("~"), ".aurea-asistente")


DATOS = _datos()
TRABAJO = os.path.join(DATOS, "trabajo")          # temporales del OCR y de cada pasada
PROYECTOS = os.path.join(DATOS, "proyectos")      # copias inmutables y tablas cifradas, por proyecto
BASE_DATOS = os.path.join(DATOS, "aurea.sqlite3")
REGISTRO = os.path.join(DATOS, "registro.log")    # sin texto de documentos: solo eventos técnicos
SALIDAS = os.environ.get("AUREA_SALIDAS") or os.path.join(os.path.expanduser("~"), "Áurea Asistente")

# Programas incluidos en el instalador (Windows: Tesseract; Mac: nada extra)
RAIZ = os.environ.get("AUREA_RAIZ") or os.path.dirname(APP)
TESSERACT_INCLUIDO = os.path.join(RAIZ, "tesseract", "tesseract.exe" if ES_WINDOWS else "tesseract")

SIN_VENTANA = 0x08000000 if ES_WINDOWS else 0  # que ningún auxiliar abra una consola en Windows

# Rastros habituales de carpetas sincronizadas con servicios en la nube
_NUBE = ("icloud", "mobile documents", "onedrive", "dropbox", "google drive", "googledrive",
         "cloudstorage", "box sync", "pcloud", "mega")


def preparar():
    for c in (DATOS, TRABAJO, PROYECTOS):
        os.makedirs(c, exist_ok=True)


def sincronizada(ruta):
    """True si la ruta parece estar dentro de una carpeta sincronizada con la nube."""
    r = os.path.realpath(ruta).lower()
    if any(n in r for n in _NUBE):
        return True
    if ES_MAC:
        # «Escritorio y Documentos en iCloud»: ~/Documents y ~/Desktop pasan a ser enlaces
        for d in ("Documents", "Desktop"):
            base = os.path.join(os.path.expanduser("~"), d)
            if r.startswith(os.path.realpath(base).lower()) and "mobile documents" in os.path.realpath(base).lower():
                return True
    return False


def ejecutar(args, **kw):
    kw.setdefault("capture_output", True)
    if ES_WINDOWS:
        kw.setdefault("creationflags", SIN_VENTANA)
    return subprocess.run(args, **kw)


def abrir_carpeta(ruta):
    if ES_WINDOWS:
        os.startfile(ruta)  # noqa
    elif ES_MAC:
        subprocess.run(["open", ruta])
    else:
        subprocess.run(["xdg-open", ruta])
