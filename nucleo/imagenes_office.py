# -*- coding: utf-8 -*-
"""Texto dentro de las imágenes de Word, PowerPoint y Excel.

Las imágenes van guardadas dentro del archivo (word/media, ppt/media, xl/media). Se leen con
el mismo OCR local que las páginas escaneadas y, en la copia, los datos que aparecen en ellas
se tapan con un recuadro negro dibujado sobre la propia imagen, que se guarda en el mismo
formato. Las imágenes vectoriales (EMF/WMF) no se pueden leer ni editar así: se avisa."""
import hashlib
import io
import posixpath
import re

import motor
import ocr

MEDIA = re.compile(r"^(word|ppt|xl)/media/[^/]+$", re.IGNORECASE)
LEGIBLES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}
VECTORIALES = {".emf", ".wmf", ".svg"}
MINIMO = 24          # píxeles: por debajo, una imagen no tiene texto legible
_CACHE = {}


class _Lienzo:
    """Lo que el OCR necesita de una «página»: su tamaño (aquí, en píxeles de la imagen)."""
    def __init__(self, ancho, alto):
        self.width, self.height = ancho, alto


def es_imagen(nombre):
    return bool(MEDIA.match(nombre)) and posixpath.splitext(nombre)[1].lower() in LEGIBLES


def es_vectorial(nombre):
    return bool(MEDIA.match(nombre)) and posixpath.splitext(nombre)[1].lower() in VECTORIALES


def _abrir(data):
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def lineas(data):
    """Líneas de OCR de una imagen (en píxeles), o [] si no hay OCR o no se puede leer."""
    if not ocr.DISPONIBLE:
        return []
    clave = hashlib.sha1(data).hexdigest()
    if clave in _CACHE:
        return _CACHE[clave]
    res = []
    try:
        img = _abrir(data)
        if img.width >= MINIMO and img.height >= MINIMO:
            if getattr(img, "n_frames", 1) > 1:
                img.seek(0)
            rgb = img.convert("RGB")
            # las imágenes pequeñas se amplían: el OCR lee mal letras de pocos píxeles
            f = 1
            if min(rgb.width, rgb.height) < 300:
                f = max(1, min(4, 600 // max(1, min(rgb.width, rgb.height))))
            if f > 1:
                from PIL import Image
                rgb = rgb.resize((rgb.width * f, rgb.height * f), Image.LANCZOS)
            res = ocr.leer_imagen(rgb, _Lienzo(img.width, img.height))
    except Exception:  # noqa  (imagen dañada o formato raro: no se lee)
        res = []
    _CACHE[clave] = res
    return res


def texto(data):
    return "\n".join(l["texto"] for l in lineas(data))


def tapar(data, nombre, mapa):
    """Bytes de la imagen con los datos del mapa tapados, o None si no hay nada que tapar."""
    ls = lineas(data)
    if not ls or not mapa:
        return None
    offs, acc = [], 0
    for l in ls:
        offs.append(acc)
        acc += len(l["texto"]) + 1
    completo = "\n".join(l["texto"] for l in ls)
    rects = []
    for ini, fin, _ in motor.coincidencias(completo, mapa):
        for l, o in zip(ls, offs):
            a, b = max(ini, o), min(fin, o + len(l["texto"]))
            if a < b:
                rects.append(ocr.rect_fragmento(l, a - o, b - o, mx=2, my=2))
    if not rects:
        return None
    from PIL import Image, ImageDraw
    img = _abrir(data)
    formato = img.format or "PNG"
    if getattr(img, "n_frames", 1) > 1:
        img.seek(0)                      # un GIF animado se queda en su primer fotograma
    modo = img.mode
    lienzo = img.convert("RGBA" if "A" in modo or modo == "P" else "RGB")
    d = ImageDraw.Draw(lienzo)
    negro = (0, 0, 0, 255) if lienzo.mode == "RGBA" else (0, 0, 0)
    for r in rects:
        d.rectangle([max(0, r.x0), max(0, r.y0), min(lienzo.width, r.x1), min(lienzo.height, r.y1)], fill=negro)
    salida = io.BytesIO()
    ext = posixpath.splitext(nombre)[1].lower()
    if ext in (".jpg", ".jpeg"):
        lienzo.convert("RGB").save(salida, "JPEG", quality=95)
    elif ext in (".gif",):
        lienzo.convert("RGB").convert("P", palette=Image.ADAPTIVE).save(salida, "GIF")
    elif ext in (".bmp",):
        lienzo.convert("RGB").save(salida, "BMP")
    elif ext in (".tif", ".tiff"):
        lienzo.save(salida, "TIFF")
    elif ext == ".webp":
        lienzo.save(salida, "WEBP", quality=95)
    else:
        lienzo.save(salida, "PNG")
    # también desaparece lo que lleve la imagen dentro (EXIF con autor, ubicación…): no se copia
    return salida.getvalue()
