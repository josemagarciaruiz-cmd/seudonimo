# -*- coding: utf-8 -*-
"""Seudónimo · lectura y escritura de cada formato.
Word, PowerPoint y Excel se editan por dentro (XML), de modo que el documento
anonimizado conserva su formato, tablas, gráficos e imágenes. Los PDF se leen y se
tachan con PDFium (ver pdfdoc.py)."""
import os
import posixpath
import re
import shutil
import zipfile

from lxml import etree
from PIL import Image, ImageOps

import correo
import motor
import imagenes_office
import ocr
import paginas_office
import pdfdoc
import rutas
from pdfdoc import Rect

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
CH = "http://schemas.openxmlformats.org/drawingml/2006/chart"
PML = "http://schemas.openxmlformats.org/presentationml/2006/main"

TEXTO = {".txt", ".csv", ".tsv", ".md"}
ZIP = {".docx": "docx", ".docm": "docx", ".pptx": "pptx", ".pptm": "pptx",
       ".xlsx": "xlsx", ".xlsm": "xlsx"}
CONVERTIBLES = {".doc": ".docx", ".rtf": ".docx", ".odt": ".docx",
                ".xls": ".xlsx", ".ods": ".xlsx", ".ppt": ".pptx", ".odp": ".pptx"}
IMAGENES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
if rutas.ES_MAC:
    IMAGENES |= {".heic", ".heif"}  # las fotos del iPhone: el Mac las convierte con «sips»
CORREOS = correo.EXTENSIONES          # .eml, .msg y chats de WhatsApp (.zip): se entregan como .txt
ADMITIDOS = TEXTO | set(ZIP) | set(CONVERTIBLES) | IMAGENES | CORREOS | {".pdf"}

_DML = r"charts/chart\d+|diagrams/(?:data|drawing)\d+"
PARTES = {
    "docx": [(re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"), "docx"),
             (re.compile(r"^word/(%s)\.xml$" % _DML), "dml")],
    "pptx": [(re.compile(r"^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$"), "pptx"),
             # patrones y diseños: pies de página y textos fijos («Despacho X · confidencial»)
             (re.compile(r"^ppt/(slideMasters/slideMaster\d+|slideLayouts/slideLayout\d+|notesMasters/notesMaster\d+)\.xml$"), "patron"),
             (re.compile(r"^ppt/(%s)\.xml$" % _DML), "dml")],
    "xlsx": [(re.compile(r"^xl/sharedStrings\.xml$"), "sst"),
             (re.compile(r"^xl/(drawings/drawing\d+|%s)\.xml$" % _DML), "dml"),
             (re.compile(r"^xl/comments(/comment)?\d*\.xml$"), "xlcom"),
             (re.compile(r"^xl/threadedComments/threadedComment\d*\.xml$"), "xlhilo"),
             (re.compile(r"^xl/worksheets/sheet\d+\.xml$"), "hoja")],
}

PARSER = etree.XMLParser(huge_tree=True, resolve_entities=False, remove_blank_text=False)


DPI_REPASO = 360  # resolución de la segunda lectura de las páginas escaneadas


class ErrorFormato(Exception):
    pass


# ---------------------------------------------------------------- conversión

def _soffice():
    candidatos = ["/Applications/LibreOffice.app/Contents/MacOS/soffice", shutil.which("soffice") or ""]
    if rutas.ES_WINDOWS:
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            candidatos.append(os.path.join(base, "LibreOffice", "program", "soffice.exe"))
    for c in candidatos:
        if c and os.path.exists(c):
            return c
    return None


# Conversión con el propio Microsoft Office en Windows (si está instalado).
_OFFICE_PS = {
    ".docx": "$o=New-Object -ComObject Word.Application;$o.Visible=$false;$o.DisplayAlerts=0;"
             "$d=$o.Documents.Open($args[0],$false,$true);$d.SaveAs2($args[1],16);$d.Close($false);$o.Quit()",
    ".xlsx": "$o=New-Object -ComObject Excel.Application;$o.Visible=$false;$o.DisplayAlerts=$false;"
             "$d=$o.Workbooks.Open($args[0],0,$true);$d.SaveAs($args[1],51);$d.Close($false);$o.Quit()",
    ".pptx": "$o=New-Object -ComObject PowerPoint.Application;"
             "$d=$o.Presentations.Open($args[0],$true,$false,$false);$d.SaveAs($args[1],24);$d.Close();$o.Quit()",
}


def _con_office(ruta, salida, nuevo_ext):
    script = _OFFICE_PS.get(nuevo_ext)
    if not script:
        return False
    try:
        rutas.ejecutar(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", "& {%s}" % script, os.path.abspath(ruta), os.path.abspath(salida)],
                       text=True, timeout=180)
    except Exception:
        return False
    return os.path.exists(salida)


def preparar(ruta, carpeta):
    """Convierte los formatos antiguos (.doc, .xls, .ppt…) a los modernos."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext in IMAGENES:
        return _imagen_a_pdf(ruta, ext)
    if ext in CORREOS:
        try:
            salida, aviso = correo.a_texto(ruta, carpeta)
        except correo.ErrorCorreo as e:
            raise ErrorFormato(str(e))
        return salida, ".txt", aviso
    if ext not in CONVERTIBLES:
        return ruta, ext, None
    nuevo_ext = CONVERTIBLES[ext]
    salida = os.path.splitext(ruta)[0] + nuevo_ext
    aviso = ("El archivo %s se ha convertido a %s para poder anonimizarlo; "
             "revisa que el formato se ha conservado." % (ext, nuevo_ext))
    if rutas.ES_MAC and ext in (".doc", ".rtf", ".odt"):
        r = rutas.ejecutar(["/usr/bin/textutil", "-convert", "docx", "-output", salida, ruta], text=True)
        if r.returncode == 0 and os.path.exists(salida):
            return salida, nuevo_ext, aviso
    if rutas.ES_WINDOWS and _con_office(ruta, salida, nuevo_ext):
        return salida, nuevo_ext, aviso
    so = _soffice()
    if so:
        try:
            rutas.ejecutar([so, "--headless", "--convert-to", nuevo_ext[1:], "--outdir", carpeta, ruta],
                           text=True, timeout=180)
        except Exception:
            pass
        if os.path.exists(salida):
            return salida, nuevo_ext, aviso
    raise ErrorFormato(
        "Los archivos %s son del formato antiguo de Office. Ábrelo y guárdalo como %s, "
        "y vuelve a subirlo." % (ext, nuevo_ext))


def _imagen_a_pdf(ruta, ext):
    fuente = ruta
    if ext in (".heic", ".heif"):
        fuente = os.path.splitext(ruta)[0] + "__conv.jpg"
        rutas.ejecutar(["/usr/bin/sips", "-s", "format", "jpeg", ruta, "--out", fuente])
        if not os.path.exists(fuente):
            raise ErrorFormato("No he podido abrir la imagen %s." % os.path.basename(ruta))
    salida = os.path.splitext(ruta)[0] + ".pdf"
    try:
        with Image.open(fuente) as img:
            paginas = []
            for k in range(getattr(img, "n_frames", 1)):  # TIFF de varias páginas
                img.seek(k)
                paginas.append(ImageOps.exif_transpose(img.copy()).convert("RGB"))
        primera = paginas[0]
        resolucion = max(72.0, primera.width / 8.27)
        primera.save(salida, "PDF", resolution=resolucion, quality=92,
                     save_all=len(paginas) > 1, append_images=paginas[1:])
    except Exception:
        raise ErrorFormato("No he podido abrir la imagen %s." % os.path.basename(ruta))
    return salida, ".pdf", None


# ---------------------------------------------------------------- utilidades XML

def _ancestro(el, tags):
    p = el.getparent()
    while p is not None and p.tag not in tags:
        p = p.getparent()
    return p


def _tipo_parte(nombre, familia):
    for rx, kind in PARTES.get(familia, []):
        if rx.match(nombre):
            return kind
    return None


def _unidades(root, kind):
    """Devuelve, párrafo a párrafo, la lista de nodos de texto que lo forman."""
    if kind == "docx":
        P = "{%s}p" % W
        tags = {"{%s}t" % W, "{%s}delText" % W, "{%s}instrText" % W}
        for p in root.iter(P):
            ts = [t for t in p.iter() if t.tag in tags and _ancestro(t, {P}) is p]
            if ts:
                yield ts
    elif kind in ("pptx", "dml", "patron"):
        P, T = "{%s}p" % A, "{%s}t" % A
        SP, PH = "{%s}sp" % PML, "{%s}ph" % PML
        for p in root.iter(P):
            if kind == "patron":
                # en los patrones solo cuenta el texto fijo (un pie, un aviso); el de los marcadores
                # de posición es «Haga clic para modificar…»
                sp = _ancestro(p, {SP})
                ph = next(sp.iter(PH), None) if sp is not None else None
                if ph is not None and ph.get("type") != "ftr":
                    continue
            ts = [t for t in p.iter(T) if _ancestro(t, {P}) is p]
            if ts:
                yield ts
        if kind == "dml":
            # valores de texto guardados en los gráficos (etiquetas de categorías y series que
            # vienen de las celdas: pueden ser nombres)
            for cache in root.iter("{%s}strCache" % CH, "{%s}multiLvlStrCache" % CH):
                for v in cache.iter("{%s}v" % CH):
                    if v.text:
                        yield [v]
    else:
        T, RPH = "{%s}t" % S, "{%s}rPh" % S
        if kind == "xlhilo":   # comentarios encadenados de Excel 365: <text> sin espacio de nombres de hoja
            for t in root.iter():
                if isinstance(t.tag, str) and etree.QName(t).localname == "text" and t.text:
                    yield [t]
            return
        unidad = {"sst": "si", "xlcom": "comment", "hoja": "is"}[kind]
        for u in root.iter("{%s}%s" % (S, unidad)):
            ts = [t for t in u.iter(T) if _ancestro(t, {RPH}) is None]
            if ts:
                yield ts


def _celdas(root):
    """Celdas de Excel con números largos (teléfonos, NAF, CCC) o resultados de fórmula de texto."""
    C, V, F = "{%s}c" % S, "{%s}v" % S, "{%s}f" % S
    for c in root.iter(C):
        v = c.find(V)
        if v is None or not v.text:
            continue
        t = c.get("t")
        if t == "str":
            yield c, v, "str"
        elif t in (None, "n") and c.find(F) is None and re.fullmatch(r"\d{9,12}", v.text.strip()):
            yield c, v, "num"


def _nombres_ordenados(z):
    def natural(n):
        return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", n)]
    return sorted(z.namelist(), key=natural)


# ---------------------------------------------------------------- extracción

def leer_plano(ruta):
    raw = open(ruta, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1"), "latin-1"


def extraer_texto(ruta, ext, comprobar=True, progreso=None, verificar=False, dpi=None):
    if ext in TEXTO:
        return leer_plano(ruta)[0]
    if ext == ".pdf":
        return _extraer_pdf(ruta, comprobar, progreso, verificar, dpi)
    familia = ZIP.get(ext)
    if not familia:
        raise ErrorFormato("Formato no admitido: %s" % ext)
    partes = []
    try:
        with zipfile.ZipFile(ruta) as z:
            for nombre in _nombres_ordenados(z):
                kind = _tipo_parte(nombre, familia)
                if not kind:
                    continue
                root = etree.fromstring(z.read(nombre), PARSER)
                for ts in _unidades(root, kind):
                    partes.append("".join(t.text or "" for t in ts))
                if kind == "hoja":
                    for c, v, _ in _celdas(root):
                        partes.append(v.text)
            if familia == "xlsx" and "xl/workbook.xml" in z.namelist():
                partes += [n for n in nombres_hojas(z.read("xl/workbook.xml")) if n.strip()]
            for nombre in _nombres_ordenados(z):
                if imagenes_office.es_imagen(nombre):
                    t = imagenes_office.texto(z.read(nombre))
                    if t.strip():
                        partes.append(t)
    except zipfile.BadZipFile:
        raise ErrorFormato("El archivo está dañado o protegido con contraseña.")
    return "\n".join(partes)


def necesita_ocr(page, verificar=False):
    """Página escaneada: sin texto seleccionable y con imagen. Al verificar el resultado
    se pasa también por OCR toda página dominada por una imagen."""
    cobertura = page.cobertura_imagen()
    if len(page.get_text().strip()) < 20:
        return cobertura > 0
    return verificar and cobertura > 0.4


def texto_paginas(paginas):
    """«la página 6», «las páginas 6 y 7», «las páginas 3, 6 y 9»."""
    p = [str(x) for x in paginas]
    if len(p) == 1:
        return "la página %s" % p[0]
    return "las páginas %s y %s" % (", ".join(p[:-1]), p[-1])


def recortar_pdf(ruta, paginas, carpeta):
    """Copia del PDF con solo esas páginas (numeradas desde 1), en ese orden."""
    import pypdfium2 as pdfium
    src = pdfium.PdfDocument(ruta)
    try:
        n = len(src)
        malas = [p for p in paginas if not 1 <= p <= n]
        if malas:
            raise ErrorFormato("El documento tiene %d páginas: no existe %s." % (n, texto_paginas(malas)))
        nuevo = pdfium.PdfDocument.new()
        nuevo.import_pages(src, [p - 1 for p in paginas])
        base = os.path.splitext(os.path.basename(ruta))[0]
        salida = os.path.join(carpeta, "%s (pag. %s).pdf" % (base, "-".join(map(str, paginas))[:60]))
        nuevo.save(salida)
        nuevo.close()
        return salida
    finally:
        src.close()


def _abrir_pdf(ruta):
    try:
        return pdfdoc.abrir(ruta)
    except pdfdoc.ErrorPDF as e:
        raise ErrorFormato(str(e))


def extraer_paginas(ruta, ext, progreso=None, verificar=False, dpi=None):
    """Texto de cada página (PDF y Word), diapositiva (PowerPoint) u hoja (Excel); para el resto
    de formatos, una sola «página» con todo el texto."""
    if ext == ".pdf":
        return _paginas_pdf(ruta, progreso, verificar, dpi)
    if ext in ZIP:
        completo = extraer_texto(ruta, ext, comprobar=False)
        try:
            partes = paginas_office.partes(ruta, ext)
        except Exception:  # noqa  (un archivo raro: se trata entero, como antes)
            return [completo]
        # el conjunto tiene que ser el documento entero: lo que no se haya repartido va a la primera
        repartido = set("\n".join(partes).split("\n"))
        resto = [l for l in completo.split("\n") if l.strip() and l not in repartido]
        if resto:
            partes[0] = "\n".join([partes[0]] + resto)
        return partes
    return [extraer_texto(ruta, ext, comprobar=False, progreso=progreso, verificar=verificar, dpi=dpi)]


def unidad(ext, plural=False):
    """Cómo se llaman las partes de un documento: páginas, diapositivas u hojas."""
    return paginas_office.unidad(ext, plural)


def texto_partes(ext, numeros):
    """«la página 6», «las diapositivas 2 y 3», «la hoja 1»."""
    u1, u2 = unidad(ext), unidad(ext, True)
    p = [str(x) for x in numeros]
    if len(p) == 1:
        return "la %s %s" % (u1, p[0])
    return "las %s %s y %s" % (u2, ", ".join(p[:-1]), p[-1])


def recortar(ruta, ext, paginas, carpeta):
    """Copia con solo esas páginas (PDF, Word), diapositivas (PowerPoint) u hojas (Excel)."""
    if ext == ".pdf":
        return recortar_pdf(ruta, paginas, carpeta)
    if ext not in ZIP:
        raise ErrorFormato("Este tipo de archivo no tiene páginas: se seudonimiza entero.")
    base = os.path.splitext(os.path.basename(ruta))[0]
    abrev = {"docx": "pag.", "pptx": "diap.", "xlsx": "hoja"}[ZIP[ext]]
    salida = os.path.join(carpeta, "%s (%s %s)%s" % (base, abrev, "-".join(map(str, paginas))[:60], ext))
    try:
        return paginas_office.recortar(ruta, ext, paginas, salida)
    except paginas_office.ErrorPaginas as e:
        raise ErrorFormato(str(e))


def _extraer_pdf(ruta, comprobar=True, progreso=None, verificar=False, dpi=None):
    texto = "\n".join(_paginas_pdf(ruta, progreso, verificar, dpi))
    if comprobar and not texto.strip():
        raise ErrorFormato("No he encontrado texto en el PDF, ni siquiera con OCR.")
    return texto


def _paginas_pdf(ruta, progreso=None, verificar=False, dpi=None):
    with _abrir_pdf(ruta) as doc:
        escaneadas = [p.number for p in doc if necesita_ocr(p, verificar)]
        if escaneadas and not ocr.DISPONIBLE:
            raise ErrorFormato("El PDF tiene páginas escaneadas y el OCR no está disponible en este equipo.")
        partes = []
        for page in doc:
            t = page.get_text()
            if page.number in escaneadas:
                if progreso:
                    progreso(escaneadas.index(page.number) + 1, len(escaneadas))
                lineas = ocr.leer_pagina(page, None if verificar else (ruta, page.number), dpi=dpi)
                t_ocr = "\n".join(l["texto"] for l in lineas)
                t = (t + "\n" + t_ocr) if verificar else t_ocr
            else:
                # una firma en banda, un pie legal o una foto con texto dentro de una página con
                # texto: no se tapan enteras como los logos, así que se leen con OCR
                lineas = _ocr_imagenes(page, None if verificar else (ruta, page.number), dpi=dpi)
                if lineas:
                    t = t + "\n" + "\n".join(l["texto"] for l in lineas)
            partes.append(t)
    return partes


# ---------------------------------------------------------------- escritura

def aplicar(origen, destino, ext, mapa, opciones=None):
    opciones = opciones or {}
    if ext in TEXTO:
        texto, enc = leer_plano(origen)
        with open(destino, "w", encoding=enc, newline="") as f:
            f.write(motor.reemplazar_texto(texto, mapa))
        return {}
    if ext == ".pdf":
        return _aplicar_pdf(origen, destino, mapa, logos=bool(opciones.get("logos", True)), extra=opciones.get("extra"))
    return _aplicar_zip(origen, destino, ZIP[ext], mapa, logos=bool(opciones.get("logos", True)))


def _preservar(ts):
    for t in ts:
        if t.text and (t.text[0].isspace() or t.text[-1].isspace()):
            t.set(XML_SPACE, "preserve")


def _aplicar_zip(origen, destino, familia, mapa, logos=True):
    info = {"vectoriales": 0, "imagenes_tapadas": 0, "logos": 0, "caras": 0}
    with zipfile.ZipFile(origen) as zin, zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout:
        hojas = {}
        if familia == "xlsx" and "xl/workbook.xml" in zin.namelist():
            hojas = renombrar_hojas_plan(zin.read("xl/workbook.xml"), mapa)
        tam = imagenes_office.tamanos(zin, familia) if logos else {}
        # logotipos vectoriales (EMF/WMF): no se pueden editar, se cambian por una imagen PNG
        vect = {n: posixpath.splitext(n)[0] + "-tapado.png" for n in zin.namelist()
                if imagenes_office.es_vectorial(n) and imagenes_office.es_logo(tam.get(n))}
        for item in zin.infolist():
            data = zin.read(item.filename)
            kind = _tipo_parte(item.filename, familia)
            if item.filename in vect:
                zout.writestr(vect[item.filename], imagenes_office.marcador_logo(*_tamano_vectorial(tam.get(item.filename))))
                info["logos"] += 1
                continue
            if imagenes_office.es_imagen(item.filename):
                nueva, que = imagenes_office.tapar(data, item.filename, mapa,
                                                   logo=logos and imagenes_office.es_logo(tam.get(item.filename)), caras=logos)
                if nueva is not None:
                    data = nueva
                    info["imagenes_tapadas"] += 1
                    if que == "logo":
                        info["logos"] += 1
                    elif que == "caras":
                        info["caras"] += 1
                zout.writestr(item, data)
                continue
            if vect and item.filename.endswith(".rels"):
                data = _cambiar_destinos(data, item.filename, vect)
            if vect and item.filename == "[Content_Types].xml":
                data = _tipos_png(data, vect)
            if imagenes_office.es_vectorial(item.filename):
                info["vectoriales"] += 1
            if hojas and item.filename.endswith(".xml") and (item.filename.startswith("xl/") or item.filename == "docProps/app.xml"):
                data = _aplicar_hojas(data, hojas)
            if kind:
                root = etree.fromstring(data, PARSER)
                for ts in _unidades(root, kind):
                    if motor.reemplazar_segmentos(ts, mapa) and kind != "pptx":
                        _preservar(ts)
                if kind == "hoja":
                    for c, v, clase in _celdas(root):
                        nuevo = motor.reemplazar_texto(v.text.strip(), mapa)
                        if nuevo == v.text.strip():
                            continue
                        if clase == "str":
                            v.text = nuevo
                        else:
                            c.remove(v)
                            c.set("t", "inlineStr")
                            is_ = etree.SubElement(c, "{%s}is" % S)
                            etree.SubElement(is_, "{%s}t" % S).text = nuevo
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            elif item.filename == "docProps/core.xml":
                data = _limpiar_propiedades(data, mapa, borrar={"creator", "lastModifiedBy"})
            elif item.filename == "docProps/app.xml":
                # «lpstr»: títulos de las diapositivas y nombres de las hojas (TitlesOfParts)
                data = _limpiar_propiedades(data, mapa, borrar={"Company", "Manager"}, extra={"lpstr"})
            elif item.filename.endswith(".rels"):
                data = _limpiar_rels(data, mapa)
            elif item.filename == "docProps/custom.xml":
                data = _limpiar_propiedades(data, mapa, borrar=set(), todas=True)
            if item.filename.endswith(".xml"):
                data = _limpiar_autoria(data)
            zout.writestr(item, data)
    return info


def _tamano_vectorial(fr):
    """Tamaño en píxeles del recuadro que sustituye a un logotipo vectorial (proporción de la página)."""
    if not fr:
        return 300, 120
    ancho = max(60, int(1600 * fr[1]))
    alto = max(30, int(2260 * fr[2]))
    return min(ancho, 1600), min(alto, 2260)


def _cambiar_destinos(data, nombre_rels, cambios):
    root = etree.fromstring(data, PARSER)
    base = posixpath.dirname(posixpath.dirname(nombre_rels))
    tocado = False
    for r in root:
        t = r.get("Target") or ""
        if r.get("TargetMode") == "External":
            continue
        destino = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join(base, t))
        if destino in cambios:
            nuevo = cambios[destino]
            r.set("Target", "/" + nuevo if t.startswith("/") else posixpath.relpath(nuevo, base or "."))
            tocado = True
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True) if tocado else data


def _tipos_png(data, cambios):
    CTN = "http://schemas.openxmlformats.org/package/2006/content-types"
    root = etree.fromstring(data, PARSER)
    for o in list(root.iter("{%s}Override" % CTN)):
        if (o.get("PartName") or "").lstrip("/") in cambios:
            root.remove(o)
    if not any((d.get("Extension") or "").lower() == "png" for d in root.iter("{%s}Default" % CTN)):
        etree.SubElement(root, "{%s}Default" % CTN, Extension="png", ContentType="image/png")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


# ---------------------------------------------------------------- nombres de las hojas de Excel

_PROHIBIDOS_HOJA = re.compile(r"[\[\]:*?/\\]")


def nombres_hojas(data):
    root = etree.fromstring(data, PARSER)
    return [h.get("name") or "" for h in root.iter("{%s}sheet" % S)]


def renombrar_hojas_plan(data, mapa):
    """{nombre viejo: nombre nuevo} de las hojas cuyo nombre lleva algún dato. En un nombre de
    hoja no caben corchetes, así que el marcador va sin ellos («Nóminas PERSONA_001»)."""
    viejos = nombres_hojas(data)
    usados = {v.lower() for v in viejos}
    plan = {}
    for v in viejos:
        nuevo = motor.reemplazar_texto(v, mapa)
        if nuevo == v:
            continue
        nuevo = re.sub(r"\[([A-Z_]+_\d+)\]", r"\1", nuevo)
        nuevo = _PROHIBIDOS_HOJA.sub(" ", nuevo).strip().strip("'")[:31].strip() or "Hoja"
        base, n = nuevo, 2
        while nuevo.lower() in usados:
            suf = " (%d)" % n
            nuevo = base[:31 - len(suf)] + suf
            n += 1
        usados.add(nuevo.lower())
        plan[v] = nuevo
    return plan


def _ref_hoja(nombre):
    return "'%s'" % nombre.replace("'", "''")


def _cambiar_refs(texto, plan):
    """Cambia las referencias a hojas renombradas dentro de una fórmula: 'Ana Ruiz'!A1, Datos!B2."""
    for viejo, nuevo in plan.items():
        texto = texto.replace(_ref_hoja(viejo) + "!", _ref_hoja(nuevo) + "!")
        if re.fullmatch(r"[^\W\d][\w.]*", viejo):
            texto = re.sub(r"(?<![\w.'])" + re.escape(viejo) + r"!", lambda m: _ref_hoja(nuevo) + "!", texto)
    return texto


_FORMULAS = {"f", "definedName", "formula", "formula1", "formula2"}


def _aplicar_hojas(data, plan):
    """Renombra las hojas en el libro y en todo lo que las nombra: fórmulas, nombres definidos,
    gráficos, validaciones, hipervínculos internos, tablas dinámicas y propiedades del archivo."""
    # los nombres pueden ir con referencias de carácter (N&#243;minas): se mira en el texto ya leído
    try:
        root = etree.fromstring(data, PARSER)
    except etree.XMLSyntaxError:
        return data
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        local = etree.QName(el).localname
        if local == "sheet" and el.get("name") in plan:
            el.set("name", plan[el.get("name")])
        if local in _FORMULAS and el.text:
            el.text = _cambiar_refs(el.text, plan)
        if local == "lpstr" and el.text in plan:          # docProps/app.xml
            el.text = plan[el.text]
        for atributo in ("location", "ref", "sqref"):
            if el.get(atributo) and "!" in el.get(atributo):
                el.set(atributo, _cambiar_refs(el.get(atributo), plan))
        if local == "worksheetSource" and el.get("sheet") in plan:   # origen de una tabla dinámica
            el.set("sheet", plan[el.get("sheet")])
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


_AUTORIA = {"author", "initials", "userId", "providerId", "lastModifiedBy", "creator"}


def _limpiar_autoria(data):
    """Autores de comentarios, de cambios controlados y de personas (word/people.xml,
    xl/persons): son nombres reales y no forman parte del texto del documento."""
    if not any(x in data for x in (b"author", b"initials", b"userId", b"displayName")):
        return data
    try:
        root = etree.fromstring(data, PARSER)
    except Exception:
        return data
    cambiado = False
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        for a in list(el.attrib):
            local = etree.QName(a).localname
            if local in _AUTORIA or local == "displayName":
                el.set(a, "R" if local == "initials" else ("" if local in ("userId", "providerId") else "Revisor"))
                cambiado = True
        if etree.QName(el).localname == "author" and el.text and el.text.strip():
            el.text = "Revisor"          # <authors><author>…</author> de los comentarios de Excel
            cambiado = True
    if not cambiado:
        return data
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _limpiar_propiedades(data, mapa, borrar, todas=False, extra=()):
    try:
        root = etree.fromstring(data, PARSER)
    except Exception:
        return data
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        local = etree.QName(el).localname
        if local in borrar:
            el.text = ""
        elif el.text and (todas or local in {"title", "subject", "description", "keywords", "category"} or local in extra):
            el.text = motor.reemplazar_texto(el.text, mapa)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _limpiar_rels(data, mapa):
    if b"mailto:" not in data and b"@" not in data:
        return data
    try:
        root = etree.fromstring(data, PARSER)
    except Exception:
        return data
    for el in root.iter():
        destino = el.get("Target") if isinstance(el.tag, str) else None
        if destino and ("mailto:" in destino.lower() or "@" in destino):
            el.set("Target", "mailto:anonimizado")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _limpia(s):
    return motor.clave(s).strip(".,;:()[]\"'«»¿?¡!")


def _rects_por_palabras(palabras, frase):
    """Localiza la frase palabra a palabra, respetando los límites de cada palabra
    (así «Ana» no tacha un trozo de «semana»). Devuelve un grupo de rectángulos
    por cada aparición (uno por línea si la frase salta de línea)."""
    obj = [x for x in (_limpia(p) for p in frase.split()) if x]
    if not obj:
        return []
    norm = [_limpia(w[4]) for w in palabras]
    grupos, n = [], len(obj)
    for i in range(len(norm) - n + 1):
        if norm[i:i + n] == obj:
            por_linea = {}
            for w in palabras[i:i + n]:
                k, r = (w[5], w[6]), Rect(w[:4])
                por_linea[k] = por_linea[k] | r if k in por_linea else r
            grupos.append(list(por_linea.values()))
    return grupos


def _dentro(r, u):
    inter = r & u
    return (not inter.is_empty) and inter.get_area() >= 0.8 * max(r.get_area(), 0.01)


def _toca(r, tachones):
    """¿La palabra queda (aunque sea en parte) bajo algún tachón? Entonces no se conserva."""
    for t, _ in tachones:
        inter = r & t
        if not inter.is_empty and inter.get_area() >= 0.15 * max(r.get_area(), 0.01):
            return True
    return False


def _tachar_texto(page, mapa, no_localizados):
    """Página con texto: devuelve los tachones [(Rect, marcador)] y las palabras que quedan."""
    texto = page.get_text()
    hall = motor.coincidencias(texto, mapa)
    if not hall:
        return [], []
    palabras = page.palabras()
    frases = {}
    for ini, fin, marc in hall:
        frases.setdefault(texto[ini:fin], marc)
    tachones, usados = [], []
    # primero las frases largas: «María López Herrera» antes que «López Herrera»
    for frase, marc in sorted(frases.items(), key=lambda x: -len(x[0])):
        grupos = _rects_por_palabras(palabras, frase)
        if not grupos:
            # la frase va partida en el PDF (otra línea, otra columna): se buscan sus trozos
            for linea in [x for x in re.split(r"\s*\n\s*|,\s*", frase) if len(x.strip()) >= 4]:
                grupos += page.buscar(linea)
        if not grupos:
            no_localizados.append(frase.replace("\n", " "))
            continue
        for grupo in grupos:
            grupo = [r for r in grupo if not any(_dentro(r, u) for u in usados)]
            for k, r in enumerate(grupo):
                tachones.append((r.ampliar(0.3, 0.3), marc if k == 0 else ""))
                usados.append(r)
    quedan = [(Rect(w[:4]), w[4]) for w in palabras if not _toca(Rect(w[:4]), tachones)]
    return tachones, quedan


def _tachar_ocr(page, mapa, origen, previos=()):
    """Página escaneada: se localiza cada dato con el OCR y se tapa en la imagen."""
    lineas = ocr.leer_pagina(page, (origen, page.number))
    offs, acc = [], 0
    for l in lineas:
        offs.append(acc)
        acc += len(l["texto"]) + 1
    completo = "\n".join(l["texto"] for l in lineas)
    tachones = list(previos)
    for ini, fin, marc in motor.coincidencias(completo, mapa):
        primero = True
        for l, o in zip(lineas, offs):
            a, b = max(ini, o), min(fin, o + len(l["texto"]))
            if a < b:
                tachones.append((ocr.rect_fragmento(l, a - o, b - o), marc if primero else ""))
                primero = False
    # Repaso: se vuelve a leer la página ya tapada, a otra resolución. El OCR no lee igual
    # dos veces; lo que se le escapó en la primera lectura (un DNI, una fecha, un nombre)
    # aparece ahora y se tapa también. Es lo que antes había que hacer a mano con varias pasadas.
    for dpi in (DPI_REPASO, DPI_REPASO + 60):
        img = page.renderizar(dpi)
        pdfdoc._pintar(img, dpi / 72.0, tachones)
        otras = ocr.leer_imagen(img, page)
        texto2 = "\n".join(l["texto"] for l in otras)
        offs2, acc = [], 0
        for l in otras:
            offs2.append(acc)
            acc += len(l["texto"]) + 1
        nuevos = []
        for ini, fin, marc in motor.coincidencias(texto2, mapa):
            if re.fullmatch(r"\[[A-Z_]+_\d+\]", texto2[ini:fin]):
                continue
            for l, o in zip(otras, offs2):
                a, b = max(ini, o), min(fin, o + len(l["texto"]))
                if a < b:
                    nuevos.append((ocr.rect_fragmento(l, a - o, b - o), ""))
        if not nuevos:
            break
        tachones += nuevos
    quedan = []
    if tachones:
        for l in lineas:
            for r, a, b in l["palabras"]:
                if not _toca(r, tachones):
                    quedan.append((r, l["texto"][a:b]))
    return tachones, quedan


MARCA_LOGO = "[LOGO O SELLO]"


def _logos_incrustados(page):
    """Logotipos, escudos y sellos que van como imagen aparte dentro de la página.
    Se dejan las imágenes grandes (una foto, un documento escaneado pegado), que son contenido."""
    W, H = page.width, page.height
    res = []
    for r in page.imagenes():
        if r.width < 8 or r.height < 8:
            continue
        if r.get_area() > 0.12 * W * H or r.width > 0.6 * W or r.height > 0.45 * H:
            continue
        res.append((r.ampliar(1.5, 1.5), MARCA_LOGO))
    return res


def _caras_pagina(page, dpi=110):
    """Caras en las fotos de una página (una foto de carné escaneada, una fotografía pegada):
    se tapan enteras con «[CARA]». Solo se mira si la página tiene alguna imagen."""
    import rostros
    if not rostros.DISPONIBLE:
        return []
    try:
        if not page.imagenes() and not necesita_ocr(page):
            return []
        img = page.renderizar(dpi)
    except Exception:  # noqa
        return []
    e = dpi / 72.0
    return [(pdfdoc.Rect(x0 / e, y0 / e, x1 / e, y1 / e), rostros.MARCA) for x0, y0, x1, y1 in rostros.caras(img)]


def _imagenes_contenido(page):
    """Las imágenes que _logos_incrustados deja como contenido (grandes o en banda ancha)."""
    W, H = page.width, page.height
    return [r for r in page.imagenes() if r.width >= 8 and r.height >= 8 and
            (r.get_area() > 0.12 * W * H or r.width > 0.6 * W or r.height > 0.45 * H)]


def _ocr_imagenes(page, clave=None, dpi=None):
    """Líneas de OCR que caen dentro de las imágenes grandes de una página que tiene texto:
    la firma de un correo hecha imagen, el pie legal, una foto con un nombre. Sin esto, lo
    que pone en ellas no lo ve ni la detección ni la verificación."""
    if not ocr.DISPONIBLE:
        return []
    rects = [r.ampliar(2, 2) for r in _imagenes_contenido(page)]
    if not rects:
        return []
    try:
        lineas = ocr.leer_pagina(page, clave, dpi=dpi)
    except Exception:  # noqa
        return []
    return [l for l in lineas if any(_dentro(l["rect"], r) for r in rects)]


def _tachar_lineas(lineas, mapa):
    """Tachones sobre los datos conocidos que aparecen en unas líneas de OCR."""
    if not lineas:
        return []
    offs, acc = [], 0
    for l in lineas:
        offs.append(acc)
        acc += len(l["texto"]) + 1
    completo = "\n".join(l["texto"] for l in lineas)
    res = []
    for ini, fin, marc in motor.coincidencias(completo, mapa):
        primero = True
        for l, o in zip(lineas, offs):
            a, b = max(ini, o), min(fin, o + len(l["texto"]))
            if a < b:
                res.append((ocr.rect_fragmento(l, a - o, b - o), marc if primero else ""))
                primero = False
    return res


def _manchas_de_color(page, ya_tapado, dpi=100):
    """Sellos, firmas y logotipos en páginas escaneadas: zonas compactas de color vivo
    (tinta azul o morada de un sello, los colores de un escudo) sobre un documento que,
    por lo demás, es blanco y negro. Devuelve sus rectángulos en coordenadas de página."""
    img = page.renderizar(dpi)
    escala = dpi / 72.0
    paso = 6  # celdas de 6 px: ~4 puntos de página
    hsv = img.convert("HSV")
    h, w = img.height, img.width
    cw, ch = (w + paso - 1) // paso, (h + paso - 1) // paso
    px = hsv.load()
    celdas = set()
    for cy in range(ch):
        for cx in range(cw):
            vivos = 0
            for y in range(cy * paso, min(h, cy * paso + paso), 2):
                for x in range(cx * paso, min(w, cx * paso + paso), 2):
                    _, s_, v_ = px[x, y]
                    if s_ > 70 and v_ > 60:
                        vivos += 1
                        if vivos >= 3:
                            break
                if vivos >= 3:
                    break
            if vivos >= 3:
                celdas.add((cx, cy))
    # componentes conexos (con un hueco de una celda de tolerancia)
    vistos, res = set(), []
    for c in celdas:
        if c in vistos:
            continue
        cola, comp = [c], []
        vistos.add(c)
        while cola:
            x, y = cola.pop()
            comp.append((x, y))
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    n = (x + dx, y + dy)
                    if n in celdas and n not in vistos:
                        vistos.add(n)
                        cola.append(n)
        if len(comp) < 6:
            continue
        xs = [x for x, _ in comp]
        ys = [y for _, y in comp]
        r = Rect(min(xs) * paso / escala, min(ys) * paso / escala,
                 (max(xs) + 1) * paso / escala, (max(ys) + 1) * paso / escala)
        # tamaño de un sello o un logotipo: ni una línea ni media página
        if r.width < 12 or r.height < 12:
            continue
        if r.width > 0.5 * page.width or r.height > 0.3 * page.height:
            continue
        if r.get_area() > 0.08 * page.width * page.height:
            continue
        # una línea de texto en color (un título azul) es mucho más ancha que alta; un sello o un logotipo, no
        if r.width > 2.8 * r.height or r.height > 2.8 * r.width:
            continue
        if any(_dentro(r, u) for u, _ in ya_tapado):
            continue
        res.append((r.ampliar(2, 2), MARCA_LOGO))
    return res


def _aplicar_pdf(origen, destino, mapa, logos=True, extra=None):
    """extra: {página: [(Rect, marcador)]} con zonas que la verificación encontró aún visibles y
    que se tapan además de lo que localiza la edición (ver localizar_restos)."""
    no_localizados = []
    tachones, visibles, escaneadas = {}, {}, set()
    extra = extra or {}
    with _abrir_pdf(origen) as doc:
        for page in doc:
            previos = (_logos_incrustados(page) + _caras_pagina(page) if logos else []) + list(extra.get(page.number, []))
            if necesita_ocr(page):
                escaneadas.add(page.number)
                t, q = _tachar_ocr(page, mapa, origen, previos)
                if logos:
                    t += _manchas_de_color(page, t)
            else:
                t, q = _tachar_texto(page, mapa, no_localizados)
                t += previos
                t += _tachar_lineas(_ocr_imagenes(page, (origen, page.number)), mapa)
            if t:
                q = [(r, w) for r, w in q if not _toca(r, t)]
                tachones[page.number], visibles[page.number] = t, q
    pdfdoc.guardar_tachado(origen, destino, tachones, visibles, escaneadas)
    return {"no_localizados": sorted(set(no_localizados))}


def localizar_restos(ruta, restos, dpi=None):
    """Dónde siguen a la vista, en una copia ya tapada, los datos conocidos que la verificación ha
    encontrado («restos»). Mira la capa de texto y vuelve a leer con OCR cada página con imagen, a
    la resolución de la verificación. Devuelve {página: [(Rect, marcador)]}: el siguiente ciclo los
    tapa sobre el original aunque la edición no haya sabido localizarlos (un dato partido entre
    líneas, leído de otra forma por el OCR…)."""
    res = {}
    if not restos:
        return res
    with _abrir_pdf(ruta) as doc:
        for page in doc:
            zonas = []
            texto = page.get_text()
            if texto.strip():
                palabras = page.palabras()
                for ini, fin, marc in motor.coincidencias(texto, restos):
                    frase = texto[ini:fin]
                    grupos = _rects_por_palabras(palabras, frase) or page.buscar(frase)
                    for grupo in grupos:
                        zonas += [(r.ampliar(0.3, 0.3), "") for r in grupo]
            lineas = None
            if necesita_ocr(page, verificar=True) and ocr.DISPONIBLE:
                lineas = ocr.leer_pagina(page, None, dpi=dpi)
            elif texto.strip():
                lineas = _ocr_imagenes(page, None, dpi=dpi)
            if lineas:
                offs, acc = [], 0
                for l in lineas:
                    offs.append(acc)
                    acc += len(l["texto"]) + 1
                completo = "\n".join(l["texto"] for l in lineas)
                for ini, fin, marc in motor.coincidencias(completo, restos):
                    if re.fullmatch(r"\[[A-Z_]+_\d+\]", completo[ini:fin]):
                        continue
                    for l, o in zip(lineas, offs):
                        a, b = max(ini, o), min(fin, o + len(l["texto"]))
                        if a < b:
                            zonas.append((ocr.rect_fragmento(l, a - o, b - o), ""))
            if zonas:
                res[page.number] = zonas
    return res


def pdf_a_imagenes(pdf, base):
    """Para documentos que llegaron como foto: devuelve también la imagen anonimizada."""
    return pdfdoc.a_imagenes(pdf, base, dpi=200)
