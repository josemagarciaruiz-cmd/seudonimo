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


# ---------------------------------------------------------------- tamaño con que se muestra cada imagen

WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A4_EMU = (7560310, 10692130)
DIBUJOS = re.compile(r"^(word/(document|header\d*|footer\d*)|ppt/(slides/slide|slideLayouts/slideLayout|slideMasters/slideMaster)\d+|xl/drawings/drawing\d+)\.xml$")


def _pagina(z, familia):
    from lxml import etree
    try:
        if familia == "docx":
            root = etree.fromstring(z.read("word/document.xml"))
            pg = next(root.iter("{%s}pgSz" % W_NS), None)
            if pg is not None:
                return int(pg.get("{%s}w" % W_NS)) * 635, int(pg.get("{%s}h" % W_NS)) * 635
        if familia == "pptx":
            sz = next(etree.fromstring(z.read("ppt/presentation.xml")).iter("{%s}sldSz" % P_NS), None)
            if sz is not None:
                return int(sz.get("cx")), int(sz.get("cy"))
    except Exception:  # noqa
        pass
    return A4_EMU


def _destinos(z, parte):
    from lxml import etree
    d, n = posixpath.split(parte)
    rels = posixpath.join(d, "_rels", n + ".rels")
    if rels not in z.namelist():
        return {}
    res = {}
    for r in etree.fromstring(z.read(rels)).iter("{%s}Relationship" % PR):
        if r.get("TargetMode") != "External":
            t = r.get("Target") or ""
            res[r.get("Id")] = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join(d, t))
    return res


def tamanos(z, familia):
    """{imagen: (fracción del área de la página, del ancho, del alto)} con el mayor tamaño con que
    se muestra cada imagen en el documento. Una imagen sin tamaño conocido no aparece."""
    from lxml import etree
    W, H = _pagina(z, familia)
    res = {}
    for parte in z.namelist():
        if not DIBUJOS.match(parte):
            continue
        destinos = _destinos(z, parte)
        if not destinos:
            continue
        try:
            root = etree.fromstring(z.read(parte))
        except Exception:  # noqa
            continue
        for blip in root.iter("{%s}blip" % A):
            destino = destinos.get(blip.get("{%s}embed" % R))
            if not destino:
                continue
            cx = cy = None
            anc = blip.getparent()
            for _ in range(6):
                if anc is None:
                    break
                for el in anc.iter():
                    if isinstance(el.tag, str) and etree.QName(el).localname in ("extent", "ext") and el.get("cx") and el.get("cy"):
                        cx, cy = int(el.get("cx")), int(el.get("cy"))
                        break
                if cx:
                    break
                anc = anc.getparent()
            if not cx or not cy:
                continue
            fr = (cx * cy / float(W * H), cx / float(W), cy / float(H))
            previo = res.get(destino)
            res[destino] = fr if previo is None else tuple(max(a, b) for a, b in zip(previo, fr))
    return res


def es_logo(fr):
    """El mismo criterio que en los PDF: pequeña y no en banda ancha → logotipo, sello, firma o foto pequeña."""
    return fr is not None and fr[0] <= 0.12 and fr[1] <= 0.6 and fr[2] <= 0.45


def _rotulo(lienzo, caja, texto, fondo=(231, 235, 238), letra=(27, 38, 51)):
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(lienzo)
    x0, y0, x1, y1 = [int(round(v)) for v in caja]
    relleno = fondo + ((255,) if lienzo.mode == "RGBA" else ())
    d.rectangle([x0, y0, x1, y1], fill=relleno)
    ancho, alto = x1 - x0, y1 - y0
    def fuente_de(t):
        try:
            return ImageFont.load_default(size=t)
        except TypeError:          # Pillow antiguo: una sola letra, pequeña
            return ImageFont.load_default()
    tam = max(8, alto // 3)
    fuente = fuente_de(tam)
    while tam > 8 and d.textlength(texto, font=fuente) > ancho * 0.9:
        tam -= 2
        fuente = fuente_de(tam)
    tw = d.textlength(texto, font=fuente)
    if tw < ancho - 4 and tam < alto - 2:
        d.text((x0 + (ancho - tw) / 2, y0 + (alto - tam) / 2), texto, fill=letra + ((255,) if lienzo.mode == "RGBA" else ()), font=fuente)


def marcador_logo(ancho, alto, formato="PNG"):
    """Imagen gris del mismo tamaño con «[LOGO O SELLO]», para sustituir una imagen entera."""
    from PIL import Image
    img = Image.new("RGB", (max(1, ancho), max(1, alto)), (231, 235, 238))
    _rotulo(img, (0, 0, ancho - 1, alto - 1), "[LOGO O SELLO]")
    salida = io.BytesIO()
    img.save(salida, "JPEG" if formato.upper() in ("JPEG", "JPG") else formato.upper() if formato.upper() in ("PNG", "GIF", "BMP", "TIFF", "WEBP") else "PNG")
    return salida.getvalue()


def tapar(data, nombre, mapa, logo=False, caras=True, extra=None):
    """Bytes de la imagen con los datos del mapa tapados (y las caras), la imagen entera
    sustituida si es un logotipo, o None si no hay nada que tapar. Devuelve (bytes, qué)."""
    ext = posixpath.splitext(nombre)[1].lower()
    if logo:
        try:
            img = _abrir(data)
            fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".gif": "GIF", ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF", ".webp": "WEBP"}.get(ext, "PNG")
            return marcador_logo(img.width, img.height, fmt), "logo"
        except Exception:  # noqa
            return None, None
    ls = lineas(data) if mapa else []
    rects_caras = []
    if caras:
        try:
            import rostros
            rects_caras = rostros.caras(_abrir(data))
        except Exception:  # noqa
            rects_caras = []
    # caras que la verificación encontró aún a la vista en la copia (mismas coordenadas: la copia
    # de la imagen tiene el mismo tamaño que el original)
    rects_caras = list(rects_caras) + list(extra or [])
    hecho = _tapar(data, nombre, mapa, ls, rects_caras)
    return (hecho, "caras" if rects_caras else "texto") if hecho is not None else (None, None)


def _tapar(data, nombre, mapa, ls, rects_caras):
    if not ls and not rects_caras:
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
    if not rects and not rects_caras:
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
    for caja in rects_caras:
        _rotulo(lienzo, caja, "[CARA]")
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
