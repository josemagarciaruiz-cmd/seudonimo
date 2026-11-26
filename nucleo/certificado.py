# -*- coding: utf-8 -*-
"""Certificado de la seudonimización (PDF) para incorporarlo al expediente.

Deja constancia de qué se hizo, con qué método y con qué resultado, SIN datos originales: los
documentos se identifican por el nombre de su copia seudonimizada y por la huella SHA-256 del
original y de la copia (permite comprobar después que el archivo es el mismo sin revelar su
contenido). Se genera con ReportLab (licencia BSD)."""
import hashlib
import os
import time

import motor
import rutas
from version import VERSION

NOMBRE = "Certificado de seudonimización.pdf"


def huella(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def generar(informe, destino, documentos, proyecto=""):
    """documentos: [{"copia", "estado_texto", "ciclos", "sha_original", "sha_copia"}]."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape as e

    noche, oro, gris = colors.HexColor("#16222F"), colors.HexColor("#A8822A"), colors.HexColor("#5B6472")
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=noche, alignment=TA_LEFT)
    titulo = ParagraphStyle("t", parent=base, fontName="Times-Bold", fontSize=20, leading=24, spaceAfter=2)
    sub = ParagraphStyle("s", parent=base, textColor=gris, fontSize=9)
    h2 = ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=10, spaceAfter=4)
    peq = ParagraphStyle("p", parent=base, fontSize=7.5, leading=9.5, textColor=gris)
    celda = ParagraphStyle("c", parent=base, fontSize=8.5, leading=10.5)
    mono = ParagraphStyle("m", parent=celda, fontName="Courier", fontSize=6.1, leading=8.4, textColor=gris)

    ruta = os.path.join(destino, NOMBRE)
    doc = SimpleDocTemplate(ruta, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title="Certificado de seudonimización", author=rutas.NOMBRE)
    rec = informe.get("recuento", {})
    par = informe.get("parametros", {})
    reg = informe.get("registro", {})
    h = []
    h.append(Paragraph("Certificado de seudonimización", titulo))
    h.append(Paragraph("Emitido por %s %s el %s%s" % (e(rutas.NOMBRE), e(VERSION), e(informe.get("fecha", time.strftime("%Y-%m-%d %H:%M"))),
                                                     (" · Proyecto: %s" % e(proyecto)) if proyecto else ""), sub))
    h.append(Spacer(1, 8))

    h.append(Paragraph("Resultado", h2))
    filas = [["Documentos tratados", str(len(informe.get("documentos", [])))],
             ["Sin hallazgos en las comprobaciones configuradas", str(rec.get("sin_hallazgos", 0))],
             ["Requieren revisión", str(rec.get("revision", 0))],
             ["Con error de procesamiento", str(rec.get("error", 0))],
             ["Datos distintos sustituidos por marcadores", str(reg.get("entidades", 0))]]
    t = Table(filas, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 9.5), ("TEXTCOLOR", (0, 0), (-1, -1), noche),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#D8D2C6")),
                           ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    h.append(t)

    por_tipo = reg.get("por_tipo") or {}
    if por_tipo:
        h.append(Paragraph("Categorías de datos sustituidas", h2))
        h.append(Paragraph(" · ".join("%s: %d" % (e(motor.ETIQUETAS.get(k, k)), v) for k, v in sorted(por_tipo.items())), base))

    h.append(Paragraph("Método", h2))
    h.append(Paragraph(
        "Seudonimización local: ningún documento ni dato ha salido del equipo. Modelo de lenguaje <b>%s</b> ejecutado "
        "en el propio ordenador, reglas de detección de identificadores y OCR local para las páginas escaneadas. "
        "Verificación <b>%s</b>: %d pasadas de detección; ciclos de reconstrucción desde el original inmutable con "
        "verificación independiente (máximo %s ciclos; %s verificación(es) limpias consecutivas exigidas%s). "
        "Cada dato se sustituye por un marcador estable del proyecto (por ejemplo [PERSONA_001])." % (
            e(str(informe.get("modelo") or "—")), "intensiva" if informe.get("perfil") == "intensivo" else "estándar",
            par.get("min_detecciones", 2), par.get("max_ciclos", "—"), par.get("limpias", 1),
            "; con modelo auditor" if par.get("modelo_auditor") else ""), base))

    h.append(Paragraph("Documentos", h2))
    filas = [[Paragraph("<b>Copia seudonimizada</b>", celda), Paragraph("<b>Resultado</b>", celda),
              Paragraph("<b>Huellas SHA-256</b><br/>original (arriba) y copia (abajo)", celda)]]
    for d in documentos:
        filas.append([Paragraph(e(d["copia"]), celda), Paragraph("%s<br/>%d ciclo(s)" % (e(d["estado_texto"]), d.get("ciclos", 0)), celda),
                      Paragraph("%s<br/>%s" % (d.get("sha_original", "—"), d.get("sha_copia", "—")), mono)])
    t = Table(filas, colWidths=[57 * mm, 32 * mm, 85 * mm], repeatRows=1)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#D8D2C6")),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.8, oro), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    h.append(t)

    h.append(Paragraph("Alcance y límites", h2))
    h.append(Paragraph(
        "La seudonimización sustituye los datos identificativos por marcadores, de modo que los documentos ya no pueden "
        "atribuirse a una persona concreta sin la tabla de correspondencias, que se conserva por separado y cifrada en "
        "el equipo del profesional (art. 4.5 del Reglamento (UE) 2016/679). Los datos seudonimizados siguen siendo datos "
        "personales (considerando 26 RGPD). «Sin hallazgos en las comprobaciones configuradas» no equivale a "
        "anonimización garantizada: la ausencia de coincidencias no demuestra la ausencia de datos desconocidos, y la "
        "persona puede seguir siendo identificable por el contexto. Los documentos marcados para revisión no deben "
        "comunicarse a terceros sin revisarlos.", base))
    h.append(Spacer(1, 10))
    h.append(Paragraph("Este certificado no contiene datos personales de los documentos. Las huellas permiten comprobar, "
                       "calculando de nuevo el SHA-256, que un archivo es exactamente el que se trató.", peq))

    def pie(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(gris)
        canvas.drawString(18 * mm, 10 * mm, "%s · Certificado de seudonimización" % rutas.NOMBRE)
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, "Página %d" % d.page)
        canvas.setStrokeColor(oro)
        canvas.setLineWidth(1.2)
        canvas.line(18 * mm, A4[1] - 10 * mm, A4[0] - 18 * mm, A4[1] - 10 * mm)
        canvas.restoreState()

    doc.build(h, onFirstPage=pie, onLaterPages=pie)
    return ruta
