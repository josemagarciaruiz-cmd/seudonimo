# -*- coding: utf-8 -*-
"""Genera los iconos de Seudónimo a partir del dibujo original, `empaquetado/icono.svg` (el
detective: silueta con sombrero sobre oro, de la que solo se ven los ojos).

1. Rasterizar el SVG a 1024 px (Chromium de Playwright):
     node empaquetado/rasterizar-icono.js empaquetado/icono.svg empaquetado/icono-1024.png
2. Generar los tamaños de Tauri (PNG, .ico de Windows, .icns de Mac) y el de la interfaz:
     python3 empaquetado/icono.py"""
import os

from PIL import Image

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONOS = os.path.join(D, "escritorio", "src-tauri", "icons")
ORIGEN = os.path.join(D, "empaquetado", "icono-1024.png")

if __name__ == "__main__":
    base = Image.open(ORIGEN).convert("RGBA")
    for nombre, t in (("32x32.png", 32), ("64x64.png", 64), ("128x128.png", 128),
                      ("128x128@2x.png", 256), ("icon.png", 512)):
        base.resize((t, t), Image.LANCZOS).save(os.path.join(ICONOS, nombre))
    base.save(os.path.join(ICONOS, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    base.save(os.path.join(ICONOS, "icon.icns"))
    os.makedirs(os.path.join(D, "interfaz", "img"), exist_ok=True)
    base.resize((128, 128), Image.LANCZOS).save(os.path.join(D, "interfaz", "img", "icono.png"))
    print("iconos generados")
