# -*- coding: utf-8 -*-
"""Pruebas unitarias del núcleo (sin modelo): python -m pytest pruebas"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nucleo"))
os.environ.setdefault("SEUDONIMO_DATOS", tempfile.mkdtemp())

import motor  # noqa: E402
import registro  # noqa: E402


def test_etiquetas_estables_y_variantes():
    r = registro.Registro(1)
    r.incorporar([{"texto": "Lucía Ferrer Gil", "tipo": "PERSONA"}, {"texto": "FERRER GIL, LUCÍA", "tipo": "PERSONA"},
                  {"texto": "12345678Z", "tipo": "DNI"}])
    r.incorporar([{"texto": "12.345.678-Z", "tipo": "DNI"}])
    marcadores = {e["marcador"] for e in r.entidades}
    assert marcadores == {"[PERSONA_001]", "[DNI_001]"}
    t = motor.reemplazar_texto("Doña Lucía Ferrer Gil (DNI 12 345 678 Z). Ferrer Gil, Lucía.", r.mapa())
    assert "Ferrer" not in t and "12" not in t


def test_no_fusiona_homonimos_ni_nombres_de_pila():
    r = registro.Registro(1)
    r.incorporar([{"texto": "Lucía Ferrer Gil", "tipo": "PERSONA"}, {"texto": "Marcos Ferrer Cabrera", "tipo": "PERSONA"}])
    n = r.incorporar([{"texto": "Ferrer", "tipo": "PERSONA"}, {"texto": "Lucía", "tipo": "PERSONA"}])
    assert all(x["marcador"] not in ("[PERSONA_001]", "[PERSONA_002]") for x in n)
    assert r.entidades[-2].get("ambigua")


def test_descartados_no_vuelven():
    r = registro.Registro(1)
    r.incorporar([{"texto": "Oficina Técnica", "tipo": "DEPARTAMENTO"}])
    r.descartar(0)
    assert r.incorporar([{"texto": "Oficina Técnica", "tipo": "DEPARTAMENTO"}]) == []
    assert r.mapa() == []


def test_marcadores_no_son_datos():
    assert motor.detectar_regex("Código [CSV_001] y [PERSONA_002]") == []
    assert motor.MARCADOR_OCR.sub("#", "CSV: tcsv_001") == "CSV: #"
    assert motor.MARCADOR_OCR.sub("#", "persona 12 años") == "persona 12 años"
    # lecturas reales del OCR de Vision sobre marcadores tachados (regresión del 26/11/2026)
    for leido in ("ICCC.0011", "C.C.C.: ICCC.0011", "(PERSONA_002)", "[DNI.003]", "lIBAN_0011", "[CSV_001]"):
        assert "CCC" not in motor.MARCADOR_OCR.sub("#", leido).replace("C.C.C.", "")
        assert not motor.detectar_regex(motor.MARCADOR_OCR.sub(lambda m: " " * len(m.group(0)), leido))


def test_fragmentar_con_desfase_cambia_los_cortes():
    texto = "\n".join("línea %d con algo de texto" % i for i in range(400))
    a = motor.fragmentar(texto)
    b = motor.fragmentar(texto, desfase=1250)
    assert "".join(a) == "".join(b) == texto + "\n"
    assert len(a[0]) != len(b[0])


def test_cifrado_ida_y_vuelta():
    import cifrado
    datos = registro.Registro(7)
    datos.incorporar([{"texto": "Lucía Ferrer Gil", "tipo": "PERSONA"}])
    sellado = cifrado.cifrar(7, datos.a_bytes())
    assert b"Ferrer" not in sellado
    otra = registro.Registro.de_bytes(cifrado.descifrar(7, sellado), 7)
    assert otra.buscar("Lucía Ferrer Gil")["marcador"] == "[PERSONA_001]"
    cifrado.borrar_clave(7)


def test_validacion_estructural_y_variantes_ocr():
    assert not motor.valido("008", "TELEFONO") and motor.valido("628 111 222", "TELEFONO")
    assert not motor.valido("TELEO0 008", "TELEFONO")
    assert motor.valido("12.345.678-Z", "DNI") and motor.valido("X1234567L", "DNI") and not motor.valido("1234", "DNI")
    assert not motor.valido("Dña.", "PERSONA") and motor.valido("Lucía Ferrer", "PERSONA")
    for ruido in ("Diña", "Dna", "Dofia", "D./Diña", "D1ña", "Doña"):
        assert not motor.valido(ruido, "PERSONA"), ruido
    for nombre in ("Ana", "Eva", "Dina Ruiz", "Doménico"):
        assert motor.valido(nombre, "PERSONA"), nombre
    original = "Datos: DNI 5886S754Z y vive en Arrecife. D./Dña. Lucía Ferrer Gil"
    assert motor.variante_en("58865754Z", original) == "5886S754Z"     # el OCR del original leyó una S
    assert motor.variante_en("Diña", original) is None                  # ruido: no se parece a nada


def test_registro_rechaza_formas_imposibles():
    r = registro.Registro(2)
    assert r.incorporar([{"texto": "008", "tipo": "TELEFONO"}, {"texto": "Dña.", "tipo": "PERSONA"}]) == []


def test_listas_del_despacho_y_tipos_conservados():
    registro.fijar_listas([{"texto": "Tribunal Superior de Justicia de Canarias"}],
                          [{"texto": "Hoteles Volcán Azul S.L.", "tipo": "EMPRESA"}])
    try:
        texto = "Hoteles Volcán Azul S.L. recurre ante el Tribunal Superior de Justicia de Canarias."
        r = registro.Registro(1)
        r.incorporar(registro.de_la_lista(texto) + [{"texto": "Tribunal Superior de Justicia de Canarias", "tipo": "EMPRESA"},
                                                     {"texto": "Oficina Técnica", "tipo": "DEPARTAMENTO"}])
        assert [e["texto"] for e in r.mapa()] == ["Hoteles Volcán Azul S.L.", "Oficina Técnica"]
        r.conservar = {"DEPARTAMENTO"}
        assert [e["texto"] for e in r.mapa()] == ["Hoteles Volcán Azul S.L."]
    finally:
        registro.fijar_listas([], [])


def test_correo_eml_a_texto():
    import correo
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "c.eml")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("From: Ana Pérez <ana@ejemplo.es>\nSubject: Despido\nContent-Type: text/html; charset=utf-8\n\n"
                "<p>Me han despedido.<br>DNI 12345678Z</p>")
    salida, aviso = correo.a_texto(ruta, d)
    texto = open(salida, encoding="utf-8").read()
    assert salida.endswith(".txt") and "Ana Pérez" in texto and "12345678Z" in texto and "<p>" not in texto


def test_reidentificar_marcadores():
    import re
    r = registro.Registro(1)
    r.incorporar([{"texto": "Lucía Ferrer Gil", "tipo": "PERSONA"}, {"texto": "Ferrer Gil", "tipo": "PERSONA"}])
    marca = re.compile(r"\[\s*([A-Z][A-Z_]*_\d{1,4})\s*\]|(?<![\w\[])([A-Z][A-Z]+(?:_[A-Z]+)*_\d{3})(?![\w\]])")
    sal = marca.sub(lambda m: max(r.por_marcador("[%s]" % (m.group(1) or m.group(2)))["formas"], key=len),
                    "Según [PERSONA_001] y PERSONA_001.")
    assert sal == "Según Lucía Ferrer Gil y Lucía Ferrer Gil."


def test_sin_pensamiento_del_modelo():
    from proveedores.ollama import _sin_pensamiento, limpiar_pensamiento

    def flujo(trozos):
        for x in trozos:
            yield {"contenido": x}
        yield {"fin": True, "llamadas": []}
    salida = "".join(t.get("contenido", "") for t in _sin_pensamiento(flujo(["thou", "ght\nRazono…<chan", "nel|>El plan ", "está listo."])))
    assert salida == "El plan está listo."
    assert "".join(t.get("contenido", "") for t in _sin_pensamiento(flujo(["Hola, ", "qué tal"]))) == "Hola, qué tal"
    assert limpiar_pensamiento("thought\n<channel|>Texto") == "Texto"


def test_recortar_pdf_solo_unas_paginas():
    import formatos
    from reportlab.pdfgen import canvas
    d = tempfile.mkdtemp()
    ruta = os.path.join(d, "doc.pdf")
    c = canvas.Canvas(ruta)
    for i in range(1, 8):
        c.drawString(60, 780, "Contenido de la pagina %d" % i)
        c.showPage()
    c.save()
    salida = formatos.recortar_pdf(ruta, [6], d)
    paginas = formatos.extraer_paginas(salida, ".pdf")
    assert len(paginas) == 1 and "pagina 6" in paginas[0]
    assert formatos.texto_paginas([6, 7]) == "las páginas 6 y 7"
    try:
        formatos.recortar_pdf(ruta, [9], d)
        assert False, "debería fallar"
    except formatos.ErrorFormato as e:
        assert "7 páginas" in str(e)


def test_escritura_fallida_no_bloquea_la_base():
    import sqlite3
    import threading
    import almacen
    ruta = os.path.join(tempfile.mkdtemp(), "b.sqlite3")
    alm = almacen.Almacen(ruta)
    error = []

    def hilo():   # como un trabajo que escribe en un proyecto que ya no existe
        try:
            alm._x("INSERT INTO archivos(proyecto, carpeta, ruta, nombre) VALUES (?,?,?,?)", (999, 999, "x", "x"))
        except sqlite3.Error as e:
            error.append(e)
        alm._q("SELECT 1")          # el hilo sigue vivo con su conexión, como el gestor de trabajos
        evento.wait(5)

    evento = threading.Event()
    t = threading.Thread(target=hilo)
    t.start()
    time.sleep(0.3)
    otra = sqlite3.connect(ruta, timeout=1)
    otra.execute("CREATE TABLE IF NOT EXISTS prueba(x)")    # fallaría con «database is locked»
    otra.commit()
    evento.set()
    t.join()
    assert error


def test_colegiado_y_webs():
    hallados = {(e["tipo"], e["texto"]) for e in motor.detectar_regex(
        "Graduado Social nº 88. Colegiada nº 1234. Visita josemaria.ai o www.despacho-ejemplo.es/contacto. "
        "Importe 88,50 €. Sede en sede.seg-social.gob.es y www.boe.es. Escribe a ana@josemaria.ai")}
    assert ("COLEGIADO", "nº 88") in hallados and ("COLEGIADO", "Colegiada nº 1234") in hallados
    assert ("WEB", "josemaria.ai") in hallados and ("WEB", "www.despacho-ejemplo.es/contacto") in hallados
    assert not any("seg-social" in t or "boe.es" in t for _, t in hallados)
    assert ("EMAIL", "ana@josemaria.ai") in hallados
    mapa = [{"texto": "nº 88", "tipo": "COLEGIADO", "marcador": "[COLEGIADO_001]"}]
    assert motor.reemplazar_texto("nº 88 y 88,50 €", mapa) == "[COLEGIADO_001] y 88,50 €"


def test_partes_de_office_y_recorte_sin_restos():
    import zipfile
    import pytest
    docx = pytest.importorskip("docx")
    openpyxl = pytest.importorskip("openpyxl")
    pptx = pytest.importorskip("pptx")
    import formatos
    d = tempfile.mkdtemp()
    w = docx.Document()
    for i, t in enumerate(["Uno Ana Ruiz Gil", "Dos Pedro Sanz López", "Tres Lucía Ferrer Gil"]):
        if i:
            w.add_page_break()
        w.add_paragraph(t)
    w.save(os.path.join(d, "w.docx"))
    p = pptx.Presentation()
    for t in ["Uno Ana", "Dos Pedro Sanz", "Tres Lucía"]:
        p.slides.add_slide(p.slide_layouts[1]).shapes.title.text = t
    p.save(os.path.join(d, "p.pptx"))
    wb = openpyxl.Workbook()
    wb.active["A1"] = "Uno"
    wb.create_sheet("B")["A1"] = "Pedro Sanz López"
    wb.create_sheet("C")["A1"] = "Uno"
    wb.save(os.path.join(d, "x.xlsx"))
    for nombre in ("w.docx", "p.pptx", "x.xlsx"):
        ruta, ext = os.path.join(d, nombre), os.path.splitext(nombre)[1]
        assert len(formatos.extraer_paginas(ruta, ext)) == 3
        corte = formatos.recortar(ruta, ext, [1, 3], d)
        assert len(formatos.extraer_paginas(corte, ext)) == 2
        with zipfile.ZipFile(corte) as z:
            assert not any(b"Pedro" in z.read(n) for n in z.namelist())


def test_hojas_de_excel_renombradas_con_sus_formulas():
    import re
    import zipfile
    import pytest
    openpyxl = pytest.importorskip("openpyxl")
    import formatos
    d = tempfile.mkdtemp()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nóminas Ana Ruiz"
    ws["B1"] = 1500
    wb.create_sheet("Resumen")["B1"] = "='Nóminas Ana Ruiz'!B1"
    ruta, salida = os.path.join(d, "l.xlsx"), os.path.join(d, "s.xlsx")
    wb.save(ruta)
    assert "Nóminas Ana Ruiz" in formatos.extraer_texto(ruta, ".xlsx")
    formatos.aplicar(ruta, salida, ".xlsx", [{"texto": "Ana Ruiz", "tipo": "PERSONA", "marcador": "[PERSONA_001]"}])
    with zipfile.ZipFile(salida) as z:
        todo = b"".join(z.read(n) for n in z.namelist()).decode("utf-8", "ignore")
    assert "Ana Ruiz" not in todo and "N&#243;minas Ana" not in todo
    assert openpyxl.load_workbook(salida).sheetnames == ["Nóminas PERSONA_001", "Resumen"]
    assert re.search(r"<f>'N(ó|&#243;)minas PERSONA_001'!B1</f>", todo)


def test_texto_en_imagenes_de_office():
    import io
    import zipfile
    import pytest
    import ocr
    if not ocr.DISPONIBLE:
        pytest.skip("sin OCR")
    docx = pytest.importorskip("docx")
    from PIL import Image, ImageDraw, ImageFont
    import formatos
    try:
        fuente = ImageFont.truetype("DejaVuSans.ttf", 36)
    except OSError:
        try:
            fuente = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 36)
        except OSError:
            pytest.skip("sin fuente para dibujar")
    im = Image.new("RGB", (900, 180), "white")
    ImageDraw.Draw(im).text((20, 60), "Firmado: Lucía Ferrer Gil", fill="black", font=fuente)
    b = io.BytesIO()
    im.save(b, "PNG")
    b.seek(0)
    d = tempfile.mkdtemp()
    w = docx.Document()
    w.add_paragraph("Carta.")
    w.add_picture(b)
    ruta, salida = os.path.join(d, "f.docx"), os.path.join(d, "s.docx")
    w.save(ruta)
    assert "Ferrer" in formatos.extraer_texto(ruta, ".docx")
    info = formatos.aplicar(ruta, salida, ".docx", [{"texto": "Lucía Ferrer Gil", "tipo": "PERSONA", "marcador": "[PERSONA_001]"}])
    assert info["imagenes_tapadas"] == 1
    assert "Ferrer" not in formatos.extraer_texto(salida, ".docx", verificar=True)


def test_copias_junto_a_los_originales_y_anteriores():
    import multipasada
    import registro as registro_mod
    import trabajos
    d = tempfile.mkdtemp()
    carpeta = os.path.join(d, "Clientes", "Ana Ruiz")
    os.makedirs(carpeta)
    orig = os.path.join(carpeta, "Carta Ana Ruiz.txt")
    open(orig, "w").write("Ana Ruiz")
    reg = registro_mod.Registro()
    reg.incorporar([{"texto": "Ana Ruiz", "tipo": "PERSONA", "origen": "regla"}], 1)
    docs = [{"id": 1, "ruta": orig, "rel": "Ana Ruiz/Carta Ana Ruiz.txt", "nombre": "Carta Ana Ruiz.txt"}]
    finales = []
    for i, estado in enumerate(("sin_hallazgos", "revision")):
        lote = multipasada.TrabajoLote("t%d" % i, docs, reg, destino=os.path.join(d, "informes", str(i)),
                                       guardar=trabajos.modo_guardar({"nombre": "P"}))
        lote.inicio = 0
        doc = lote.docs[0]
        doc.estado, doc.ext, doc.ext_original = estado, ".txt", ".txt"
        doc.salida = os.path.join(d, "copia%d.txt" % i)
        open(doc.salida, "w").write("[PERSONA_001]")
        lote.exportar()
        finales.append(doc.final)
    sal = os.path.join(carpeta, "Seudonimizados")
    assert os.path.dirname(finales[0]) == sal and "Ana Ruiz" not in os.path.basename(finales[0])
    assert finales[1].endswith("(seudonimizado - revisar).txt")
    assert sorted(os.listdir(sal)) == ["Anteriores", "Carta [PERSONA_001] (seudonimizado - revisar).txt", "Certificados"]
    assert len(os.listdir(os.path.join(sal, "Anteriores"))) == 1


def test_caras_y_logotipos_en_office():
    import io
    import zipfile
    import pytest
    import rostros
    if not rostros.DISPONIBLE:
        pytest.skip("sin detector de caras")
    docx = pytest.importorskip("docx")
    from docx.shared import Cm
    from PIL import Image
    import formatos
    foto = os.path.join(os.path.dirname(__file__), "datos", "astronauta.jpg")
    assert rostros.caras(Image.open(foto)), "no ha visto la cara"
    logo = io.BytesIO()
    Image.new("RGB", (300, 120), (20, 60, 140)).save(logo, "PNG")
    logo.seek(0)
    d = tempfile.mkdtemp()
    w = docx.Document()
    w.add_picture(logo, width=Cm(3))
    w.add_picture(foto, width=Cm(12))
    ruta, salida = os.path.join(d, "f.docx"), os.path.join(d, "s.docx")
    w.save(ruta)
    info = formatos.aplicar(ruta, salida, ".docx", [], {"logos": True})
    assert info["logos"] == 1 and info["caras"] == 1
    with zipfile.ZipFile(salida) as z:
        fotos = [Image.open(io.BytesIO(z.read(n))) for n in z.namelist() if n.startswith("word/media/")]
    grande = max(fotos, key=lambda i: i.width)
    assert not rostros.caras(grande.convert("RGB")), "la cara sigue a la vista"


def test_verificacion_de_caras_y_segundo_ciclo():
    """Una cara que la edición no tapó (aquí, con la opción desactivada) la ve la verificación,
    y con esas zonas el ciclo siguiente la tapa: en PDF y en Word."""
    import pytest
    import rostros
    if not rostros.DISPONIBLE:
        pytest.skip("sin detector de caras")
    from reportlab.pdfgen import canvas
    import formatos
    foto = os.path.join(os.path.dirname(__file__), "datos", "astronauta.jpg")
    d = tempfile.mkdtemp()
    pdf = os.path.join(d, "dni.pdf")
    c = canvas.Canvas(pdf)
    c.drawString(72, 780, "Copia del documento de identidad")
    c.drawImage(foto, 72, 400, 250, 250)
    c.save()
    copia = os.path.join(d, "c1.pdf")
    formatos.aplicar(pdf, copia, ".pdf", [], {"logos": False})
    caras = formatos.caras_en(copia, ".pdf")
    assert caras, "la verificación no ve la cara"
    extra = {p: [(r, "[CARA]") for r in rs] for p, rs in caras.items()}
    copia2 = os.path.join(d, "c2.pdf")
    formatos.aplicar(pdf, copia2, ".pdf", [], {"logos": False, "extra": extra})
    assert not formatos.caras_en(copia2, ".pdf")
    docx = pytest.importorskip("docx")
    from docx.shared import Cm
    w = docx.Document()
    w.add_picture(foto, width=Cm(12))
    ruta = os.path.join(d, "f.docx")
    w.save(ruta)
    s1 = os.path.join(d, "s1.docx")
    formatos.aplicar(ruta, s1, ".docx", [], {"logos": False})
    medios = formatos.caras_en(s1, ".docx")
    assert medios
    s2 = os.path.join(d, "s2.docx")
    formatos.aplicar(ruta, s2, ".docx", [], {"logos": False, "extra_medios": medios})
    assert not formatos.caras_en(s2, ".docx")


def test_riesgo_por_contexto_reglas_modelo_y_generalizacion():
    import contexto
    import proveedores
    texto = ("[PERSONA_001], de 54 años, trabaja como jefa de almacén en el centro de Arrecife desde el "
             "3 de marzo de 2015 con un salario de 1.832,45 €. Tiene una antigüedad de 11 años. "
             "Está de baja desde el 12/02/2026 por un trastorno adaptativo.")
    r = {(h["categoria"], h["texto"]) for h in contexto.por_reglas(texto)}
    assert ("edad", "54 años") in r and ("fecha", "3 de marzo de 2015") in r and ("fecha", "12/02/2026") in r
    assert ("importe", "1.832,45 €") in r and not any(t == "11 años" for _, t in r)

    class Falso:
        def estructurado(self, modelo, mensajes, esquema):
            return {"datos": [{"texto": "jefa de almacén", "categoria": "puesto", "generalizado": "mando intermedio"},
                              {"texto": "Arrecife", "categoria": "lugar", "generalizado": "un municipio de Lanzarote"},
                              {"texto": "trastorno adaptativo", "categoria": "salud", "generalizado": "un proceso de salud mental"},
                              {"texto": "inventado por el modelo", "categoria": "otro", "generalizado": "x"},
                              {"texto": "[PERSONA_001]", "categoria": "otro", "generalizado": "alguien"}]}
    antes = proveedores.actual
    proveedores.actual = lambda: Falso()
    try:
        a = contexto.analizar(texto)
    finally:
        proveedores.actual = antes
    textos = {h["texto"] for h in a["hallazgos"]}
    assert {"jefa de almacén", "Arrecife", "trastorno adaptativo", "54 años"} <= textos
    assert "inventado por el modelo" not in textos and "[PERSONA_001]" not in textos
    assert a["nivel"] == "alto"
    mapa = contexto.como_mapa([{"texto": "54 años", "reemplazo": "entre 50 y 59 años"},
                               {"texto": "Arrecife", "reemplazo": "un municipio de Lanzarote"}])
    assert motor.reemplazar_texto(texto, mapa).startswith("[PERSONA_001], de entre 50 y 59 años, trabaja como jefa de almacén en el centro de un municipio de Lanzarote")


def test_contexto_no_repite_lo_ya_generalizado_ni_duplica():
    import contexto
    import proveedores

    class Falso:
        def estructurado(self, modelo, mensajes, esquema):
            return {"datos": [{"texto": "un proceso de salud mental", "categoria": "salud", "generalizado": "algo"},
                              {"texto": "desde el 12/02/2026", "categoria": "fecha", "generalizado": "desde 2026"}]}
    antes = proveedores.actual
    proveedores.actual = lambda: Falso()
    try:
        a = contexto.analizar("De entre 50 y 59 años, de baja desde el 12/02/2026 por un proceso de salud mental.",
                              aplicadas=[{"texto": "trastorno adaptativo", "reemplazo": "un proceso de salud mental"},
                                         {"texto": "54 años", "reemplazo": "entre 50 y 59 años"}])
    finally:
        proveedores.actual = antes
    assert [(h["categoria"], h["texto"]) for h in a["hallazgos"]] == [("fecha", "12/02/2026")]


def test_contexto_unicidad_por_regla_y_con_generalizaciones_previas():
    import contexto
    import proveedores
    r = {(h["texto"], h["generalizado"]) for h in contexto._unicidad(
        "Es la única mujer con categoría de jefa de almacén en la isla dentro del grupo empresarial. "
        "Era la más antigua de la plantilla. Es el único que habla alemán en la oficina. "
        "La única prueba aportada es el correo. Lo único que consta es la carta.")}
    assert ("la única mujer con categoría de jefa de almacén en la isla dentro del grupo empresarial",
            "una mujer con categoría de jefa de almacén") in r
    assert ("la más antigua de la plantilla", "una de las personas con más antigüedad") in r
    assert ("el único que habla alemán en la oficina", "alguien que habla alemán") in r
    assert len(r) == 3            # ni «la única prueba» ni «lo único que consta»

    class Falso:
        def estructurado(self, modelo, mensajes, esquema):
            # el modelo señala un trozo de la misma frase y propone algo que sigue siendo único
            return {"datos": [{"texto": "única mujer con categoría de mando intermedio en la isla", "categoria": "unico",
                               "generalizado": "única persona con categoría de mando intermedio en la zona"}]}
    assert contexto._sin_unicidad("única persona con categoría de mando intermedio en la zona") == "una persona con categoría de mando intermedio"
    antes = proveedores.actual
    proveedores.actual = lambda: Falso()
    try:
        # segunda pasada: la copia ya lleva «mando intermedio» en lugar de «jefa de almacén»
        copia = "Es la única mujer con categoría de mando intermedio en la isla dentro del grupo empresarial."
        a = contexto.analizar(copia, aplicadas=[{"texto": "jefa de almacén", "reemplazo": "mando intermedio",
                                                 "categoria": "puesto"}])
    finally:
        proveedores.actual = antes
    h = [x for x in a["hallazgos"] if x["categoria"] == "unico"]
    assert len(h) == 1            # el trozo que señala el modelo está dentro de la frase de la regla
    assert h[0]["recomendado"] and h[0]["generalizado"] == "una mujer con categoría de mando intermedio"
    assert h[0]["original"] == "la única mujer con categoría de jefa de almacén en la isla dentro del grupo empresarial"
    original = "Es la única mujer con categoría de jefa de almacén en la isla dentro del grupo empresarial."
    mapa = contexto.como_mapa([{"texto": "jefa de almacén", "reemplazo": "mando intermedio"},
                               {"texto": h[0]["original"], "reemplazo": h[0]["generalizado"]}])
    assert motor.reemplazar_texto(original, mapa) == "Es una mujer con categoría de mando intermedio."


def test_tapar_a_mano_dentro_de_una_generalizacion():
    import multipasada
    base = [{"texto": "proceso", "tipo": "OTRO", "marcador": "[OTRO_001]"}]
    mapa = multipasada.mapa_completo(base, [{"texto": "trastorno adaptativo", "reemplazo": "un proceso de salud mental"}])
    original = "Está de baja por un trastorno adaptativo derivado del conflicto."
    assert motor.reemplazar_texto(original.replace("un trastorno", "trastorno"), mapa) == \
        "Está de baja por un [OTRO_001] de salud mental derivado del conflicto."


def test_zona_manual_del_rotulador_se_tapa_en_la_copia(tmp_path):
    import formatos
    from reportlab.pdfgen import canvas
    import multipasada
    import pdfdoc
    ruta = str(tmp_path / "doc.pdf")
    c = canvas.Canvas(ruta, pagesize=(595, 842))
    c.drawString(72, 760, "Cabecera de la empresa")
    c.drawString(72, 700, "Texto que se queda a la vista")
    c.save()
    # el rotulador tapa la cabecera (coordenadas de pantalla: origen arriba a la izquierda)
    doc = multipasada.TrabajoDocumento({"id": 7, "ruta": ruta, "rel": "doc.pdf", "nombre": "doc.pdf"}, None,
                                       {"zonas": {"7": [{"id": "a1", "pagina": 1, "rect": [60, 842 - 775, 300, 842 - 750]}]}}, str(tmp_path))
    doc._sembrar_zonas_manuales()
    assert 0 in doc.zonas_extra and doc.zonas_extra[0][0][1] == multipasada.MARCA_MANUAL
    salida = str(tmp_path / "copia.pdf")
    formatos.aplicar(ruta, salida, ".pdf", [], {"logos": False, "extra": doc.zonas_extra})
    texto = formatos.extraer_paginas(salida, ".pdf")[0]
    assert "Cabecera" not in texto and "a la vista" in texto and "[TAPADO]" in texto
    with pdfdoc.abrir(salida) as d:
        assert len(d) == 1 and d[0].renderizar(50).size[0] > 0


def test_zonas_manuales_del_proyecto():
    import trabajos
    assert trabajos.zonas_manuales({"zonas": None}) == {}
    assert trabajos.zonas_manuales({"zonas": "no es json"}) == {}
    assert trabajos.zonas_manuales({"zonas": '{"7": [{"id": "a", "pagina": 1, "rect": [1, 2, 3, 4]}]}'})["7"][0]["pagina"] == 1


def test_vista_office_solo_si_hay_programa():
    import oficina
    # en este equipo de pruebas no hay Office: la copia se ve en texto y a_pdf no hace nada
    assert oficina.programa(".txt") is None
    if oficina.programa(".docx") is None:
        assert oficina.a_pdf("/no/existe.docx") is None


def test_equipo_semaforo(monkeypatch):
    """¿Llega este ordenador? Verde, amarillo y rojo según memoria, espacio, procesador y gráfica."""
    import equipo
    import rutas

    def fijar(mac=False, win=False, mem=16.0, cpu_ok=True, graficas=(), libre=100.0, so_ok=True):
        monkeypatch.setattr(rutas, "ES_MAC", mac)
        monkeypatch.setattr(rutas, "ES_WINDOWS", win)
        monkeypatch.setattr(equipo, "espacio_libre_gb", lambda: libre)
        monkeypatch.setattr(equipo, "_fijos", lambda: {"memoria_gb": mem, "procesador": "X", "procesador_ok": cpu_ok,
                                                       "sistema": "S", "sistema_ok": so_ok, "graficas": list(graficas)})

    fijar(mac=True, mem=16)
    assert equipo.comprobar(False, False)["nivel"] == "verde"
    fijar(mac=True, mem=8)
    r = equipo.comprobar(False, False)
    assert r["nivel"] == "rojo" and "8 GB" in r["motivos"][0]
    fijar(mac=True, mem=12)
    assert equipo.comprobar()["nivel"] == "amarillo"
    fijar(mac=True, cpu_ok=False)
    assert "Intel" in equipo.comprobar()["motivos"][0]
    fijar(mac=True, libre=10)
    r = equipo.comprobar(False, False)
    assert r["nivel"] == "rojo" and r["espacio_necesario_gb"] == 16
    fijar(mac=True, libre=10)
    assert equipo.comprobar(True, True)["nivel"] == "verde"       # ya está todo descargado
    fijar(win=True, mem=16, graficas=[{"nombre": "Intel UHD", "vram_gb": None, "acelera": False}])
    r = equipo.comprobar()
    assert r["nivel"] == "amarillo" and "tarjeta gráfica" in r["motivos"][0]
    fijar(win=True, mem=32, graficas=[{"nombre": "NVIDIA RTX 4060", "vram_gb": 8, "acelera": True}])
    assert equipo.comprobar()["nivel"] == "verde"
    fijar(win=True, mem=32, graficas=[{"nombre": "NVIDIA RTX 4060", "vram_gb": 8, "acelera": True}], so_ok=False)
    assert "Windows Update" in equipo.comprobar()["motivos"][0]
