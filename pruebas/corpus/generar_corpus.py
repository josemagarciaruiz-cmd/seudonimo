# -*- coding: utf-8 -*-
"""Corpus sintético etiquetado para medir la seudonimización. TODOS LOS DATOS SON INVENTADOS.

Uso:  python generar_corpus.py <carpeta de salida>
Crea los documentos y «etiquetas.json», con lo que debe desaparecer y lo que debe quedarse.

Categorías de las etiquetas:
- sensibles: identificadores críticos (deben desaparecer: cuentan para el recall crítico).
- parciales: restos parciales (nombre de pila suelto, apellido suelto). Se miden aparte.
- cuasi: cuasi-identificadores (municipio, código postal, centro de salud). Se miden aparte.
- conservar: datos jurídicamente necesarios que NO deben taparse (antigüedad, importes, categoría).
- esperado: «sin_hallazgos» o «revision» (p. ej., un Word con control de cambios debe ir a revisión).

Necesita (solo para generar): reportlab, openpyxl, python-docx, python-pptx, Pillow."""
import json
import os
import random
import runpy
import sys
import textwrap

SAL = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "generado")
os.makedirs(SAL, exist_ok=True)
os.environ["CORPUS_SALIDA"] = SAL
B = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_base.py"))
P, EMPRESA, CIF, EMP_DIR, EMP_TEL, EMP_CCC, RRHH, RRHH_DNI = (B[k] for k in (
    "personas", "EMPRESA", "CIF", "EMP_DIR", "EMP_TEL", "EMP_CCC", "RRHH", "RRHH_DNI"))
dni, nie, naf, iban, tel = B["dni"], B["nie"], B["naf"], B["iban"], B["tel"]
random.seed(20261126)

ET = {}


def S(t, tipo):
    return {"texto": t, "tipo": tipo}


def persona(p, nac=True, dom=True, cuenta=True, correo=True, telefono=True):
    s = [S(p["completo"], "PERSONA"), S(p["doc"], "DNI"), S(p["naf"], "NAF")]
    if nac: s.append(S(p["nac"], "F_NACIMIENTO"))
    if dom: s.append(S(p["dir"], "DOMICILIO"))
    if cuenta: s.append(S(p["iban"], "IBAN"))
    if correo: s.append(S(p["email"], "EMAIL"))
    if telefono: s.append(S(p["tel"], "TELEFONO"))
    return s


EMPRESA_CORTA = "Hoteles Volcán Azul"
EMP = [S(EMPRESA_CORTA, "EMPRESA"), S(CIF, "NIF"), S(EMP_TEL, "TELEFONO"), S(EMP_CCC, "CCC"),
       S(RRHH[0], "PERSONA"), S(RRHH[1], "EMAIL"), S("Avenida de las Playas, 61", "DOMICILIO")]

# ------------------------------------------------------------------ etiquetas de los seis documentos base
ev = ["Rayco Perdomo Viera", "Margarita Cabrera Toledo", "Airam Duarte Santana"]
s = EMP[:]
for p in P:
    s += persona(p) + [S(p["depto"], "DEPARTAMENTO")]
ET["Evaluación del desempeño 2026 - Hoteles Volcán Azul.xlsx"] = {
    "sensibles": s + [S(x, "PERSONA") for x in ev],
    "parciales": [S(p["nombre"], "PERSONA") for p in P],
    "cuasi": [S(p["pueblo"], "MUNICIPIO") for p in P],
    "conservar": [p["ant"] for p in P] + [p["puesto"] for p in P], "esperado": "sin_hallazgos"}
s = []
for p in P[:12]:
    s += [S(p["ap1"] + " " + p["ap2"], "PERSONA"), S(p["doc"], "DNI"), S(p["naf"], "NAF"), S(p["nac"], "F_NACIMIENTO"),
          S(p["dir"], "DOMICILIO"), S(p["tel"], "TELEFONO"), S(p["email"], "EMAIL"), S(p["iban"], "IBAN")]
ET["Listado de plantilla - altas y datos bancarios.csv"] = {
    "sensibles": s, "parciales": [S(p["nombre"], "PERSONA") for p in P[:12]],
    "cuasi": [S(p["pueblo"], "MUNICIPIO") for p in P[:12]], "conservar": [p["ant"] for p in P[:12]], "esperado": "sin_hallazgos"}
p2, q5 = P[2], P[5]
ET["Comunicación de sanción y certificado de empresa.pdf"] = {
    "sensibles": EMP + persona(p2, nac=False, cuenta=False, correo=False) + persona(q5, telefono=False) + [
        S("Rayco Perdomo Viera", "PERSONA"), S("20260045123300871", "REGISTRO"), S(RRHH_DNI, "DNI"),
        S("HVA7K-2Q9PL-M4R8T-ZX61C", "CSV"), S(p2["depto"], "DEPARTAMENTO")],
    "parciales": [S(p2["nombre"], "PERSONA")], "cuasi": [S(p2["pueblo"], "MUNICIPIO")],
    "conservar": [q5["ant"], "%.2f" % q5["salario"], "falta leve"], "esperado": "sin_hallazgos"}
a, b, e = P[0], P[7], P[10]
ET["Captura chat 1 - datos para el alta.png"] = {
    "sensibles": persona(a, nac=False, correo=False), "parciales": [], "cuasi": [S(a["pueblo"], "MUNICIPIO")],
    "conservar": [], "esperado": "sin_hallazgos"}
ET["Captura chat 2 - baja médica.png"] = {
    "sensibles": [S(b["nombre"] + " " + b["ap1"], "PERSONA"), S(b["doc"], "DNI"), S(b["email"], "EMAIL"),
                  S("Armando Rodríguez Feo", "PERSONA")],
    "parciales": [S(b["nombre"], "PERSONA")], "cuasi": [S("Valterra", "LUGAR"), S(b["depto"].lower(), "DEPARTAMENTO")],
    "conservar": [], "esperado": "sin_hallazgos"}
ET["Captura chat 3 - cliente empresa.png"] = {
    "sensibles": [S(e["completo"], "PERSONA"), S(CIF, "NIF"), S(EMP_CCC, "CCC"), S(e["dir"], "DOMICILIO"),
                  S(e["tel"], "TELEFONO"), S(e["iban"], "IBAN")],
    "parciales": [S("Rayco", "PERSONA")], "cuasi": [S(e["pueblo"], "MUNICIPIO")],
    "conservar": [e["ant"], "%.2f" % e["salario"]], "esperado": "sin_hallazgos"}

# ------------------------------------------------------------------ 7. Contrato (Word): runs partidos, cabecera,
# pie, comentario, propiedades y un cambio controlado (que debe llevar el documento a revisión)
from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402

c3 = P[3]
d = Document()
d.core_properties.author = RRHH[0]
d.core_properties.title = "Contrato de %s" % c3["completo"]
d.sections[0].header.paragraphs[0].text = "%s · CIF %s" % (EMPRESA, CIF)
d.sections[0].footer.paragraphs[0].text = "Recursos Humanos: %s · Tel. %s" % (RRHH[1], EMP_TEL)
d.add_heading("CONTRATO DE TRABAJO INDEFINIDO", 1)
d.add_paragraph("En Puerto del Carmen, a 2 de noviembre de 2026.")
d.add_paragraph("De una parte, Dña. %s, con DNI %s, en nombre y representación de %s." % (RRHH[0], RRHH_DNI, EMPRESA))
par = d.add_paragraph("De otra parte, D./Dña. ")
r1 = par.add_run(c3["nombre"]); r1.bold = True
par.add_run(" "); par.add_run(c3["ap1"]); r4 = par.add_run(" " + c3["ap2"]); r4.italic = True
par.add_run(", con DNI/NIE %s y número de afiliación %s, nacido/a el %s, con domicilio en %s, %s %s." % (
    c3["doc"], c3["naf"], c3["nac"], c3["dir"], c3["cp"], c3["pueblo"]))
d.add_paragraph("CLÁUSULAS").runs[0].bold = True
d.add_paragraph("Primera. La persona trabajadora prestará servicios como %s, en el grupo profesional que corresponda "
                "según el convenio colectivo de hostelería de Las Palmas, con antigüedad reconocida desde el %s." % (
                    c3["puesto"], c3["ant"]))
d.add_paragraph("Segunda. El salario bruto mensual será de %.2f euros, abonado por transferencia a la cuenta %s." % (
    c3["salario"], c3["iban"]))
pc = d.add_paragraph("Tercera. Teléfono de contacto: ")
rc = pc.add_run(c3["tel"])
try:
    d.add_comment(rc, text="Confirmar con %s si el móvil sigue siendo este; el correo es %s." % (c3["nombre"], c3["email"]),
                  author=RRHH[0], initials="MC")
except Exception:  # python-docx sin comentarios
    pass
# cambio controlado: un teléfono antiguo borrado que sigue dentro del archivo
p_del = d.add_paragraph("Cuarta. Teléfono anterior: ")
viejo = tel()
dl = OxmlElement("w:del"); dl.set(qn("w:id"), "1"); dl.set(qn("w:author"), RRHH[0]); dl.set(qn("w:date"), "2026-11-02T10:00:00Z")
rr = OxmlElement("w:r"); dt = OxmlElement("w:delText"); dt.text = viejo; rr.append(dt); dl.append(rr)
p_del._p.append(dl)
n_contrato = "Contrato de trabajo - %s %s.docx" % (c3["ap1"], c3["ap2"])
d.save(os.path.join(SAL, n_contrato))
ET[n_contrato] = {"sensibles": EMP[:6] + [S(RRHH_DNI, "DNI")] + persona(c3) + [S(c3["ap1"] + " " + c3["ap2"], "PERSONA")],
                  "parciales": [S(c3["nombre"], "PERSONA")], "cuasi": [S(c3["pueblo"], "MUNICIPIO")],
                  "conservar": [c3["ant"], "%.2f" % c3["salario"], c3["puesto"]], "oculto": [S(viejo, "TELEFONO")],
                  "esperado": "revision"}

# ------------------------------------------------------------------ 8. Nómina (PDF nativo): antigüedad y periodo se conservan
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

n4 = P[4]
nom = "Nómina octubre 2026.pdf"
cv = canvas.Canvas(os.path.join(SAL, nom), pagesize=A4)
W, H = A4
cv.setFont("DVB", 12); cv.drawString(40, H - 50, "RECIBO INDIVIDUAL JUSTIFICATIVO DEL PAGO DE SALARIOS")
cv.setFont("DV", 9)
izq = ["Empresa: " + EMPRESA, "CIF: " + CIF, "Domicilio: " + EMP_DIR, "C.C.C.: " + EMP_CCC]
der = ["Trabajador/a: " + n4["completo"], "DNI: " + n4["doc"], "N.º afiliación: " + n4["naf"],
       "Categoría: " + n4["puesto"], "Antigüedad: " + n4["ant"], "Periodo de liquidación: 01/10/2026 al 31/10/2026"]
for i, t in enumerate(izq):
    cv.drawString(40, H - 80 - 13 * i, t)
for i, t in enumerate(der):
    cv.drawString(320, H - 80 - 13 * i, t)
y = H - 180
cv.setFont("DVB", 9); cv.drawString(40, y, "DEVENGOS"); cv.drawString(420, y, "IMPORTE"); y -= 16
cv.setFont("DV", 9)
for con, imp in [("Salario base", n4["salario"] * 0.8), ("Plus de transporte", 82.15), ("Antigüedad (trienios)", n4["salario"] * 0.08),
                 ("Plus de nocturnidad", 41.30)]:
    cv.drawString(40, y, con); cv.drawRightString(480, y, ("%.2f" % imp).replace(".", ",")); y -= 13
total = n4["salario"] * 0.88 + 123.45
y -= 6; cv.setFont("DVB", 9); cv.drawString(40, y, "TOTAL DEVENGADO"); cv.drawRightString(480, y, ("%.2f" % total).replace(".", ",")); y -= 30
cv.setFont("DV", 9)
cv.drawString(40, y, "Líquido a percibir mediante transferencia a la cuenta " + n4["iban"]); y -= 13
cv.drawString(40, y, "Firma y sello de la empresa"); cv.drawString(320, y, "Recibí: " + n4["nombre"] + " " + n4["ap1"])
cv.setFont("DV", 7); cv.drawString(40, 30, "Documento con datos ficticios generado para probar Seudónimo.")
cv.save()
ET[nom] = {"sensibles": [S(EMPRESA_CORTA, "EMPRESA"), S(CIF, "NIF"), S("Avenida de las Playas, 61", "DOMICILIO"), S(EMP_CCC, "CCC"),
                         S(n4["completo"], "PERSONA"), S(n4["doc"], "DNI"), S(n4["naf"], "NAF"), S(n4["iban"], "IBAN"),
                         S(n4["nombre"] + " " + n4["ap1"], "PERSONA")],
           "parciales": [], "cuasi": [], "conservar": [n4["ant"], "01/10/2026 al 31/10/2026", ("%.2f" % total).replace(".", ","), n4["puesto"]],
           "esperado": "sin_hallazgos"}

# ------------------------------------------------------------------ 9. Sentencia escaneada (imagen dentro de PDF), una página girada
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

s6, s8 = P[6], P[8]
F = "/usr/share/fonts/truetype/dejavu/"
fnt = ImageFont.truetype(F + "DejaVuSerif.ttf", 30); fntb = ImageFont.truetype(F + "DejaVuSerif-Bold.ttf", 32)
texto1 = [("b", "JUZGADO DE LO SOCIAL Nº 1 DE ARRECIFE"), ("", "Autos: Despido 812/2026"), ("", ""),
          ("b", "SENTENCIA Nº 431/2026"), ("", ""),
          ("", "En Arrecife, a 20 de noviembre de 2026."), ("", ""),
          ("", "Vistos los presentes autos seguidos a instancia de D./Dña. %s, con DNI %s," % (s6["completo"], s6["doc"])),
          ("", "asistido/a por la letrada Dña. %s, frente a la empresa %s," % ("Nerea Umpiérrez Santana", EMPRESA)),
          ("", "con CIF %s, sobre despido." % CIF), ("", ""), ("b", "HECHOS PROBADOS"),
          ("", "PRIMERO.- La parte actora ha venido prestando servicios para la demandada con"),
          ("", "antigüedad desde el %s, categoría de %s y salario de %.2f euros" % (s6["ant"], s6["puesto"].lower(), s6["salario"])),
          ("", "mensuales con prorrata de pagas extraordinarias."),
          ("", "SEGUNDO.- Con fecha 30/09/2026 la empresa entregó a la actora carta de despido."),
          ("", "TERCERO.- La actora reside en %s, %s %s." % (s6["dir"], s6["cp"], s6["pueblo"]))]


def pagina(lineas, girar=0):
    im = Image.new("L", (2480, 3508), 250); dr = ImageDraw.Draw(im)
    y = 260
    for estilo, t in lineas:
        for l in textwrap.wrap(t, 70) or [""]:
            dr.text((220, y), l, font=fntb if estilo == "b" else fnt, fill=25); y += 52
    im = im.rotate(0.6, fillcolor=250).filter(ImageFilter.GaussianBlur(0.6))
    if girar:
        im = im.rotate(girar, expand=True, fillcolor=250)
    return im.convert("RGB")


texto2 = [("b", "FALLO"), ("", "Estimo la demanda interpuesta por D./Dña. %s y declaro improcedente" % s6["completo"]),
          ("", "el despido. Notifíquese a las partes, haciéndoles saber que contra esta sentencia cabe"),
          ("", "recurso de suplicación. Testigo: D. %s, con domicilio en %s." % (s8["completo"], s8["dir"]))]
pags = [pagina(texto1), pagina(texto2, girar=90)]
sen = "Sentencia despido (escaneada).pdf"
pags[0].save(os.path.join(SAL, sen), save_all=True, append_images=pags[1:], resolution=300)
ET[sen] = {"sensibles": [S(s6["completo"], "PERSONA"), S(s6["doc"], "DNI"), S("Nerea Umpiérrez Santana", "PERSONA"),
                         S(EMPRESA_CORTA, "EMPRESA"), S(CIF, "NIF"), S(s6["dir"], "DOMICILIO"), S("812/2026", "EXPEDIENTE"),
                         S(s8["completo"], "PERSONA"), S(s8["dir"], "DOMICILIO")],
           "parciales": [], "cuasi": [S(s6["pueblo"], "MUNICIPIO")],
           "conservar": [s6["ant"], "%.2f" % s6["salario"], "JUZGADO DE LO SOCIAL"], "esperado": "sin_hallazgos"}

# ------------------------------------------------------------------ 10. Notas en texto: nombre partido entre líneas, relación indirecta
t9, t11 = P[9], P[11]
notas = "Notas de la reunión con el cliente.txt"
with open(os.path.join(SAL, notas), "w", encoding="utf-8") as f:
    f.write("Reunión 18/11/2026 — Hoteles Volcán Azul\n\n"
            "Asisten: Rayco (gerente) y la responsable de RR. HH.\n"
            "Caso de D. %s\n%s %s (NIE/DNI %s). Móvil %s.\n"
            "Su hermana, %s, también trabaja en el hotel (%s).\n"
            "Correo de contacto: %s\n"
            "Pendiente: calcular indemnización con antigüedad %s.\n" % (
                t9["nombre"], t9["ap1"], t9["ap2"], t9["doc"], t9["tel"].replace(" ", ""), t11["completo"], t11["depto"],
                t9["email"], t9["ant"]))
ET[notas] = {"sensibles": [S(t9["nombre"] + " " + t9["ap1"] + " " + t9["ap2"], "PERSONA"), S(t9["doc"], "DNI"),
                           S(t9["tel"], "TELEFONO"), S(t11["completo"], "PERSONA"), S(t9["email"], "EMAIL"),
                           S(EMPRESA_CORTA, "EMPRESA"), S(t11["depto"], "DEPARTAMENTO")],
             "parciales": [S("Rayco", "PERSONA")], "cuasi": [], "conservar": [t9["ant"], "18/11/2026"], "esperado": "sin_hallazgos"}

# ------------------------------------------------------------------ 11. Presentación con notas del orador
from pptx import Presentation  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

pr = Presentation()
sl = pr.slides.add_slide(pr.slide_layouts[1])
sl.shapes.title.text = "Comité de empresa · %s" % EMPRESA_CORTA
tf = sl.placeholders[1].text_frame
tf.text = "Delegado: Rayco Perdomo Viera"
for p in P[12:15]:
    tf.add_paragraph().text = "%s — %s" % (p["completo"], p["depto"])
sl.notes_slide.notes_text_frame.text = "Llamar a %s al %s antes del comité." % (P[12]["completo"], P[12]["tel"])
pres = "Presentación comité.pptx"
pr.save(os.path.join(SAL, pres))
ET[pres] = {"sensibles": [S(EMPRESA_CORTA, "EMPRESA"), S("Rayco Perdomo Viera", "PERSONA")] +
            [S(p["completo"], "PERSONA") for p in P[12:15]] + [S(p["depto"], "DEPARTAMENTO") for p in P[12:15]] +
            [S(P[12]["tel"], "TELEFONO")], "parciales": [], "cuasi": [], "conservar": [], "esperado": "sin_hallazgos"}

# ------------------------------------------------------------------ 12. Libro con hoja oculta y comentario
import openpyxl  # noqa: E402
from openpyxl.comments import Comment  # noqa: E402

wb = openpyxl.Workbook()
w1 = wb.active; w1.title = "Resumen"
w1["A1"] = "Turnos de diciembre"; w1["A2"] = "Personas"; w1["B2"] = 4
w1["A3"] = "Responsable"; w1["B3"] = RRHH[0]
w1["B3"].comment = Comment("DNI de la responsable: %s" % RRHH_DNI, "RRHH")
w2 = wb.create_sheet("Contactos"); w2.sheet_state = "hidden"
w2.append(["Nombre", "Teléfono", "Correo"])
for p in P[:4]:
    w2.append([p["completo"], p["tel"], p["email"]])
oc = "Turnos con hoja oculta.xlsx"
wb.save(os.path.join(SAL, oc))
ET[oc] = {"sensibles": [S(RRHH[0], "PERSONA"), S(RRHH_DNI, "DNI")] +
          sum([[S(p["completo"], "PERSONA"), S(p["tel"], "TELEFONO"), S(p["email"], "EMAIL")] for p in P[:4]], []),
          "parciales": [], "cuasi": [], "conservar": ["Turnos de diciembre"], "esperado": "sin_hallazgos"}

with open(os.path.join(SAL, "etiquetas.json"), "w", encoding="utf-8") as f:
    json.dump(ET, f, ensure_ascii=False, indent=1)
print("\n".join(sorted(os.listdir(SAL))))
