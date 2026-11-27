# -*- coding: utf-8 -*-
"""Verificación independiente de un documento ya seudonimizado.

No se fía del texto que produjo la pasada anterior: reabre el archivo exportado desde el disco,
vuelve a extraer el texto (y el OCR, a otra resolución), busca los datos originales conocidos
del proyecto en todas sus variantes, vuelve a pasar las reglas, pide a un modelo auditor (con un
prompt distinto del de detección) que busque restos, e inspecciona la estructura del archivo:
metadatos, comentarios, control de cambios, hojas ocultas, objetos incrustados, adjuntos,
revisiones incrementales y metadatos EXIF.

La ausencia de hallazgos NO demuestra la ausencia de datos personales desconocidos: el
resultado se expresa como «sin hallazgos en las comprobaciones configuradas»."""
import io
import os
import re
import zipfile

from lxml import etree
from PIL import Image

import formatos
import motor
import ocr
import pdfdoc

# Métodos de verificación: cada ciclo usa uno distinto para que las pasadas no repitan los
# mismos errores (otra resolución de OCR, otro prompt, otros cortes entre fragmentos).
METODOS = [
    {"nombre": "A", "dpi": 300, "prompt": "auditoria", "desfase": 1250},
    {"nombre": "B", "dpi": 420, "prompt": "auditoria_b", "desfase": 600},
    {"nombre": "C", "dpi": 360, "prompt": "auditoria", "desfase": 1900},
]

INCIDENCIAS_GRAVES = {"dato_en_metadatos", "dato_en_parte_oculta", "dato_en_imagen", "adjuntos_pdf",
                      "objeto_incrustado", "exif", "control_de_cambios"}


def metodo(ciclo):
    return METODOS[ciclo % len(METODOS)]


def _hay_conocido(texto, mapa):
    """Marcadores cuyos datos originales siguen apareciendo en el texto (sin devolver el dato)."""
    restos = []
    for e in mapa:
        if motor.patron(e["texto"], e.get("tipo")).search(texto):
            restos.append(e)
    return restos


def verificar(salida, ext, registro, opciones=None, progreso=None, cancelado=None):
    """Devuelve {"metodo", "restos":[...], "nuevos":[...], "incidencias":[...], "texto_len"}.
    «restos»: datos ya registrados que siguen en la salida (no se localizaron al editar).
    «nuevos»: datos que el registro no conocía (reglas o auditor), para incorporar.
    «incidencias»: problemas de estructura, con «grave» si impiden aprobar."""
    opciones = opciones or {}
    m = metodo(opciones.get("ciclo", 0))
    usar_modelo = opciones.get("modelo_auditor", True)
    res = {"metodo": m["nombre"], "restos": [], "nuevos": [], "incidencias": []}

    # 1. Extracción independiente desde el disco (texto nativo + OCR de toda página con imagen)
    if progreso:
        progreso(0.05, "verificación %s: releyendo el archivo exportado…" % m["nombre"])
    try:
        texto = formatos.extraer_texto(salida, ext, comprobar=False, verificar=True, dpi=m["dpi"])
    except Exception as e:  # noqa
        res["incidencias"].append({"tipo": "error_extraccion", "detalle": str(e)[:200], "grave": True})
        return res
    res["texto_len"] = len(texto)
    res["texto"] = texto     # solo en memoria, para el controlador; nunca va al informe
    mapa = registro.mapa()

    # 2. Datos originales conocidos (de todo el proyecto, no solo de este documento)
    vistos = set()
    for e in _hay_conocido(texto, mapa):
        if e["marcador"] not in vistos:
            vistos.add(e["marcador"])
            res["restos"].append({"marcador": e["marcador"], "tipo": e["tipo"], "texto": e["texto"]})

    # Los marcadores, también como los deforma el OCR («[CSV_001]» leído «tcsv_001»), no son datos
    limpio = motor.MARCADOR_OCR.sub(lambda x: " " * len(x.group(0)), texto)

    # 3. Reglas deterministas sobre la salida
    for d in motor.detectar_regex(limpio):
        if not registro.buscar(d["texto"]) and motor.clave_dato(d["texto"]) not in registro.descartados:
            d["origen"] = "Verificación · regla"
            res["nuevos"].append(d)

    # 4. Modelo auditor, con un prompt distinto del de detección y otros cortes
    if usar_modelo and limpio.strip() and not (cancelado and cancelado()):
        def avance(i, t):
            if progreso:
                progreso(0.15 + 0.8 * i / max(t, 1), "verificación %s: el modelo auditor lee el fragmento %d de %d" % (m["nombre"], i, t))
        for d in motor.detectar_gemma(limpio, avance, costura=False, prompt=motor.PROMPTS[m["prompt"]],
                                      modelo=opciones.get("modelo"), desfase=m["desfase"], cancelado=cancelado,
                                      origen="Verificación · auditor %s" % m["nombre"]):
            if registro.buscar(d["texto"]) or motor.clave_dato(d["texto"]) in registro.descartados:
                continue
            res["nuevos"].append(d)
        res["nuevos"] = motor.filtrar_fechas(res["nuevos"], limpio)

    # 5. Estructura del archivo
    res["incidencias"] += estructura(salida, ext, mapa)

    # 6. Caras: se vuelven a buscar en la copia, con el detector desde cero
    if opciones.get("caras") and not (cancelado and cancelado()):
        if progreso:
            progreso(0.97, "verificación %s: buscando caras en las imágenes de la copia…" % m["nombre"])
        try:
            res["caras"] = formatos.caras_en(salida, ext)
        except Exception as e:  # noqa
            res["incidencias"].append({"tipo": "error_caras", "grave": False,
                                       "detalle": "No se han podido revisar las caras de la copia: %s" % str(e)[:120]})
    return res


# ---------------------------------------------------------------- estructura

def estructura(ruta, ext, mapa):
    try:
        if ext == ".pdf":
            return _estructura_pdf(ruta, mapa)
        if ext in formatos.ZIP:
            return _estructura_ooxml(ruta, mapa)
        if ext.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"):
            return _estructura_imagen(ruta)
    except Exception as e:  # noqa
        return [{"tipo": "error_estructura", "detalle": str(e)[:200], "grave": True}]
    return []


def _estructura_pdf(ruta, mapa):
    inc = []
    raw = open(ruta, "rb").read()
    if raw.count(b"%%EOF") > 1:
        inc.append({"tipo": "revisiones_incrementales", "grave": True,
                    "detalle": "El PDF conserva revisiones anteriores que podrían contener el texto original."})
    import pypdfium2 as pdfium
    import pypdfium2.raw as praw
    doc = pdfium.PdfDocument(ruta)
    try:
        meta = doc.get_metadata_dict(skip_empty=True)
        texto_meta = " ".join(str(v) for v in meta.values())
        if texto_meta and _hay_conocido(texto_meta, mapa):
            inc.append({"tipo": "dato_en_metadatos", "grave": True, "detalle": "Los metadatos del PDF contienen datos originales."})
        n_adj = praw.FPDFDoc_GetAttachmentCount(doc.raw)
        if n_adj:
            inc.append({"tipo": "adjuntos_pdf", "grave": True, "detalle": "El PDF lleva %d archivo(s) adjunto(s) sin revisar." % n_adj})
        anot = 0
        for i in range(len(doc)):
            pag = doc[i]
            anot += praw.FPDFPage_GetAnnotCount(pag.raw)
            pag.close()
        if anot:
            inc.append({"tipo": "anotaciones", "grave": False,
                        "detalle": "El PDF tiene %d anotación(es); su texto se ha revisado con la extracción." % anot})
    finally:
        doc.close()
    return inc


_PARTES_VISIBLES = re.compile(r"^(word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml|"
                              r"xl/(sharedStrings|worksheets/sheet\d+)\.xml|ppt/slides/slide\d+\.xml)$")


def _estructura_ooxml(ruta, mapa):
    inc = []
    with zipfile.ZipFile(ruta) as z:
        nombres = z.namelist()
        for n in nombres:
            if not n.endswith((".xml", ".rels")):
                continue
            data = z.read(n)
            try:
                root = etree.fromstring(data, formatos.PARSER)
                texto = " ".join(t for t in root.itertext())
                # los atributos también: títulos, textos alternativos de imágenes, nombres de autor
                texto += " " + " ".join(v for el in root.iter() for v in el.attrib.values())
            except Exception:
                texto = data.decode("utf-8", "ignore")
            restos = _hay_conocido(texto, mapa)
            if restos and not _PARTES_VISIBLES.match(n):
                tipo = "dato_en_metadatos" if n.startswith("docProps/") else "dato_en_parte_oculta"
                inc.append({"tipo": tipo, "grave": True,
                            "detalle": "La parte interna «%s» contiene %d dato(s) original(es) (%s)." % (
                                n, len(restos), ", ".join(sorted({e["marcador"] for e in restos})))})
            if n == "word/document.xml" and (b"<w:del " in data or b"<w:ins " in data or b"<w:delText" in data):
                inc.append({"tipo": "control_de_cambios", "grave": True,
                            "detalle": "El documento conserva control de cambios: el texto eliminado sigue dentro."})
            if n == "xl/workbook.xml" and re.search(rb'state="(very)?[hH]idden"', data):
                inc.append({"tipo": "hojas_ocultas", "grave": False,
                            "detalle": "El libro tiene hojas ocultas; se han seudonimizado igual que las visibles."})
        incrustados = [n for n in nombres if "/embeddings/" in n]
        if incrustados:
            inc.append({"tipo": "objeto_incrustado", "grave": True,
                        "detalle": "Hay %d objeto(s) incrustado(s) (otros documentos dentro de este) que no se pueden revisar." % len(incrustados)})
        if any(n.startswith("xl/pivotCache/") for n in nombres):
            inc.append({"tipo": "cache_tabla_dinamica", "grave": False,
                        "detalle": "El libro tiene cachés de tablas dinámicas; se han revisado como texto."})
        # imágenes dentro del documento: OCR y búsqueda de datos originales y de reglas
        medios = [n for n in nombres if "/media/" in n and n.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"))]
        if medios and ocr.DISPONIBLE:
            for n in medios[:20]:
                try:
                    img = Image.open(io.BytesIO(z.read(n))).convert("RGB")
                    if img.width < 120 or img.height < 40:
                        continue
                    lineas = ocr.leer_imagen(img, _PaginaFalsa(img))
                    t = "\n".join(l["texto"] for l in lineas)
                    if _hay_conocido(t, mapa) or motor.detectar_regex(t):
                        inc.append({"tipo": "dato_en_imagen", "grave": True,
                                    "detalle": "La imagen interna «%s» contiene texto con datos identificativos." % os.path.basename(n)})
                except Exception:
                    continue
    return inc


class _PaginaFalsa:
    """Para pasar una imagen suelta al OCR, que trabaja en coordenadas de página."""
    def __init__(self, img):
        self.width, self.height = img.width, img.height
        self.rect = pdfdoc.Rect(0, 0, img.width, img.height)


def _estructura_imagen(ruta):
    img = Image.open(ruta)
    if img.getexif() or img.info.get("exif"):
        return [{"tipo": "exif", "grave": True, "detalle": "La imagen conserva metadatos EXIF."}]
    return []
