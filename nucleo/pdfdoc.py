# -*- coding: utf-8 -*-
"""Seudónimo · lectura y tachado de PDF con PDFium (licencia Apache 2.0 / BSD).

Sustituye a PyMuPDF, cuya licencia AGPL impedía distribuir la aplicación.

Todas las posiciones se expresan en «coordenadas de pantalla»: puntos PDF con el origen
arriba a la izquierda y la página tal y como se ve (con su giro aplicado).

Cómo se tacha: cada página que contiene un dato se vuelve a dibujar como imagen, se tapan
los datos con un recuadro blanco y su marcador, y se le añade una capa de texto invisible
(seleccionable y buscable) en la que solo están las palabras que no se han tachado. Así el
dato original desaparece de verdad del archivo: no queda debajo del recuadro. Las páginas
sin datos se copian tal cual, sin perder calidad."""
import ctypes
import functools
import io
import math
import re
import threading

import pypdfium2 as pdfium
import pypdfium2.raw as raw
from PIL import Image, ImageDraw, ImageFont

DPI_TEXTO = 200        # resolución de las páginas tachadas que eran texto
DPI_ESCANEO = 300      # resolución de las páginas tachadas que eran escaneos
CALIDAD_JPEG = 88
_ESPACIOS = re.compile(r"[\s  -​　]")


# PDFium no admite llamadas desde varios hilos a la vez (la interfaz pide páginas mientras un
# trabajo tacha otro documento): toda llamada a la biblioteca pasa por este cerrojo.
CERROJO = threading.RLock()


def _serializado(f):
    @functools.wraps(f)
    def envoltura(*a, **k):
        with CERROJO:
            return f(*a, **k)
    return envoltura


class ErrorPDF(Exception):
    pass


class Rect:
    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self, x0=0.0, y0=0.0, x1=0.0, y1=0.0):
        if not isinstance(x0, (int, float)):
            x0, y0, x1, y1 = x0
        self.x0, self.y0, self.x1, self.y1 = float(x0), float(y0), float(x1), float(y1)

    def __iter__(self):
        return iter((self.x0, self.y0, self.x1, self.y1))

    def __repr__(self):
        return "Rect(%.1f, %.1f, %.1f, %.1f)" % tuple(self)

    @property
    def width(self):
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self):
        return max(0.0, self.y1 - self.y0)

    @property
    def is_empty(self):
        return self.x1 <= self.x0 or self.y1 <= self.y0

    def get_area(self):
        return self.width * self.height

    def __or__(self, o):
        return Rect(min(self.x0, o.x0), min(self.y0, o.y0), max(self.x1, o.x1), max(self.y1, o.y1))

    def __and__(self, o):
        return Rect(max(self.x0, o.x0), max(self.y0, o.y0), min(self.x1, o.x1), min(self.y1, o.y1))

    def intersects(self, o):
        return not (self & o).is_empty

    def ampliar(self, mx, my):
        return Rect(self.x0 - mx, self.y0 - my, self.x1 + mx, self.y1 + my)

    def escalar(self, f):
        return Rect(self.x0 * f, self.y0 * f, self.x1 * f, self.y1 * f)


# ---------------------------------------------------------------- lectura

class Documento:
    @_serializado
    def __init__(self, ruta):
        try:
            self.pdf = pdfium.PdfDocument(ruta)
        except pdfium.PdfiumError as e:
            if "password" in str(e).lower() or "contraseña" in str(e).lower():
                raise ErrorPDF("El PDF está protegido con contraseña. Quítasela y vuelve a subirlo.")
            raise ErrorPDF("No he podido abrir el PDF: está dañado o no es un PDF válido.")
        self.ruta = ruta
        self.paginas = [Pagina(self, i) for i in range(len(self.pdf))]

    def __len__(self):
        return len(self.paginas)

    def __iter__(self):
        return iter(self.paginas)

    def __getitem__(self, i):
        return self.paginas[i]

    @_serializado
    def close(self):
        for p in self.paginas:
            p.cerrar()
        self.pdf.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Pagina:
    @_serializado
    def __init__(self, doc, idx):
        self.doc, self.number = doc, idx
        self.page = doc.pdf[idx]
        self.width, self.height = self.page.get_size()
        self._conv = pdfium.PdfPosConv(
            self.page, (0, 0, math.ceil(self.width * 10), math.ceil(self.height * 10), 0))
        self._tp = None
        self._texto = None
        self._palabras = None

    @property
    def rect(self):
        return Rect(0, 0, self.width, self.height)

    @_serializado
    def cerrar(self):
        if self._tp is not None:
            self._tp.close()
            self._tp = None
        self.page.close()

    # -- conversión de coordenadas del PDF a coordenadas de pantalla
    def _a_pantalla(self, izq, abajo, der, arriba):
        xa, ya = self._conv.to_bitmap(izq, abajo)
        xb, yb = self._conv.to_bitmap(der, arriba)
        return Rect(min(xa, xb) / 10, min(ya, yb) / 10, max(xa, xb) / 10, max(ya, yb) / 10)

    @property
    @_serializado
    def tp(self):
        if self._tp is None:
            self._tp = self.page.get_textpage()
        return self._tp

    @_serializado
    def get_text(self):
        if self._texto is None:
            n = self.tp.count_chars()
            t = self.tp.get_text_range(0, n) if n else ""
            self._texto = t.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
        return self._texto

    @_serializado
    def palabras(self):
        """Lista de palabras: (x0, y0, x1, y1, texto, bloque, línea, n.º de palabra)."""
        if self._palabras is not None:
            return self._palabras
        res, linea, num = [], 0, 0
        actual, caja = [], None

        def cerrar_palabra():
            nonlocal actual, caja, num
            if actual and caja is not None:
                res.append((caja.x0, caja.y0, caja.x1, caja.y1, "".join(actual), 0, linea, num))
                num += 1
            actual, caja = [], None

        n = self.tp.count_chars()
        ultimo_y = None
        for i in range(n):
            u = raw.FPDFText_GetUnicode(self.tp, i)
            c = chr(u) if u else ""
            if c in ("\r", "\n"):
                cerrar_palabra()
                if c == "\n":
                    linea += 1
                    num = 0
                continue
            if not c or _ESPACIOS.match(c):
                cerrar_palabra()
                continue
            if raw.FPDFText_IsGenerated(self.tp, i) == 1:
                continue
            # caja «holgada»: todo el alto de la letra, igual para «a», «g» o «,»
            izq, abajo, der, arriba = self.tp.get_charbox(i, loose=True)
            r = self._a_pantalla(izq, abajo, der, arriba)
            if r.is_empty:
                r = Rect(r.x0, r.y0, r.x0 + 0.5, r.y0 + 0.5)
            centro = (r.y0 + r.y1) / 2
            # salto de línea sin carácter de salto: la letra está claramente más abajo
            if caja is not None and ultimo_y is not None and abs(centro - ultimo_y) > max(r.height, 4) * 0.6:
                cerrar_palabra()
                linea += 1
                num = 0
            ultimo_y = centro
            actual.append(c)
            caja = r if caja is None else caja | r
        cerrar_palabra()
        self._palabras = res
        return res

    @_serializado
    def buscar(self, texto):
        """Cada aparición literal de *texto* (sin distinguir mayúsculas), como lista de
        rectángulos: uno por cada renglón que ocupa."""
        res = []
        try:
            buscador = self.tp.search(texto, match_case=False, match_whole_word=False)
        except Exception:
            return res
        while True:
            m = buscador.get_next()
            if not m:
                break
            ini, cuenta = m
            renglones = []
            for j in range(self.tp.count_rects(ini, cuenta)):
                izq, abajo, der, arriba = self.tp.get_rect(j)
                r = self._a_pantalla(izq, abajo, der, arriba)
                for k, otro in enumerate(renglones):
                    solape = min(r.y1, otro.y1) - max(r.y0, otro.y0)
                    if solape > 0.5 * min(r.height, otro.height):
                        renglones[k] = otro | r
                        break
                else:
                    renglones.append(r)
            if renglones:
                res.append(renglones)
        return res

    @_serializado
    def cobertura_imagen(self):
        """Parte de la página tapada por imágenes (0 a 1)."""
        total = 0.0
        try:
            for obj in self.page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE]):
                izq, abajo, der, arriba = obj.get_bounds()
                total += (self._a_pantalla(izq, abajo, der, arriba) & self.rect).get_area()
        except Exception:
            pass
        return min(1.0, total / (self.rect.get_area() or 1))

    @_serializado
    def imagenes(self):
        """Rectángulos (en pantalla) de las imágenes incrustadas en la página."""
        res = []
        try:
            for obj in self.page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE], max_depth=4):
                izq, abajo, der, arriba = obj.get_bounds()
                r = self._a_pantalla(izq, abajo, der, arriba) & self.rect
                if not r.is_empty:
                    res.append(r)
        except Exception:
            pass
        return res

    @_serializado
    def renderizar(self, dpi):
        """Imagen RGB de la página tal y como se ve."""
        bm = self.page.render(scale=dpi / 72.0, may_draw_forms=True)
        img = bm.to_pil().convert("RGB")
        bm.close()
        return img

    @_serializado
    def enlaces_mailto(self):
        """Índices de las anotaciones de enlace que apuntan a una dirección de correo."""
        res = []
        for k in range(raw.FPDFPage_GetAnnotCount(self.page)):
            annot = raw.FPDFPage_GetAnnot(self.page, k)
            try:
                if raw.FPDFAnnot_GetSubtype(annot) != raw.FPDF_ANNOT_LINK:
                    continue
                link = raw.FPDFAnnot_GetLink(annot)
                accion = raw.FPDFLink_GetAction(link) if link else None
                if not accion or raw.FPDFAction_GetType(accion) != raw.PDFACTION_URI:
                    continue
                n = raw.FPDFAction_GetURIPath(self.doc.pdf, accion, None, 0)
                if n <= 0:
                    continue
                buf = ctypes.create_string_buffer(n)
                raw.FPDFAction_GetURIPath(self.doc.pdf, accion, buf, n)
                uri = bytes(buf).split(b"\0")[0].decode("latin-1", "replace")
                if uri.lower().startswith("mailto:"):
                    res.append(k)
            finally:
                raw.FPDFPage_CloseAnnot(annot)
        return res


def abrir(ruta):
    return Documento(ruta)


# ---------------------------------------------------------------- escritura

def _fuente(px):
    try:
        return ImageFont.load_default(size=max(8, int(px)))
    except Exception:  # Pillow antiguo
        return ImageFont.load_default()


def _pintar(img, escala, tachones):
    """Tapa cada zona con un recuadro blanco y escribe el marcador en la primera."""
    dib = ImageDraw.Draw(img)
    for r, marc in tachones:
        rp = r.escalar(escala)
        caja = [int(math.floor(rp.x0)), int(math.floor(rp.y0)), int(math.ceil(rp.x1)), int(math.ceil(rp.y1))]
        dib.rectangle(caja, fill=(255, 255, 255))
        if marc:
            alto = max(4.0, min(9.0, r.height * 0.6)) * escala
            fuente = _fuente(alto)
            # si el marcador no cabe, se reduce la letra hasta que quepa
            while alto > 6 and dib.textlength(marc, font=fuente) > (caja[2] - caja[0]) + 2:
                alto -= 1
                fuente = _fuente(alto)
            y = caja[1] + max(0, ((caja[3] - caja[1]) - alto) / 2) - alto * 0.1
            dib.text((caja[0] + 1, y), marc, fill=(0, 0, 0), font=fuente)


def _texto_invisible(pdf, pagina_nueva, fuente, alto_pagina, palabras):
    """Añade, sin que se vea, el texto que queda en la página (para poder buscar y copiar)."""
    for r, texto in palabras:
        if not texto.strip() or r.height <= 0:
            continue
        tam = max(1.0, r.height * 0.85)
        obj = raw.FPDFPageObj_CreateTextObj(pdf, fuente, tam)
        if not obj:
            continue
        wide = ctypes.create_string_buffer((texto + " \0").encode("utf-16-le"))
        raw.FPDFText_SetText(obj, ctypes.cast(wide, ctypes.POINTER(ctypes.c_ushort)))
        raw.FPDFTextObj_SetTextRenderMode(obj, raw.FPDF_TEXTRENDERMODE_INVISIBLE)
        ancho_natural = max(0.1, (len(texto) + 1) * tam * 0.5)
        sx = max(0.2, min(5.0, r.width / ancho_natural))
        y_base = alto_pagina - r.y1 + r.height * 0.2
        raw.FPDFPageObj_Transform(obj, sx, 0, 0, 1, r.x0, y_base)
        raw.FPDFPage_InsertObject(pagina_nueva, obj)


def _en_orden_de_lectura(items):
    """Ordena las palabras por renglones (de arriba abajo) y, dentro de cada uno, de izquierda a derecha."""
    items = sorted(items, key=lambda v: (v[0].y0 + v[0].y1) / 2)
    renglones, actual, centro = [], [], None
    for v in items:
        c = (v[0].y0 + v[0].y1) / 2
        if actual and abs(c - centro) > max(2.0, v[0].height * 0.5):
            renglones.append(actual)
            actual = []
        if not actual:
            centro = c
        actual.append(v)
    if actual:
        renglones.append(actual)
    return [v for r in renglones for v in sorted(r, key=lambda v: v[0].x0)]


@_serializado
def guardar_tachado(origen, destino, tachones_por_pagina, texto_por_pagina=None, escaneadas=()):
    """Escribe el PDF anonimizado.

    tachones_por_pagina: {n.º de página: [(Rect, marcador o ""), ...]}
    texto_por_pagina:    {n.º de página: [(Rect, palabra), ...]} palabras que siguen visibles
    escaneadas:          páginas que eran imagen (se rehacen a más resolución)."""
    texto_por_pagina = texto_por_pagina or {}
    with Documento(origen) as doc:
        nuevo = pdfium.PdfDocument.new()
        fuente = None
        for pag in doc:
            n = pag.number
            tachones = tachones_por_pagina.get(n) or []
            mailto = pag.enlaces_mailto()
            if not tachones and not mailto:
                nuevo.import_pages(doc.pdf, [n])
                continue
            if not tachones:
                nuevo.import_pages(doc.pdf, [n])
                p = nuevo[len(nuevo) - 1]
                for k in sorted(mailto, reverse=True):
                    raw.FPDFPage_RemoveAnnot(p, k)
                p.gen_content()
                p.close()
                continue
            dpi = DPI_ESCANEO if n in escaneadas else DPI_TEXTO
            escala = dpi / 72.0
            img = pag.renderizar(dpi)
            _pintar(img, escala, tachones)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=CALIDAD_JPEG, optimize=True, subsampling=0)
            buf.seek(0)
            p = nuevo.new_page(pag.width, pag.height)
            imagen = pdfium.PdfImage.new(nuevo)
            imagen.load_jpeg(buf, inline=True)
            imagen.set_matrix(pdfium.PdfMatrix().scale(pag.width, pag.height))
            p.insert_obj(imagen)
            if fuente is None:
                fuente = pdfium.PdfFont.load_standard(nuevo, "Helvetica")
            visibles = list(texto_por_pagina.get(n) or [])
            visibles += [(r, marc) for r, marc in tachones if marc]
            visibles = _en_orden_de_lectura(visibles)
            _texto_invisible(nuevo, p, fuente, pag.height, visibles)
            p.gen_content()
            p.close()
        # documento nuevo: no hereda autor, título, programa ni metadatos XMP del original
        nuevo.save(destino)
        nuevo.close()


def imagen_a_pdf(img, destino):
    """Foto o imagen escaneada -> PDF de una página (tamaño aproximado A4 de ancho)."""
    img = img.convert("RGB")
    resolucion = max(72.0, img.width / 8.27)
    img.save(destino, "PDF", resolution=resolucion, quality=92)


@_serializado
def a_imagenes(ruta_pdf, base, dpi=200):
    rutas = []
    with Documento(ruta_pdf) as doc:
        for pag in doc:
            suf = "" if len(doc) == 1 else " p%d" % (pag.number + 1)
            ruta = "%s%s.png" % (base, suf)
            pag.renderizar(dpi).save(ruta)
            rutas.append(ruta)
    return rutas
