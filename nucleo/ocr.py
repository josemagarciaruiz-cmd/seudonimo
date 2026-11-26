# -*- coding: utf-8 -*-
"""Seudónimo · OCR de páginas escaneadas, siempre en el propio ordenador.

En Mac se usa el motor de texto del sistema (Vision); en Windows, Tesseract, que va
incluido en el instalador. Ambos devuelven la posición de cada línea y de cada palabra,
lo que permite tachar los datos dentro de la propia imagen."""
import difflib
import io
import os
import re
import shutil
import uuid

import rutas
from pdfdoc import Rect

DPI = 300
_CACHE = {}

# ---------------------------------------------------------------- motores disponibles

try:
    import Vision  # noqa: F401  (solo en Mac)
    from Foundation import NSData
    _VISION = True
except Exception:  # pragma: no cover
    _VISION = False


def _buscar_tesseract():
    candidatos = [rutas.TESSERACT_INCLUIDO, shutil.which("tesseract") or ""]
    if rutas.ES_WINDOWS:
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("LOCALAPPDATA", "")):
            candidatos.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
            candidatos.append(os.path.join(base, "Programs", "Tesseract-OCR", "tesseract.exe"))
    else:
        candidatos += ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract"]
    for c in candidatos:
        if c and os.path.isfile(c):
            return c
    return None


TESSERACT = _buscar_tesseract()
_TESSDATA = None
if TESSERACT and os.path.isdir(os.path.join(os.path.dirname(TESSERACT), "tessdata")):
    _TESSDATA = os.path.join(os.path.dirname(TESSERACT), "tessdata")

if os.environ.get("SEUDONIMO_OCR") == "tesseract":
    _VISION = False
MOTOR = "Vision" if _VISION else ("Tesseract" if TESSERACT else None)
DISPONIBLE = MOTOR is not None


# ---------------------------------------------------------------- Vision (Mac)

def _vision(png, pag):
    import Vision
    datos = NSData.dataWithBytes_length_(png, len(png))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(datos, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setRecognitionLanguages_(["es-ES", "ca-ES", "en-US"])
    req.setUsesLanguageCorrection_(True)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError("El OCR de macOS ha fallado: %s" % err)

    def a_pagina(bb):
        x, y, w, h = bb.origin.x, bb.origin.y, bb.size.width, bb.size.height
        return Rect(x * pag.width, (1 - y - h) * pag.height, (x + w) * pag.width, (1 - y) * pag.height)

    lineas = []
    for obs in list(req.results() or []):
        cands = obs.topCandidates_(1)
        if not cands:
            continue
        cand = cands[0]
        texto = str(cand.string())
        if not texto.strip():
            continue
        rect = a_pagina(obs.boundingBox())
        palabras = []
        for m in re.finditer(r"\S+", texto):
            r = None
            try:
                caja, _ = cand.boundingBoxForRange_error_((m.start(), m.end() - m.start()), None)
                if caja is not None:
                    r = a_pagina(caja.boundingBox())
            except Exception:
                r = None
            if r is None or r.is_empty:
                # reparto proporcional dentro de la línea (más vale tachar de más)
                f0, f1 = m.start() / max(1, len(texto)), m.end() / max(1, len(texto))
                r = Rect(rect.x0 + f0 * rect.width, rect.y0, rect.x0 + f1 * rect.width, rect.y1)
            palabras.append((r, m.start(), m.end()))
        lineas.append({"texto": texto, "rect": rect, "palabras": palabras})
    return lineas


# ---------------------------------------------------------------- Tesseract (Windows y respaldo)

def _idiomas():
    if _TESSDATA:
        hay = {os.path.splitext(f)[0] for f in os.listdir(_TESSDATA) if f.endswith(".traineddata")}
    else:
        r = rutas.ejecutar([TESSERACT, "--list-langs"], text=True)
        hay = set((r.stdout or "").split())
    elegidos = [x for x in ("spa", "cat", "eng") if x in hay]
    return "+".join(elegidos) or "eng"


def _repetida(l, m):
    """La misma línea leída dos veces: mismo sitio y casi el mismo texto. Si en el mismo
    sitio una lectura dice otra cosa (texto girado leído como basura), se guardan las dos."""
    a, b = l["rect"], m["rect"]
    if (a & b).get_area() <= 0.5 * min(a.get_area() or 1, b.get_area() or 1):
        return False
    x, y = l["texto"].lower().strip(), m["texto"].lower().strip()
    return x in y or y in x or difflib.SequenceMatcher(None, x, y).ratio() >= 0.75


def _tesseract(png_bytes, escala):
    """Dos lecturas: la normal (psm 3, que entiende columnas y párrafos) y la de texto
    disperso con detección de orientación (psm 12), que recoge lo que la primera se salta:
    casillas de formularios, recuadros girados, informes de la Seguridad Social…"""
    os.makedirs(rutas.TRABAJO, exist_ok=True)
    ruta = os.path.join(rutas.TRABAJO, "ocr-%s.png" % uuid.uuid4().hex[:10])
    with open(ruta, "wb") as f:
        f.write(png_bytes)
    try:
        lineas = _tesseract_tsv(ruta, "3", escala)
        try:
            extra = _tesseract_tsv(ruta, "12", escala)
        except RuntimeError:
            extra = []  # sin osd.traineddata: nos quedamos con la primera lectura
        for l in extra:
            if not any(_repetida(l, m) for m in lineas):
                lineas.append(l)
        return lineas
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass


def _tesseract_tsv(ruta, psm, escala):
    args = [TESSERACT, ruta, "stdout", "-l", _idiomas(), "--psm", psm]
    if _TESSDATA:
        args += ["--tessdata-dir", _TESSDATA]
    args += ["tsv"]
    r = rutas.ejecutar(args, text=False, timeout=600)
    if r.returncode != 0:
        raise RuntimeError("El OCR ha fallado: %s" % (r.stderr or b"").decode("utf-8", "replace")[:300])
    salida = r.stdout.decode("utf-8", "replace")
    grupos = {}
    orden = []
    for fila in salida.splitlines()[1:]:
        c = fila.split("\t")
        if len(c) < 12 or c[0] != "5":
            continue
        texto = c[11].strip()
        if not texto:
            continue
        clave = (int(c[2]), int(c[3]), int(c[4]))
        x, y, w, h = (int(v) for v in c[6:10])
        r = Rect(x / escala, y / escala, (x + w) / escala, (y + h) / escala)
        if clave not in grupos:
            grupos[clave] = []
            orden.append(clave)
        grupos[clave].append((r, texto))
    lineas = []
    for clave in orden:
        palabras, partes, pos = [], [], 0
        for r, t in grupos[clave]:
            if partes:
                pos += 1
            palabras.append((r, pos, pos + len(t)))
            partes.append(t)
            pos += len(t)
        rect = palabras[0][0]
        for r, _, _ in palabras[1:]:
            rect = rect | r
        lineas.append({"texto": " ".join(partes), "rect": rect, "palabras": palabras})
    return lineas


# ---------------------------------------------------------------- interfaz común

def leer_pagina(pag, clave=None, dpi=None):
    """Líneas de la página en orden de lectura: {"texto", "rect", "palabras"}.
    Cada palabra es (Rect, inicio, fin) dentro del texto de su línea. La verificación lee
    a otra resolución (dpi) para que el OCR no repita los mismos errores."""
    dpi = dpi or DPI
    if clave is not None and clave in _CACHE:
        return _CACHE[clave]
    if not DISPONIBLE:
        raise RuntimeError("El OCR no está disponible en este equipo.")
    img = pag.renderizar(dpi)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    if MOTOR == "Vision":
        lineas = _vision(png, pag)
    else:
        lineas = _tesseract(png, dpi / 72.0)
    lineas.sort(key=lambda l: (round(l["rect"].y0 / 4), l["rect"].x0))
    if clave is not None:
        _CACHE[clave] = lineas
    return lineas


def leer_imagen(img, pag):
    """OCR de una imagen ya renderizada de la página (por ejemplo, con los datos ya tapados).
    Devuelve las líneas en coordenadas de la página, como leer_pagina."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    if MOTOR == "Vision":
        lineas = _vision(png, pag)
    else:
        lineas = _tesseract(png, img.width / pag.width)
    lineas.sort(key=lambda l: (round(l["rect"].y0 / 4), l["rect"].x0))
    return lineas


def rect_fragmento(linea, ini, fin, mx=0.4, my=0.8):
    """Rectángulo que ocupan en la página los caracteres [ini, fin) de una línea."""
    r = None
    for caja, a, b in linea["palabras"]:
        if a < fin and b > ini:
            # si el dato empieza o acaba a mitad de palabra, se tacha la palabra entera
            r = caja if r is None else r | caja
    if r is None or r.is_empty:
        r = linea["rect"]  # sin precisión: se tacha la línea entera (más vale de más)
    return r.ampliar(mx, my)


def olvidar(prefijo):
    for k in [k for k in _CACHE if str(k[0]).startswith(prefijo)]:
        _CACHE.pop(k, None)
