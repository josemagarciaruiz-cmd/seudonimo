# -*- coding: utf-8 -*-
"""Páginas de Word, diapositivas de PowerPoint y hojas de Excel.

- Texto de cada parte, para repasar solo unas páginas («repasa la diapositiva 3»).
- Copia con solo esas partes («seudonimiza solo la hoja 2»), sin dejar dentro del archivo
  nada de lo que se quita: se borran las diapositivas, hojas e imágenes que ya no se usan,
  se vacían los textos compartidos de Excel que solo usaban las hojas quitadas y las notas,
  comentarios y notas al pie que solo estaban en las páginas quitadas.

Word no guarda páginas: las calcula al mostrar el documento. Al guardar, Word apunta dónde
empezaba cada página (<w:lastRenderedPageBreak/>); se usa eso. Si el documento no lo tiene
(hecho con otro programa), solo se cuentan los saltos de página y de sección explícitos."""
import posixpath
import re
import zipfile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
EP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"

PARSER = etree.XMLParser(huge_tree=True, resolve_entities=False, remove_blank_text=False)
FAMILIAS = {".docx": "docx", ".docm": "docx", ".pptx": "pptx", ".pptm": "pptx", ".xlsx": "xlsx", ".xlsm": "xlsx"}
UNIDAD = {"docx": ("página", "páginas"), "pptx": ("diapositiva", "diapositivas"), "xlsx": ("hoja", "hojas")}


class ErrorPaginas(Exception):
    pass


def unidad(ext, plural=False):
    return UNIDAD.get(FAMILIAS.get(ext, ""), ("página", "páginas"))[1 if plural else 0]


def _q(ns, tag):
    return "{%s}%s" % (ns, tag)


def _xml(z, nombre):
    return etree.fromstring(z.read(nombre), PARSER)


def _rels_de(parte):
    d, n = posixpath.split(parte)
    return posixpath.join(d, "_rels", n + ".rels")


def _relaciones(z, parte):
    """{rId: (tipo, destino absoluto dentro del paquete, externo)} de una parte."""
    nombre = _rels_de(parte)
    if nombre not in z.namelist():
        return {}
    res = {}
    base = posixpath.dirname(parte)
    for r in _xml(z, nombre).iter(_q(PR, "Relationship")):
        externo = r.get("TargetMode") == "External"
        destino = r.get("Target") or ""
        if not externo:
            destino = destino.lstrip("/") if destino.startswith("/") else posixpath.normpath(posixpath.join(base, destino))
        res[r.get("Id")] = (r.get("Type") or "", destino, externo)
    return res


def _texto(root, ns_t, ns_p):
    lineas = []
    for p in root.iter(_q(ns_p, "p") if ns_p != S else _q(S, "si")):
        t = "".join(x.text or "" for x in p.iter(_q(ns_t, "t")))
        if t.strip():
            lineas.append(t)
    return lineas


# ---------------------------------------------------------------- PowerPoint

def _diapositivas(z):
    """Partes de las diapositivas en el orden de la presentación."""
    pres = _xml(z, "ppt/presentation.xml")
    rels = _relaciones(z, "ppt/presentation.xml")
    lista = pres.find(_q(P, "sldIdLst"))
    res = []
    for s in (lista if lista is not None else []):
        rid = s.get(_q(R, "id"))
        if rid in rels:
            res.append((s, rels[rid][1]))
    return res


def _texto_pptx(z, parte):
    lineas = [t for t in _texto(_xml(z, parte), A, A)]
    for tipo, destino, ext in _relaciones(z, parte).values():
        if not ext and tipo.endswith("/notesSlide") and destino in z.namelist():
            lineas += _texto(_xml(z, destino), A, A)
    return "\n".join(lineas)


# ---------------------------------------------------------------- Excel

def _hojas(z):
    wb = _xml(z, "xl/workbook.xml")
    rels = _relaciones(z, "xl/workbook.xml")
    hojas = wb.find(_q(S, "sheets"))
    return [(h, rels[h.get(_q(R, "id"))][1]) for h in (hojas if hojas is not None else [])
            if h.get(_q(R, "id")) in rels]


def _compartidos(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return None, []
    sst = _xml(z, "xl/sharedStrings.xml")
    return sst, list(sst.iter(_q(S, "si")))


def _indices_usados(root):
    usados = set()
    for c in root.iter(_q(S, "c")):
        if c.get("t") == "s":
            v = c.find(_q(S, "v"))
            if v is not None and (v.text or "").strip().isdigit():
                usados.add(int(v.text))
    return usados


def _texto_si(si):
    return "".join(t.text or "" for t in si.iter(_q(S, "t")) if t.getparent().tag != _q(S, "rPh"))


def _texto_hoja(z, parte, sis):
    root = _xml(z, parte)
    lineas = [_texto_si(sis[i]) for i in sorted(_indices_usados(root)) if i < len(sis)]
    for is_ in root.iter(_q(S, "is")):
        lineas.append("".join(t.text or "" for t in is_.iter(_q(S, "t"))))
    for c in root.iter(_q(S, "c")):
        v = c.find(_q(S, "v"))
        if v is not None and v.text and (c.get("t") == "str" or re.fullmatch(r"\d{9,12}", v.text.strip())):
            lineas.append(v.text)
    for tipo, destino, ext in _relaciones(z, parte).values():
        if not ext and (tipo.endswith("/comments") or tipo.endswith("/threadedComment")) and destino in z.namelist():
            for el in _xml(z, destino).iter():
                if isinstance(el.tag, str) and etree.QName(el).localname in ("t", "text") and el.text:
                    lineas.append(el.text)
    return "\n".join(x for x in lineas if x and x.strip())


# ---------------------------------------------------------------- Word

LRPB, BR, PBB, SECT = _q(W, "lastRenderedPageBreak"), _q(W, "br"), _q(W, "pageBreakBefore"), _q(W, "sectPr")


def _paginas_word(body):
    """Página (desde 1) en la que empieza cada elemento del cuerpo, y si el documento guarda
    las páginas tal como las mostró Word."""
    hijos = [h for h in body if h.tag != SECT]
    renderizado = any(True for _ in body.iter(LRPB))
    pagina, res = 1, []
    for h in hijos:
        inicio, texto_visto = pagina, False
        for el in h.iter():
            if el.tag == _q(W, "t") and (el.text or "").strip():
                texto_visto = True
            if renderizado:
                # Word apunta aquí que empezaba una página: lo que sigue ya está en la nueva
                if el.tag == LRPB:
                    pagina += 1
                    if not texto_visto:
                        inicio = pagina
            elif el.tag == BR and el.get(_q(W, "type")) == "page":
                pagina += 1                       # salto de página: lo que sigue va a la siguiente
            elif el.tag == PBB and el.get(_q(W, "val"), "1") not in ("0", "false") and not texto_visto:
                pagina += 1                       # «salto de página anterior» del párrafo
                inicio = pagina
        res.append((h, inicio))
        if not renderizado:
            ppr = h.find(_q(W, "pPr"))
            sp = ppr.find(SECT) if ppr is not None else None
            if sp is not None:
                tipo = sp.find(_q(W, "type"))
                if tipo is None or tipo.get(_q(W, "val")) in ("nextPage", "evenPage", "oddPage"):
                    pagina += 1
    return res, renderizado


def _referencias(elementos):
    notas, finales, comentarios = set(), set(), set()
    for h in elementos:
        for el in h.iter(_q(W, "footnoteReference")):
            notas.add(el.get(_q(W, "id")))
        for el in h.iter(_q(W, "endnoteReference")):
            finales.add(el.get(_q(W, "id")))
        for tag in ("commentReference", "commentRangeStart"):
            for el in h.iter(_q(W, tag)):
                comentarios.add(el.get(_q(W, "id")))
    return notas, finales, comentarios


def _textos_por_id(z, parte, tag):
    if parte not in z.namelist():
        return {}
    return {el.get(_q(W, "id")): "\n".join(_texto(el, W, W)) for el in _xml(z, parte).iter(_q(W, tag))}


def _texto_cuerpo(elementos):
    lineas = []
    for h in elementos:
        lineas += _texto(h, W, W) if h.tag != _q(W, "p") else ["".join(t.text or "" for t in h.iter(_q(W, "t")))]
    return [x for x in lineas if x.strip()]


# ---------------------------------------------------------------- lectura

def partes(ruta, ext):
    """Texto de cada página / diapositiva / hoja. Lo que vale para todas (encabezados y pies de
    Word, textos sueltos) va al final de la primera, para que el conjunto sea el documento entero."""
    familia = FAMILIAS.get(ext)
    with zipfile.ZipFile(ruta) as z:
        if familia == "pptx":
            return [_texto_pptx(z, parte) for _, parte in _diapositivas(z)] or [""]
        if familia == "xlsx":
            _, sis = _compartidos(z)
            hojas = _hojas(z)
            res = [_texto_hoja(z, parte, sis) for _, parte in hojas] or [""]
            usados = set()
            for _, parte in hojas:
                usados |= _indices_usados(_xml(z, parte))
            sueltos = [_texto_si(si) for i, si in enumerate(sis) if i not in usados and _texto_si(si).strip()]
            if sueltos:
                res[0] = "\n".join([res[0]] + sueltos)
            return res
        doc = _xml(z, "word/document.xml")
        body = doc.find(_q(W, "body"))
        asignados, _ = _paginas_word(body)
        n = max([p for _, p in asignados] or [1])
        notas = _textos_por_id(z, "word/footnotes.xml", "footnote")
        finales = _textos_por_id(z, "word/endnotes.xml", "endnote")
        comentarios = _textos_por_id(z, "word/comments.xml", "comment")
        res, usadas = [], (set(), set(), set())
        for k in range(1, n + 1):
            els = [h for h, p in asignados if p == k]
            fn, en, cm = _referencias(els)
            lineas = _texto_cuerpo(els) + [notas[i] for i in fn if i in notas] + [finales[i] for i in en if i in finales] + \
                [comentarios[i] for i in cm if i in comentarios]
            for a, b in zip(usadas, (fn, en, cm)):
                a |= b
            res.append("\n".join(x for x in lineas if x.strip()))
        comun = []
        for nombre in sorted(z.namelist()):
            if re.match(r"^word/(header|footer)\d*\.xml$", nombre):
                comun += _texto(_xml(z, nombre), W, W)
        for tabla, vistas in ((notas, usadas[0]), (finales, usadas[1]), (comentarios, usadas[2])):
            comun += [t for i, t in tabla.items() if i not in vistas and t.strip()]
        if comun:
            res[0] = "\n".join([res[0]] + comun)
        return res


def numero(ruta, ext):
    try:
        return len(partes(ruta, ext))
    except Exception:  # noqa
        return None


def word_sin_paginas(ruta):
    """True si el Word no guarda dónde empezaba cada página (no se guardó con Word)."""
    with zipfile.ZipFile(ruta) as z:
        body = _xml(z, "word/document.xml").find(_q(W, "body"))
        return not any(True for _ in body.iter(LRPB))


# ---------------------------------------------------------------- recorte

def recortar(ruta, ext, elegidas, salida):
    """Escribe en «salida» una copia con solo esas páginas / diapositivas / hojas (desde 1)."""
    familia = FAMILIAS.get(ext)
    with zipfile.ZipFile(ruta) as z:
        n = len(partes(ruta, ext))
        malas = [p for p in elegidas if not 1 <= p <= n]
        if malas:
            u = UNIDAD[familia]
            if familia == "docx" and n == 1 and word_sin_paginas(ruta):
                raise ErrorPaginas("Este Word no guarda dónde empieza cada página (se hizo con otro programa o no se "
                                   "ha guardado con Word). Ábrelo y guárdalo con Word, o guárdalo como PDF, y vuelve a pedirlo.")
            raise ErrorPaginas("El documento tiene %d %s: no existe la %s %s." % (
                n, u[1] if n != 1 else u[0], u[0], ", ".join(map(str, malas))))
        partes_xml = {nombre: z.read(nombre) for nombre in z.namelist()}
        cambios = {"pptx": _recortar_pptx, "xlsx": _recortar_xlsx, "docx": _recortar_docx}[familia](z, set(elegidas))
    partes_xml.update(cambios)
    for k in [k for k, v in partes_xml.items() if v is None]:
        del partes_xml[k]
    _recoger(partes_xml)
    _sin_titulos(partes_xml)
    with zipfile.ZipFile(ruta) as zin, zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zout:
        orden = [i.filename for i in zin.infolist()]
        for nombre in orden + sorted(set(partes_xml) - set(orden)):
            if nombre in partes_xml:
                zout.writestr(nombre, partes_xml[nombre])
    return salida


def _ser(root):
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _quitar_rel(z, parte, rids, cambios):
    nombre = _rels_de(parte)
    if nombre not in z.namelist() or not rids:
        return
    root = etree.fromstring(cambios.get(nombre) or z.read(nombre), PARSER)
    for r in list(root):
        if r.get("Id") in rids:
            root.remove(r)
    cambios[nombre] = _ser(root)


def _recortar_pptx(z, elegidas):
    cambios = {}
    pres = _xml(z, "ppt/presentation.xml")
    rels = _relaciones(z, "ppt/presentation.xml")
    lista = pres.find(_q(P, "sldIdLst"))
    quitadas, ids_quitados, partes_quitadas = set(), set(), set()
    for k, s in enumerate(list(lista), 1):
        if k not in elegidas:
            rid = s.get(_q(R, "id"))
            quitadas.add(rid)
            ids_quitados.add(s.get("id"))
            if rid in rels:
                partes_quitadas.add(rels[rid][1])
            lista.remove(s)
    cust = pres.find(_q(P, "custShowLst"))
    if cust is not None:
        pres.remove(cust)
    for s in list(pres.iter(_q(P14, "sldId"))):       # secciones de PowerPoint 2010+
        if s.get("id") in ids_quitados:
            s.getparent().remove(s)
    cambios["ppt/presentation.xml"] = _ser(pres)
    _quitar_rel(z, "ppt/presentation.xml", quitadas, cambios)
    # enlaces de una diapositiva que queda a otra que se quita: apuntan a la propia diapositiva
    for _, parte in _diapositivas(z):
        if parte in partes_quitadas:
            continue
        nombre = _rels_de(parte)
        if nombre in z.namelist():
            root = _xml(z, nombre)
            tocado = False
            for r in root:
                destino = posixpath.normpath(posixpath.join(posixpath.dirname(parte), r.get("Target") or ""))
                if (r.get("Type") or "").endswith("/slide") and destino in partes_quitadas:
                    r.set("Target", posixpath.basename(parte))
                    tocado = True
            if tocado:
                cambios[nombre] = _ser(root)
    return cambios


def _recortar_xlsx(z, elegidas):
    cambios = {}
    wb = _xml(z, "xl/workbook.xml")
    rels = _relaciones(z, "xl/workbook.xml")
    hojas = wb.find(_q(S, "sheets"))
    viejos = list(hojas)
    nuevo_indice, quitadas, nombres_quitados, quedan = {}, set(), set(), []
    for k, h in enumerate(viejos, 1):
        if k in elegidas:
            nuevo_indice[k - 1] = len(nuevo_indice)
            quedan.append(rels.get(h.get(_q(R, "id")), ("", "", True))[1])
        else:
            quitadas.add(h.get(_q(R, "id")))
            nombres_quitados.add(h.get("name") or "")
            hojas.remove(h)
    if not quedan:
        raise ErrorPaginas("Hay que dejar al menos una hoja.")
    nombres = wb.find(_q(S, "definedNames"))
    if nombres is not None:
        for d in list(nombres):
            local = d.get("localSheetId")
            texto = d.text or ""
            if local is not None and local.isdigit():
                if int(local) in nuevo_indice:
                    d.set("localSheetId", str(nuevo_indice[int(local)]))
                else:
                    nombres.remove(d)
                    continue
            if any(n and (n + "!" in texto or "'%s'!" % n.replace("'", "''") in texto) for n in nombres_quitados):
                nombres.remove(d)
        if not len(nombres):
            wb.remove(nombres)
    for vista in wb.iter(_q(S, "workbookView")):
        vista.set("activeTab", "0")
        vista.set("firstSheet", "0")
    # tablas dinámicas: solo se conservan las cachés que usan las hojas que quedan
    cachés_usadas = set()
    for parte in quedan:
        for tipo, destino, ext in _relaciones(z, parte).values():
            if tipo.endswith("/pivotTable") and not ext:
                for t2, d2, e2 in _relaciones(z, destino).values():
                    if t2.endswith("/pivotCacheDefinition"):
                        cachés_usadas.add(d2)
    pcs = wb.find(_q(S, "pivotCaches"))
    if pcs is not None:
        for pc in list(pcs):
            rid = pc.get(_q(R, "id"))
            if rid in rels and rels[rid][1] not in cachés_usadas:
                quitadas.add(rid)
                pcs.remove(pc)
        if not len(pcs):
            wb.remove(pcs)
    for rid, (tipo, destino, ext) in rels.items():
        if tipo.endswith("/calcChain"):            # Excel la rehace al abrir
            quitadas.add(rid)
    cambios["xl/workbook.xml"] = _ser(wb)
    _quitar_rel(z, "xl/workbook.xml", quitadas, cambios)
    # textos compartidos: se vacían los que solo usaban las hojas quitadas
    sst, sis = _compartidos(z)
    if sst is not None:
        usados = set()
        for parte in quedan:
            usados |= _indices_usados(_xml(z, parte))
        for i, si in enumerate(sis):
            if i not in usados:
                for hijo in list(si):
                    si.remove(hijo)
                etree.SubElement(si, _q(S, "t")).text = ""
        cambios["xl/sharedStrings.xml"] = _ser(sst)
    return cambios


def _recortar_docx(z, elegidas):
    cambios = {}
    doc = _xml(z, "word/document.xml")
    body = doc.find(_q(W, "body"))
    asignados, _ = _paginas_word(body)
    quedan = []
    for h, p in asignados:
        if p in elegidas:
            quedan.append(h)
        else:
            body.remove(h)
    if not quedan:
        raise ErrorPaginas("Esas páginas no tienen contenido.")
    _sin_saltos_en_bordes(quedan[0], quedan[-1])
    cambios["word/document.xml"] = _ser(doc)
    fn, en, cm = _referencias([body])
    for parte, tag, vivos in (("word/footnotes.xml", "footnote", fn), ("word/endnotes.xml", "endnote", en),
                              ("word/comments.xml", "comment", cm)):
        if parte not in z.namelist():
            continue
        root = _xml(z, parte)
        for el in list(root.iter(_q(W, tag))):
            separador = el.get(_q(W, "type")) in ("separator", "continuationSeparator", "continuationNotice")
            if not separador and el.get(_q(W, "id")) not in vivos:
                el.getparent().remove(el)
        cambios[parte] = _ser(root)
    return cambios


def _sin_saltos_en_bordes(primero, ultimo):
    """La copia no empieza ni acaba con una página en blanco: fuera los saltos de página que
    hay antes del primer texto del primer elemento y después del último texto del último."""
    def es_salto(el):
        return el.tag == LRPB or (el.tag == BR and el.get(_q(W, "type")) == "page") or \
            (el.tag == PBB and el.get(_q(W, "val"), "1") not in ("0", "false"))
    for el in list(primero.iter()):
        if el.tag == _q(W, "t") and (el.text or "").strip():
            break
        if es_salto(el):
            el.getparent().remove(el)
    for el in reversed(list(ultimo.iter())):
        if el.tag == _q(W, "t") and (el.text or "").strip():
            break
        if el.tag == BR and el.get(_q(W, "type")) == "page":
            el.getparent().remove(el)


def _recoger(paquete):
    """Quita del paquete las partes a las que ya no llega ninguna relación (diapositivas, hojas,
    imágenes y notas de lo que se ha quitado), con sus relaciones y su tipo de contenido."""
    alcanzadas, pendientes = set(), ["_rels/.rels"]
    vistos = set()
    while pendientes:
        rels = pendientes.pop()
        if rels in vistos or rels not in paquete:
            continue
        vistos.add(rels)
        origen = rels.replace("_rels/", "")[:-len(".rels")]
        base = posixpath.dirname(origen) if rels != "_rels/.rels" else ""
        for r in etree.fromstring(paquete[rels], PARSER).iter(_q(PR, "Relationship")):
            if r.get("TargetMode") == "External":
                continue
            t = r.get("Target") or ""
            destino = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join(base, t))
            if destino not in alcanzadas:
                alcanzadas.add(destino)
                pendientes.append(_rels_de(destino))
    sobran = [n for n in paquete if n != "[Content_Types].xml" and not n.endswith(".rels") and not n.endswith("/")
              and n not in alcanzadas]
    for n in sobran:
        del paquete[n]
        paquete.pop(_rels_de(n), None)
    if "[Content_Types].xml" in paquete and sobran:
        ct = etree.fromstring(paquete["[Content_Types].xml"], PARSER)
        for o in list(ct.iter(_q(CT, "Override"))):
            if (o.get("PartName") or "").lstrip("/") in sobran:
                ct.remove(o)
        paquete["[Content_Types].xml"] = _ser(ct)


def _sin_titulos(paquete):
    """docProps/app.xml lista los títulos de las diapositivas y los nombres de las hojas,
    también de las quitadas: se quita esa lista (Office la rehace al guardar)."""
    if "docProps/app.xml" not in paquete:
        return
    root = etree.fromstring(paquete["docProps/app.xml"], PARSER)
    for tag in ("TitlesOfParts", "HeadingPairs", "Slides", "Notes", "Pages", "Words", "Characters", "Paragraphs", "Lines"):
        for el in list(root.iter(_q(EP, tag))):
            el.getparent().remove(el)
    paquete["docProps/app.xml"] = _ser(root)
