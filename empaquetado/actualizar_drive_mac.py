# -*- coding: utf-8 -*-
"""Sustituye el contenido del instalador de Mac en Google Drive por el de una versión nueva,
SIN cambiar el archivo: el enlace de descarga sigue siendo el mismo y da siempre la última.

    https://drive.usercontent.google.com/download?id=1M3WRF8wZ3oPzu88ssCZaKG8j4DXjmVRI&export=download&confirm=t
(con «confirm=t» Drive no muestra su aviso de «no se puede analizar en busca de virus»)

Usa las credenciales del agente de Drive del Mac (~/mcp-drive-local/.env), sin mostrarlas.
Uso:  ~/mcp-drive-local/.venv/bin/python empaquetado/actualizar_drive_mac.py 0.8.2
"""
import hashlib
import os
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ARCHIVO_DRIVE = "1M3WRF8wZ3oPzu88ssCZaKG8j4DXjmVRI"      # «Seudonimo-Mac.dmg» en la carpeta Mac
NOMBRE = "Seudonimo-Mac.dmg"


def _credenciales():
    ev = {}
    with open(os.path.expanduser("~/mcp-drive-local/.env"), encoding="utf-8") as f:
        for linea in f:
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1)
                ev[k.strip()] = v.strip().strip('"').strip("'")
    return Credentials(token=None, refresh_token=ev["GOOGLE_REFRESH_TOKEN"],
                       token_uri="https://oauth2.googleapis.com/token",
                       client_id=ev["GOOGLE_CLIENT_ID"], client_secret=ev["GOOGLE_CLIENT_SECRET"],
                       scopes=["https://www.googleapis.com/auth/drive"])


def main(version):
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dmg = os.path.join(raiz, "salida", "Seudonimo-%s-Mac.dmg" % version)
    huella = hashlib.sha256(open(dmg, "rb").read()).hexdigest()
    svc = build("drive", "v3", credentials=_credenciales(), cache_discovery=False)
    media = MediaFileUpload(dmg, mimetype="application/x-apple-diskimage", resumable=True, chunksize=16 << 20)
    r = svc.files().update(fileId=ARCHIVO_DRIVE, media_body=media,
                           body={"name": NOMBRE, "description": "Seudónimo %s · SHA-256 %s" % (version, huella)},
                           fields="id,name,size,md5Checksum").execute()
    md5 = hashlib.md5(open(dmg, "rb").read()).hexdigest()
    if r.get("md5Checksum") != md5 or int(r.get("size", 0)) != os.path.getsize(dmg):
        sys.exit("El archivo de Drive no coincide con el local: revisar.")
    print("Drive actualizado: %s (%s bytes), versión %s" % (r["name"], r["size"], version))


if __name__ == "__main__":
    main(sys.argv[1])
