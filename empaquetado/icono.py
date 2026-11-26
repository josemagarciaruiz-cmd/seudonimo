# -*- coding: utf-8 -*-
"""Dibuja el icono de Seudónimo (sello dorado con una «S» sobre fondo azul noche) y genera los
tamaños que necesita Tauri: PNG, .ico (Windows) y .icns (Mac).
Uso:  python3 empaquetado/icono.py   (necesita Pillow y fontTools con brotli)"""
import io
import os

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONOS = os.path.join(D, "escritorio", "src-tauri", "icons")
FUENTE = os.path.join(D, "interfaz", "fuentes", "source-serif-4-latin-600-normal.woff2")
NOCHE, ORO, BLANCO = (27, 38, 51, 255), (168, 130, 42, 255), (255, 255, 255, 255)


def fuente(tam):
    f = TTFont(FUENTE)
    f.flavor = None
    b = io.BytesIO()
    f.save(b)
    b.seek(0)
    return ImageFont.truetype(b, tam)


def dibujar(n=1024):
    s = 4                                        # supermuestreo para bordes suaves
    N = n * s
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = int(N * 0.06)                            # margen como el de los iconos de macOS
    d.rounded_rectangle((m, m, N - m, N - m), radius=int(N * 0.18), fill=NOCHE)
    c, r = N / 2, N * 0.33
    d.ellipse((c - r, c - r, c + r, c + r), fill=ORO)
    ri, g = r * 0.9, max(2, int(N * 0.008))
    d.ellipse((c - ri, c - ri, c + ri, c + ri), outline=BLANCO, width=g)
    f = fuente(int(N * 0.42))
    x0, y0, x1, y1 = d.textbbox((0, 0), "S", font=f)
    d.text((c - (x0 + x1) / 2, c - (y0 + y1) / 2), "S", font=f, fill=BLANCO)
    return im.resize((n, n), Image.LANCZOS)


if __name__ == "__main__":
    base = dibujar(1024)
    for nombre, t in (("32x32.png", 32), ("64x64.png", 64), ("128x128.png", 128),
                      ("128x128@2x.png", 256), ("icon.png", 512)):
        base.resize((t, t), Image.LANCZOS).save(os.path.join(ICONOS, nombre))
    base.save(os.path.join(ICONOS, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    base.save(os.path.join(ICONOS, "icon.icns"))
    print("iconos generados en", ICONOS)
