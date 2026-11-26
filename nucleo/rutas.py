# -*- coding: utf-8 -*-
"""Seudónimo · carpetas de la aplicación según el sistema (Windows o Mac).

Los datos de trabajo (base de datos, copias inmutables, temporales) van a la carpeta de
datos de la aplicación del usuario, nunca a una carpeta sincronizada con la nube. Los
resultados se guardan por defecto en «~/Seudónimo», fuera de Documentos y Escritorio,
que en muchos equipos están sincronizados con iCloud u OneDrive.

Hasta la versión 0.1 la aplicación se llamaba «Áurea Asistente Local»: al arrancar por primera
vez con el nombre nuevo, sus carpetas se trasladan (ver `migrar`)."""
import os
import sqlite3
import subprocess
import sys

ES_WINDOWS = sys.platform.startswith("win")
ES_MAC = sys.platform == "darwin"
APP = os.path.dirname(os.path.abspath(__file__))
NOMBRE = "Seudónimo"


def _carpeta_datos(nombre):
    if ES_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(base, nombre)
    if ES_MAC:
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", nombre)
    return os.path.join(os.path.expanduser("~"), "." + nombre.lower())


def _datos():
    return os.environ.get("SEUDONIMO_DATOS") or _carpeta_datos("Seudonimo")


DATOS = _datos()
TRABAJO = os.path.join(DATOS, "trabajo")          # temporales del OCR y de cada pasada
PROYECTOS = os.path.join(DATOS, "proyectos")      # copias inmutables y tablas cifradas, por proyecto
BASE_DATOS = os.path.join(DATOS, "seudonimo.sqlite3")
REGISTRO = os.path.join(DATOS, "registro.log")    # sin texto de documentos: solo eventos técnicos
SALIDAS = os.environ.get("SEUDONIMO_SALIDAS") or os.path.join(os.path.expanduser("~"), "Seudónimo")

# Programas incluidos en el instalador (Windows: Tesseract; Mac: nada extra)
RAIZ = os.environ.get("SEUDONIMO_RAIZ") or os.path.dirname(APP)
TESSERACT_INCLUIDO = os.path.join(RAIZ, "tesseract", "tesseract.exe" if ES_WINDOWS else "tesseract")

SIN_VENTANA = 0x08000000 if ES_WINDOWS else 0  # que ningún auxiliar abra una consola en Windows

# Rastros habituales de carpetas sincronizadas con servicios en la nube
_NUBE = ("icloud", "mobile documents", "onedrive", "dropbox", "google drive", "googledrive",
         "cloudstorage", "box sync", "pcloud", "mega")


def migrar():
    """Traslada los datos de «Áurea Asistente Local» (0.1.x) si aún no hay datos de Seudónimo.
    Solo mueve carpetas dentro del mismo disco (no copia nada) y nunca sobrescribe."""
    hecho = []
    if os.environ.get("SEUDONIMO_DATOS"):
        return hecho
    viejo = _carpeta_datos("AureaAsistente") if (ES_WINDOWS or ES_MAC) else os.path.join(os.path.expanduser("~"), ".aurea-asistente")
    if os.path.isdir(viejo) and not os.path.exists(DATOS):
        try:
            os.rename(viejo, DATOS)
            hecho.append("datos")
        except OSError:
            return hecho
    bd_vieja = os.path.join(DATOS, "aurea.sqlite3")
    if os.path.isfile(bd_vieja) and not os.path.exists(BASE_DATOS):
        for suf in ("", "-wal", "-shm"):
            if os.path.exists(bd_vieja + suf):
                os.rename(bd_vieja + suf, BASE_DATOS + suf)
        hecho.append("base de datos")
    salidas_viejas = os.path.join(os.path.expanduser("~"), "Áurea Asistente")
    if not os.environ.get("SEUDONIMO_SALIDAS") and os.path.isdir(salidas_viejas) and not os.path.exists(SALIDAS):
        try:
            os.rename(salidas_viejas, SALIDAS)
            hecho.append("resultados")
            if os.path.isfile(BASE_DATOS):     # las rutas guardadas que apuntaban a la carpeta vieja
                c = sqlite3.connect(BASE_DATOS)
                for tabla, col in (("proyectos", "salida"), ("trabajos", "destino")):
                    c.execute("UPDATE %s SET %s = ? || substr(%s, ?) WHERE substr(%s, 1, ?) = ?" % (tabla, col, col, col),
                              (SALIDAS, len(salidas_viejas) + 1, len(salidas_viejas), salidas_viejas))
                c.commit()
                c.close()
        except (OSError, sqlite3.Error):
            pass
    return hecho


def preparar():
    migrar()
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
