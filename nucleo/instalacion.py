# -*- coding: utf-8 -*-
"""Seudónimo · puesta en marcha y gestión de modelos.

Comprueba que Ollama (el programa que ejecuta los modelos en el propio ordenador) está
instalado y en marcha. Si falta, lo descarga de su web oficial y lo instala. Los modelos se
descargan solo cuando el usuario los elige, con comprobación previa de espacio en disco.
Después todo funciona sin conexión a internet."""
import json
import os
import shutil
import subprocess
import threading
import time

import requests

import proveedores
import rutas

URL_OLLAMA_WINDOWS = "https://ollama.com/download/OllamaSetup.exe"
URL_OLLAMA_MAC = "https://ollama.com/download/Ollama-darwin.zip"

ESTADO = {"fase": "inactivo", "mensaje": "", "progreso": 0.0, "error": None}
_CERROJO = threading.Lock()
_hilo = None


# ---------------------------------------------------------------- dónde está Ollama

def _local():
    return os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")


def app_ollama():
    """La aplicación de Ollama (la que se queda junto al reloj y arranca el servidor)."""
    if rutas.ES_WINDOWS:
        c = os.path.join(_local(), "Programs", "Ollama", "ollama app.exe")
        return c if os.path.isfile(c) else None
    if rutas.ES_MAC:
        for c in ("/Applications/Ollama.app", os.path.expanduser("~/Applications/Ollama.app")):
            if os.path.isdir(c):
                return c
    return None


def cli_ollama():
    candidatos = []
    if rutas.ES_WINDOWS:
        candidatos.append(os.path.join(_local(), "Programs", "Ollama", "ollama.exe"))
    if rutas.ES_MAC:
        for a in ("/Applications/Ollama.app", os.path.expanduser("~/Applications/Ollama.app")):
            candidatos.append(os.path.join(a, "Contents", "Resources", "ollama"))
        candidatos += ["/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"]
    candidatos.append(shutil.which("ollama") or "")
    for c in candidatos:
        if c and os.path.isfile(c):
            return c
    return None


def instalado():
    return bool(app_ollama() or cli_ollama())


def activo():
    try:
        return proveedores.actual().disponible()
    except Exception:
        return False


def comprobar():
    act = activo()
    datos = {"instalado": instalado() or act, "activo": act}
    datos.update({k: ESTADO[k] for k in ("fase", "mensaje", "progreso", "error")})
    return datos


def _poner(**kw):
    with _CERROJO:
        ESTADO.update(kw)


def arrancar_ollama(espera=60):
    """Pone Ollama en marcha si no lo está. Devuelve True si responde."""
    if activo():
        return True
    app, cli = app_ollama(), cli_ollama()
    try:
        if rutas.ES_WINDOWS:
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            if app:
                subprocess.Popen([app], creationflags=flags, close_fds=True)
            elif cli:
                subprocess.Popen([cli, "serve"], creationflags=flags | rutas.SIN_VENTANA, close_fds=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif rutas.ES_MAC and app:
            subprocess.run(["open", "-g", "-a", app])
        elif cli:
            subprocess.Popen([cli, "serve"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    fin = time.time() + espera
    while time.time() < fin:
        if activo():
            return True
        time.sleep(1)
    return False


def _gb(n):
    return ("%.1f" % (n / 1e9)).replace(".", ",")


def _descargar(url, destino, texto, p0, p1):
    with requests.get(url, stream=True, timeout=60, allow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        hecho = 0
        with open(destino + ".parcial", "wb") as f:
            for trozo in r.iter_content(1 << 20):
                f.write(trozo)
                hecho += len(trozo)
                frac = hecho / total if total else 0
                _poner(progreso=p0 + (p1 - p0) * frac,
                       mensaje="%s (%s de %s GB)" % (texto, _gb(hecho), _gb(total)) if total else texto)
    os.replace(destino + ".parcial", destino)


def _instalar_ollama():
    carpeta = os.path.join(rutas.DATOS, "descargas")
    os.makedirs(carpeta, exist_ok=True)
    if rutas.ES_WINDOWS:
        exe = os.path.join(carpeta, "OllamaSetup.exe")
        _descargar(URL_OLLAMA_WINDOWS, exe, "Descargando Ollama, el motor de la IA", 0.0, 0.12)
        _poner(mensaje="Instalando Ollama… (un minuto, no cierres esta ventana)", progreso=0.12)
        subprocess.run([exe, "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES", "/SP-"],
                       timeout=1800, creationflags=rutas.SIN_VENTANA)
    elif rutas.ES_MAC:
        zipf = os.path.join(carpeta, "Ollama-darwin.zip")
        _descargar(URL_OLLAMA_MAC, zipf, "Descargando Ollama, el motor de la IA", 0.0, 0.12)
        _poner(mensaje="Instalando Ollama…", progreso=0.12)
        destino = "/Applications" if os.access("/Applications", os.W_OK) else os.path.expanduser("~/Applications")
        os.makedirs(destino, exist_ok=True)
        # «ditto» conserva la firma de Apple de la aplicación de Ollama
        subprocess.run(["/usr/bin/ditto", "-x", "-k", zipf, destino], check=True, timeout=600)
    else:
        raise RuntimeError("Instala Ollama desde https://ollama.com y vuelve a abrir la aplicación.")
    try:
        shutil.rmtree(carpeta, ignore_errors=True)
    except Exception:
        pass
    if not instalado():
        raise RuntimeError("No he podido instalar Ollama. Descárgalo de https://ollama.com e instálalo a mano.")


DESCARGAS = {}   # modelo -> {"fase", "progreso", "mensaje", "error"}


def espacio_libre_gb():
    base = os.path.expanduser("~/.ollama") if not rutas.ES_WINDOWS else os.path.join(os.path.expanduser("~"), ".ollama")
    while not os.path.exists(base):
        base = os.path.dirname(base)
    return shutil.disk_usage(base).free / 1e9


def descargar_modelo(nombre, gb_estimados=None):
    """Descarga un modelo elegido por el usuario (nunca por iniciativa de la aplicación)."""
    if DESCARGAS.get(nombre, {}).get("fase") == "trabajando":
        return False
    if gb_estimados and espacio_libre_gb() < gb_estimados + 5:
        DESCARGAS[nombre] = {"fase": "error", "progreso": 0, "mensaje": "",
                             "error": "No hay espacio suficiente: hacen falta unos %s GB libres." % _gb((gb_estimados + 5) * 1e9)}
        return False
    DESCARGAS[nombre] = {"fase": "trabajando", "progreso": 0.0, "mensaje": "Empezando la descarga…", "error": None}

    def hilo():
        def avance(hecho, total, estado):
            d = DESCARGAS[nombre]
            if total:
                d["progreso"] = min(0.99, hecho / total)
                d["mensaje"] = "Descargando %s (%s de %s GB)" % (nombre, _gb(hecho), _gb(total))
            elif "verifying" in estado:
                d["mensaje"] = "Comprobando la integridad de la descarga…"
            elif estado:
                d["mensaje"] = estado
        try:
            if not arrancar_ollama():
                raise RuntimeError("Ollama no arranca. Ábrelo y vuelve a intentarlo.")
            proveedores.actual().descargar(nombre, avance)
            DESCARGAS[nombre].update(fase="listo", progreso=1.0, mensaje="Descargado.")
        except requests.exceptions.ConnectionError:
            DESCARGAS[nombre].update(fase="error", error="Sin conexión a internet: la descarga se reanuda donde se quedó al volver a intentarlo.")
        except Exception as e:  # noqa
            DESCARGAS[nombre].update(fase="error", error=str(e) or "Error inesperado en la descarga.")
    threading.Thread(target=hilo, daemon=True).start()
    return True


def _preparar():
    try:
        _poner(fase="trabajando", error=None, progreso=0.0, mensaje="Comprobando el equipo…")
        if not activo() and not instalado():
            _instalar_ollama()
        _poner(mensaje="Poniendo en marcha Ollama…", progreso=max(ESTADO["progreso"], 0.13))
        if not arrancar_ollama():
            raise RuntimeError("Ollama está instalado pero no arranca. Ábrelo desde el menú de inicio "
                               "(o desde Aplicaciones en Mac) y vuelve a intentarlo.")
        _poner(fase="listo", progreso=1.0, mensaje="Ollama está listo. Elige ahora el modelo que quieres usar.")
    except requests.exceptions.ConnectionError:
        _poner(fase="error", error="No hay conexión a internet. Conéctate y vuelve a intentarlo: "
                                   "la descarga solo hace falta la primera vez.")
    except Exception as e:  # noqa
        _poner(fase="error", error=str(e) or "Error inesperado durante la instalación.")


def empezar():
    global _hilo
    with _CERROJO:
        if _hilo is not None and _hilo.is_alive():
            return False
        _hilo = threading.Thread(target=_preparar, daemon=True)
        _hilo.start()
    return True
