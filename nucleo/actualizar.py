# -*- coding: utf-8 -*-
"""Actualización con un clic.

1. Descarga el instalador de la versión nueva desde las versiones publicadas en GitHub (solo
   desde ese repositorio) y comprueba su huella SHA-256 con el archivo SHA256SUMS de la misma
   versión. Si no coincide, no se instala nada.
2. Deja preparado un pequeño guion que espera a que se cierre la aplicación, instala la versión
   nueva en el mismo sitio y la vuelve a abrir.
3. Cierra la aplicación. Los proyectos y los datos no se tocan: viven en la carpeta de datos.

En desarrollo (sin aplicación instalada) no se instala nada: la interfaz abre la descarga."""
import hashlib
import os
import signal
import subprocess
import sys
import threading
import time

import requests

import rutas

ORIGEN = "https://github.com/josemagarciaruiz-cmd/seudonimo/releases/download/"
ESTADO = {"fase": None, "progreso": 0.0, "mensaje": "", "error": None}


def _app_mac():
    """Ruta del .app instalado (…/Seudónimo.app), o None si no se ejecuta desde la aplicación."""
    partes = os.path.abspath(rutas.RAIZ).split(os.sep)
    for i in range(len(partes) - 1, 0, -1):
        if partes[i].endswith(".app"):
            return os.sep.join(partes[:i + 1])
    return None


def _app_windows():
    exe = os.path.join(os.path.dirname(os.path.abspath(rutas.RAIZ)), "Seudonimo.exe")
    return exe if os.path.isfile(exe) else None


def instalable():
    if not os.environ.get("SEUDONIMO_PADRE"):
        return False
    return bool(_app_windows() if rutas.ES_WINDOWS else (_app_mac() if rutas.ES_MAC else None))


def _descargar(url, destino, peso=1.0, base=0.0):
    with requests.get(url, stream=True, timeout=(15, 600)) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        hecho = 0
        h = hashlib.sha256()
        with open(destino, "wb") as f:
            for trozo in r.iter_content(1 << 20):
                f.write(trozo)
                h.update(trozo)
                hecho += len(trozo)
                if total:
                    ESTADO.update(progreso=base + peso * min(0.99, hecho / total),
                                  mensaje="Descargando la versión nueva (%d de %d MB)…" % (hecho // 1e6, total // 1e6))
    return h.hexdigest()


def iniciar(url, version, padre):
    if ESTADO.get("fase") == "trabajando":
        return
    if not url or not url.startswith(ORIGEN):
        raise ValueError("La descarga no viene de las versiones publicadas de Seudónimo.")
    ESTADO.update(fase="trabajando", progreso=0.0, mensaje="Empezando la descarga…", error=None)
    threading.Thread(target=_trabajo, args=(url, version, padre), daemon=True).start()


def _trabajo(url, version, padre):
    try:
        carpeta = os.path.join(rutas.TRABAJO, "actualizacion")
        os.makedirs(carpeta, exist_ok=True)
        nombre = url.rsplit("/", 1)[1]
        destino = os.path.join(carpeta, nombre)
        huella = _descargar(url, destino)
        ESTADO.update(progreso=0.99, mensaje="Comprobando que la descarga es íntegra…")
        sumas = requests.get(url.rsplit("/", 1)[0] + "/SHA256SUMS-%s.txt" % version, timeout=20)
        sumas.raise_for_status()
        esperada = next((l.split()[0] for l in sumas.text.splitlines() if l.strip().endswith(nombre)), None)
        if not esperada or esperada.lower() != huella.lower():
            os.remove(destino)
            raise RuntimeError("La huella del instalador no coincide con la publicada: no se instala.")
        ESTADO.update(progreso=1.0, fase="instalando",
                      mensaje="Instalando: Seudónimo se cerrará y volverá a abrirse solo en unos segundos.")
        if rutas.ES_MAC:
            _instalar_mac(destino, padre)
        elif rutas.ES_WINDOWS:
            _instalar_windows(destino, padre)
        time.sleep(1.5)                       # que la ventana llegue a mostrar el aviso
        try:
            os.kill(padre, signal.SIGTERM)    # cierra la ventana; el servicio se apaga con ella
        except OSError:
            pass
    except Exception as e:  # noqa
        ESTADO.update(fase="error", error="No se ha podido actualizar: %s" % str(e)[:200])


def _instalar_mac(dmg, padre):
    app = _app_mac()
    guion = os.path.join(os.path.dirname(dmg), "instalar.sh")
    with open(guion, "w", encoding="utf-8") as f:
        f.write('''#!/bin/zsh
# Guion de actualización de Seudónimo: espera a que se cierre la aplicación y la sustituye.
PADRE=%d
DMG=%s
DESTINO=%s
for i in $(seq 1 120); do kill -0 $PADRE 2>/dev/null || break; sleep 0.5; done
sleep 1
M=$(mktemp -d /tmp/seudonimo-act.XXXXXX)
hdiutil attach -nobrowse -quiet -mountpoint "$M" "$DMG" || { open "$DESTINO"; exit 1; }
NUEVA=$(ls -d "$M"/*.app | head -1)
rm -rf "$DESTINO.anterior"
if mv "$DESTINO" "$DESTINO.anterior" && ditto "$NUEVA" "$DESTINO"; then
  rm -rf "$DESTINO.anterior"
else
  rm -rf "$DESTINO"; mv "$DESTINO.anterior" "$DESTINO"
fi
hdiutil detach -quiet "$M"
rm -f "$DMG"
open "$DESTINO"
''' % (padre, _cita(dmg), _cita(app)))
    os.chmod(guion, 0o700)
    subprocess.Popen(["/bin/zsh", guion], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def _instalar_windows(exe, padre):
    app = _app_windows()
    guion = os.path.join(os.path.dirname(exe), "instalar.cmd")
    with open(guion, "w", encoding="utf-8") as f:
        f.write('''@echo off
chcp 65001 >nul
rem Guion de actualización de Seudónimo: espera a que se cierre la aplicación e instala.
:espera
tasklist /FI "PID eq %d" 2>nul | find "%d" >nul && (timeout /t 1 /nobreak >nul & goto espera)
"%s" /S
start "" "%s"
''' % (padre, padre, exe, app))
    flags = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen(["cmd", "/c", guion], creationflags=flags, close_fds=True)


def _cita(s):
    return "'" + s.replace("'", "'\\''") + "'"
