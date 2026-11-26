# -*- coding: utf-8 -*-
"""Dictado por voz: transcripción local con whisper.cpp.

El audio llega de la ventana (WAV mono de 16 kHz grabado con el micrófono), se escribe en un
temporal, whisper-cli lo transcribe en este ordenador y el temporal se borra. El audio nunca sale
del equipo. El modelo de voz se descarga una sola vez, cuando el usuario lo pide."""
import os
import shutil
import subprocess
import tempfile
import threading
import time

import requests

import rutas

CARPETA = os.path.join(rutas.DATOS, "voz")
MAX_SEGUNDOS = 180

# Modelos de whisper.cpp (licencia MIT), en https://huggingface.co/ggerganov/whisper.cpp
MODELOS = [
    {"nombre": "small", "archivo": "ggml-small-q5_1.bin", "mb": 190, "recomendado": True,
     "descripcion": "Rápido: menos de un segundo por frase en un Mac con chip Apple. Recomendado."},
    {"nombre": "large-v3-turbo", "archivo": "ggml-large-v3-turbo-q5_0.bin", "mb": 574,
     "descripcion": "Más preciso con ruido o con acentos marcados. Algo más lento, sobre todo sin tarjeta gráfica."},
]
URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"

# Vocabulario del despacho: orienta al modelo hacia estas palabras al transcribir
VOCABULARIO = ("Seudónimo, seudonimiza, seudonimizar, anonimiza, nómina, contrato, expediente, verificación intensiva, "
               "sentencia, finiquito, carta de despido, Seguridad Social, demanda, papeleta, convenio.")

DESCARGA = {"fase": None, "progreso": 0.0, "mensaje": "", "error": None, "nombre": None}
_CERROJO = threading.Lock()


def binario():
    nombre = "whisper-cli.exe" if rutas.ES_WINDOWS else "whisper-cli"
    incluido = os.path.join(rutas.RAIZ, "whisper", nombre)
    if os.path.isfile(incluido):
        return incluido
    return shutil.which("whisper-cli")    # desarrollo: el de Homebrew o el del sistema


def _ruta(m):
    return os.path.join(CARPETA, m["archivo"])


def _modelo(nombre):
    return next((m for m in MODELOS if m["nombre"] == nombre), None)


def estado(activo="small"):
    return {"binario": bool(binario()),
            "modelos": [dict(m, descargado=os.path.isfile(_ruta(m))) for m in MODELOS],
            "activo": activo, "listo": bool(binario()) and os.path.isfile(_ruta(_modelo(activo) or MODELOS[0])),
            "descarga": DESCARGA}


def descargar(nombre):
    m = _modelo(nombre)
    if not m:
        raise ValueError("Modelo de voz desconocido.")
    if DESCARGA.get("fase") == "trabajando":
        return
    os.makedirs(CARPETA, exist_ok=True)
    if shutil.disk_usage(CARPETA).free < (m["mb"] + 500) * 1e6:
        DESCARGA.update(fase="error", progreso=0, nombre=nombre, error="No hay espacio suficiente en el disco.")
        return
    DESCARGA.update(fase="trabajando", progreso=0.0, nombre=nombre, error=None, mensaje="Empezando la descarga…")

    def hilo():
        destino = _ruta(m)
        parcial = destino + ".parcial"
        try:
            with requests.get(URL + m["archivo"], stream=True, timeout=(15, 600)) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or m["mb"] * 1e6)
                hecho = 0
                with open(parcial, "wb") as f:
                    for trozo in r.iter_content(1 << 20):
                        f.write(trozo)
                        hecho += len(trozo)
                        DESCARGA.update(progreso=min(0.99, hecho / total),
                                        mensaje="Descargando el modelo de voz (%d de %d MB)" % (hecho // 1e6, total // 1e6))
            if os.path.getsize(parcial) < m["mb"] * 0.9e6:
                raise RuntimeError("La descarga ha quedado incompleta.")
            os.replace(parcial, destino)
            DESCARGA.update(fase="listo", progreso=1.0, mensaje="Modelo de voz listo.")
        except Exception as e:  # noqa
            try:
                os.remove(parcial)
            except OSError:
                pass
            DESCARGA.update(fase="error", error="No se ha podido descargar el modelo de voz: %s" % str(e)[:150])
    threading.Thread(target=hilo, daemon=True).start()


def transcribir(wav, modelo="small"):
    """Texto del audio (bytes de un WAV). El audio solo existe en un temporal que se borra."""
    exe = binario()
    m = _modelo(modelo) or MODELOS[0]
    if not exe:
        raise RuntimeError("Falta el programa de dictado (whisper-cli).")
    if not os.path.isfile(_ruta(m)):
        raise RuntimeError("Falta el modelo de voz: descárgalo en «Modelos».")
    if len(wav) < 1000:
        return {"texto": "", "segundos": 0}
    os.makedirs(rutas.TRABAJO, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".wav", dir=rutas.TRABAJO)
    t0 = time.time()
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(wav)
        with _CERROJO:     # un dictado cada vez
            r = rutas.ejecutar([exe, "-m", _ruta(m), "-l", "es", "-nt", "-np", "-t", str(max(2, (os.cpu_count() or 4) - 1)),
                                "--prompt", VOCABULARIO, "-f", tmp], timeout=MAX_SEGUNDOS, text=True,
                               encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError("El dictado ha fallado (código %s)." % r.returncode)
        texto = " ".join(l.strip() for l in (r.stdout or "").splitlines() if l.strip())
        # whisper marca así los silencios o el ruido: no es texto dictado
        for ruido in ("[BLANK_AUDIO]", "[ Silencio ]", "[Música]", "(música)", "[MÚSICA]"):
            texto = texto.replace(ruido, "")
        return {"texto": texto.strip(), "segundos": round(time.time() - t0, 1)}
    except subprocess.TimeoutExpired:
        raise RuntimeError("El dictado ha tardado demasiado.")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
