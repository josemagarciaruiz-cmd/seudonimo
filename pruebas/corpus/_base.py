"""Genera material de prueba para Seudónimo. TODOS LOS DATOS SON INVENTADOS.
Los DNI, NAF, CCC e IBAN tienen formato y dígitos de control válidos, pero son aleatorios."""
import csv, os, random, math
from PIL import Image, ImageDraw, ImageFont
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

random.seed(20261116)
OUT = os.environ["CORPUS_SALIDA"]
os.makedirs(OUT, exist_ok=True)
F = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", F + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", F + "DejaVuSans-Bold.ttf"))

# ------------------------------------------------------------------ datos inventados
def dni():
    n = random.randint(10_000_000, 79_999_999)
    return "%08d%s" % (n, "TRWAGMYFPDXBNJZSQVHLCKE"[n % 23])

def nie():
    pre = random.choice("XYZ"); n = random.randint(1_000_000, 9_999_999)
    num = int({"X": "0", "Y": "1", "Z": "2"}[pre] + "%07d" % n)
    return "%s%07d%s" % (pre, n, "TRWAGMYFPDXBNJZSQVHLCKE"[num % 23])

def naf():
    base = 35 * 10**8 + random.randint(10_000_000, 99_999_999)
    return "35 %08d %02d" % (base % 10**8, base % 97)

def ccc():
    base = 35 * 10**7 + random.randint(1_000_000, 9_999_999)
    return "35 %07d %02d" % (base % 10**7, base % 97)

def iban():
    entidad = random.choice(["2100", "0049", "0182", "3058", "2085", "0081"])
    oficina = "%04d" % random.randint(1000, 9999)
    cuenta = "%010d" % random.randint(0, 10**10 - 1)
    pesos = [1, 2, 4, 8, 5, 10, 9, 7, 3, 6]
    def dc(s):
        r = 11 - sum(int(c) * p for c, p in zip(s, pesos)) % 11
        return {10: 1, 11: 0}.get(r, r)
    ccc_b = entidad + oficina + "%d%d" % (dc("00" + entidad + oficina), dc(cuenta)) + cuenta
    chk = 98 - int(ccc_b + "142800") % 97
    s = "ES%02d%s" % (chk, ccc_b)
    return " ".join(s[i:i + 4] for i in range(0, 24, 4))

def tel():
    return "6%02d %03d %03d" % (random.randint(0, 99), random.randint(0, 999), random.randint(0, 999))

nombres = ["Lucía", "Marcos", "Carmen", "Javier", "Nerea", "Óscar", "Yaiza", "Adrián", "Beatriz", "Iván",
           "Raquel", "Tomás", "Daniela", "Héctor", "Ainhoa"]
apellidos = ["Ferrer", "Cabrera", "Betancort", "Medina", "Perdomo", "Rodríguez", "Umpiérrez", "Hernández",
             "Curbelo", "Morales", "Toledo", "Duarte", "Guadalupe", "Robayna", "Santana", "Fajardo", "Viera"]
calles = ["Calle Fajardo", "Avenida Mancomunidad", "Calle José Antonio", "Calle Triana", "Calle Coronel Bens",
          "Calle La Inés", "Avenida Fred Olsen", "Calle Canalejas", "Calle Teniente Coronel Serra",
          "Calle Juan Quesada", "Calle Hermanos Zerolo", "Calle Pérez Galdós", "Calle Doctor Rafael González"]
pueblos = [("35500", "Arrecife"), ("35509", "Playa Honda"), ("35510", "Puerto del Carmen"),
           ("35507", "Tahíche"), ("35530", "Teguise"), ("35580", "Playa Blanca"), ("35570", "Yaiza")]
puestos = [("Recepcionista", "Recepción"), ("Camarero/a", "Restaurante Buffet"), ("Cocinero/a", "Cocina Central"),
           ("Camarera de pisos", "Pisos y Lencería"), ("Animador/a", "Animación"), ("Técnico de mantenimiento", "Servicio Técnico"),
           ("Administrativo/a", "Administración y Contabilidad"), ("Jefe/a de sector", "Restaurante Buffet"),
           ("Ayudante de cocina", "Cocina Central"), ("Socorrista", "Piscinas y Spa")]

EMPRESA = "Hoteles Volcán Azul, S.L."
CIF = "B" + "%08d" % random.randint(35_000_000, 35_999_999)
EMP_DIR = "Avenida de las Playas, 61, 35510 Puerto del Carmen (Tías)"
EMP_TEL = "928 51 %02d %02d" % (random.randint(10, 99), random.randint(10, 99))
EMP_CCC = ccc()
RRHH = ("Margarita Cabrera Toledo", "rrhh@volcanazul-hoteles.es")
RRHH_DNI = None  # se fija más abajo, donde lo usa el certificado (mismo orden de números aleatorios)

personas = []
usados = set()
while len(personas) < 15:
    n = random.choice(nombres); a1, a2 = random.sample(apellidos, 2)
    if (n, a1) in usados:
        continue
    usados.add((n, a1))
    cp, pueblo = random.choice(pueblos)
    puesto, depto = random.choice(puestos)
    nac = "%02d/%02d/%d" % (random.randint(1, 28), random.randint(1, 12), random.randint(1965, 2001))
    ant = "%02d/%02d/%d" % (random.randint(1, 28), random.randint(1, 12), random.randint(2008, 2024))
    personas.append(dict(
        nombre=n, ap1=a1, ap2=a2, completo="%s %s %s" % (n, a1, a2),
        doc=nie() if random.random() < 0.2 else dni(), naf=naf(), iban=iban(), tel=tel(),
        email="%s.%s%d@%s" % (n.lower().replace("ó", "o").replace("í", "i"), a1.lower().replace("í", "i").replace("é", "e"),
                               random.randint(1, 99), random.choice(["gmail.com", "hotmail.com", "yahoo.es"])),
        dir="%s, %d%s" % (random.choice(calles), random.randint(1, 120), random.choice(["", ", 1º A", ", 2º B", ", bajo", ""])),
        cp=cp, pueblo=pueblo, nac=nac, ant=ant, puesto=puesto, depto=depto,
        salario=random.choice([1381.33, 1452.10, 1530.75, 1618.40, 1725.00, 1890.25, 2104.60]),
        notas=[random.randint(2, 5) for _ in range(5)]))

# ------------------------------------------------------------------ 1. Excel: evaluación del desempeño
wb = openpyxl.Workbook()
ws = wb.active; ws.title = "Evaluación 2026"
oro = PatternFill("solid", fgColor="D4A853"); claro = PatternFill("solid", fgColor="F7F0DE")
fino = Side(style="thin", color="C9B98F"); borde = Border(left=fino, right=fino, top=fino, bottom=fino)
ws["A1"] = "EVALUACIÓN DEL DESEMPEÑO · EJERCICIO 2026"; ws["A1"].font = Font(bold=True, size=14)
ws["A2"] = "%s · CIF %s · %s" % (EMPRESA, CIF, EMP_DIR)
ws["A3"] = "Responsable de RR. HH.: %s (%s) · Tel. %s" % (RRHH[0], RRHH[1], EMP_TEL)
ws["A4"] = "Datos ficticios generados para probar Seudónimo."; ws["A4"].font = Font(italic=True, color="888888", size=9)
cab = ["Nº", "Nombre y apellidos", "DNI / NIE", "N.º afiliación SS", "Fecha nacimiento", "Fecha antigüedad",
       "Puesto", "Departamento", "Domicilio", "C.P.", "Municipio", "Teléfono", "Correo electrónico", "IBAN nómina",
       "Salario bruto mensual (€)", "Orientación al cliente", "Trabajo en equipo", "Calidad del trabajo",
       "Puntualidad", "Iniciativa", "Media", "Valoración", "Comentarios del evaluador"]
fila0 = 6
for c, t in enumerate(cab, 1):
    x = ws.cell(row=fila0, column=c, value=t); x.font = Font(bold=True, color="1C1917"); x.fill = oro
    x.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center"); x.border = borde
evaluadores = ["Rayco Perdomo Viera", "Margarita Cabrera Toledo", "Airam Duarte Santana"]
comentarios = [
    "{n} muestra gran implicación. Hablado con {n} el 14/10 sobre su interés en pasar a turno de mañana.",
    "Buen desempeño. Se recomienda formación en idiomas. {nc} lo comentó en la reunión con {ev}.",
    "Debe mejorar la puntualidad (3 retrasos en septiembre). Se le comunicó por escrito a {nc}.",
    "Excelente trato con los clientes; varias reseñas lo mencionan por su nombre ({n}).",
    "Ha cubierto bajas de compañeros sin incidencias. Propuesta de complemento personal para {nc}.",
    "Rendimiento correcto. Pendiente revisar su solicitud de reducción de jornada por cuidado de hijo menor.",
]
for i, p in enumerate(personas, 1):
    media = round(sum(p["notas"]) / 5, 2)
    val = "Excelente" if media >= 4.4 else "Notable" if media >= 3.6 else "Adecuado" if media >= 2.8 else "Mejorable"
    ev = random.choice(evaluadores)
    com = random.choice(comentarios).format(n=p["nombre"], nc=p["completo"], ev=ev) + " (Evaluador: %s)" % ev
    fila = [i, p["completo"], p["doc"], p["naf"], p["nac"], p["ant"], p["puesto"], p["depto"], p["dir"], p["cp"],
            p["pueblo"], p["tel"], p["email"], p["iban"], p["salario"]] + p["notas"] + [media, val, com]
    for c, v in enumerate(fila, 1):
        x = ws.cell(row=fila0 + i, column=c, value=v); x.border = borde
        x.alignment = Alignment(vertical="top", wrap_text=(c in (2, 9, 23)))
        if i % 2 == 0:
            x.fill = claro
anchos = [5, 28, 13, 17, 12, 12, 22, 26, 34, 7, 16, 13, 32, 31, 12, 11, 11, 11, 11, 11, 8, 11, 70]
for c, w in enumerate(anchos, 1):
    ws.column_dimensions[get_column_letter(c)].width = w
ws.row_dimensions[fila0].height = 42
ws.freeze_panes = ws.cell(row=fila0 + 1, column=3)
r2 = wb.create_sheet("Resumen")
r2["A1"] = "Resumen por departamento"; r2["A1"].font = Font(bold=True, size=13)
r2["A3"], r2["B3"], r2["C3"] = "Departamento", "Personas", "Media"
for c in "ABC":
    r2[c + "3"].font = Font(bold=True); r2[c + "3"].fill = oro
deps = {}
for p in personas:
    deps.setdefault(p["depto"], []).append(sum(p["notas"]) / 5)
for k, (d, v) in enumerate(sorted(deps.items()), 4):
    r2["A%d" % k], r2["B%d" % k], r2["C%d" % k] = d, len(v), round(sum(v) / len(v), 2)
k += 2
r2["A%d" % k] = "Firmado: %s, Responsable de RR. HH. · Cuenta de cotización empresa %s" % (RRHH[0], EMP_CCC)
r2.column_dimensions["A"].width = 34; r2.column_dimensions["B"].width = 10; r2.column_dimensions["C"].width = 10
wb.save(os.path.join(OUT, "Evaluación del desempeño 2026 - Hoteles Volcán Azul.xlsx"))

# ------------------------------------------------------------------ 2. CSV: listado de plantilla
with open(os.path.join(OUT, "Listado de plantilla - altas y datos bancarios.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["Nombre", "Apellidos", "DNI/NIE", "NAF", "Fecha nacimiento", "Fecha alta", "Puesto", "Domicilio",
                "Código postal", "Municipio", "Teléfono", "Email", "IBAN", "Salario bruto anual"])
    for p in personas[:12]:
        w.writerow([p["nombre"], p["ap1"] + " " + p["ap2"], p["doc"], p["naf"], p["nac"], p["ant"], p["puesto"],
                    p["dir"], p["cp"], p["pueblo"], p["tel"], p["email"], p["iban"],
                    ("%.2f" % (p["salario"] * 14)).replace(".", ",")])

# ------------------------------------------------------------------ 3. Logo y sello inventados (imágenes)
def logo(ruta):
    im = Image.new("RGBA", (360, 360), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
    d.ellipse((10, 10, 350, 350), fill=(18, 82, 140, 255))
    d.polygon([(60, 260), (150, 120), (200, 190), (240, 140), (310, 260)], fill=(230, 120, 40, 255))
    d.polygon([(130, 150), (150, 120), (170, 150)], fill=(250, 220, 90, 255))
    for k in range(3):
        d.arc((70, 250 + k * 18, 290, 300 + k * 18), 200, 340, fill=(255, 255, 255, 255), width=8)
    im.save(ruta)

def sello(ruta):
    im = Image.new("RGBA", (420, 420), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
    azul = (40, 60, 170, 230)
    d.ellipse((10, 10, 410, 410), outline=azul, width=10); d.ellipse((60, 60, 360, 360), outline=azul, width=5)
    fnt = ImageFont.truetype(F + "DejaVuSans-Bold.ttf", 28)
    texto = "HOTELES VOLCÁN AZUL S.L. · RECURSOS HUMANOS · "
    for k, ch in enumerate(texto):
        ang = -math.pi / 2 + 2 * math.pi * k / len(texto)
        x, y = 210 + 172 * math.cos(ang), 210 + 172 * math.sin(ang)
        c = Image.new("RGBA", (40, 40), (0, 0, 0, 0)); ImageDraw.Draw(c).text((8, 2), ch, font=fnt, fill=azul)
        c = c.rotate(-math.degrees(ang) - 90, resample=Image.BICUBIC)
        im.alpha_composite(c, (int(x - 20), int(y - 20)))
    f2 = ImageFont.truetype(F + "DejaVuSans-Bold.ttf", 40)
    d.text((210, 190), CIF, font=f2, fill=azul, anchor="mm"); d.text((210, 240), "TÍAS", font=f2, fill=azul, anchor="mm")
    im.save(ruta)

def firma(ruta):
    im = Image.new("RGBA", (460, 160), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
    pts = [(20 + t * 4.2, 90 + 38 * math.sin(t / 6.0) * math.cos(t / 17.0)) for t in range(100)]
    d.line(pts, fill=(20, 30, 110, 255), width=5)
    d.line([(60, 120), (400, 60)], fill=(20, 30, 110, 255), width=4)
    im.save(ruta)

TMP = os.path.join(os.path.dirname(__file__), "_tmp"); os.makedirs(TMP, exist_ok=True)
logo(TMP + "/logo.png"); sello(TMP + "/sello.png"); firma(TMP + "/firma.png")

# ------------------------------------------------------------------ 4. PDF: carta de sanción + certificado
p = personas[2]
c = canvas.Canvas(os.path.join(OUT, "Comunicación de sanción y certificado de empresa.pdf"), pagesize=A4)
W, H = A4
def cabecera():
    c.drawImage(TMP + "/logo.png", 40, H - 105, 70, 70, mask="auto")
    c.setFont("DVB", 13); c.drawString(122, H - 60, EMPRESA.upper())
    c.setFont("DV", 8.5); c.drawString(122, H - 74, "CIF %s · %s" % (CIF, EMP_DIR))
    c.drawString(122, H - 86, "Tel. %s · %s · C.C.C. %s" % (EMP_TEL, RRHH[1], EMP_CCC))
    c.setStrokeColorRGB(0.83, 0.66, 0.33); c.setLineWidth(1); c.line(40, H - 115, W - 40, H - 115)
def parrafo(y, texto, ancho=95, tam=10.5, fuente="DV"):
    import textwrap
    c.setFont(fuente, tam)
    for linea in textwrap.wrap(texto, ancho):
        c.drawString(55, y, linea); y -= tam * 1.55
    return y - 6
cabecera()
c.setFont("DV", 10.5)
y = H - 150
for l in ["D./Dña. %s" % p["completo"], "%s" % p["dir"], "%s %s (Lanzarote)" % (p["cp"], p["pueblo"]),
          "DNI/NIE: %s" % p["doc"]]:
    c.drawString(330, y, l); y -= 15
y -= 12; c.drawString(55, y, "Puerto del Carmen, a 3 de noviembre de 2026"); y -= 30
c.setFont("DVB", 11); c.drawString(55, y, "ASUNTO: COMUNICACIÓN DE SANCIÓN POR FALTA LEVE"); y -= 26
y = parrafo(y, "Muy Sr./Sra. nuestro/a: Por medio de la presente, la dirección de %s le comunica que ha decidido "
               "imponerle una sanción de amonestación por escrito, por la comisión de una falta leve de puntualidad, "
               "al haberse producido tres retrasos injustificados en la entrada al trabajo los días 8, 15 y 22 de "
               "septiembre de 2026 en su puesto de %s del departamento de %s." % (EMPRESA, p["puesto"].lower(), p["depto"]))
y = parrafo(y, "Le recordamos que su número de afiliación a la Seguridad Social es %s y que, a efectos de cualquier "
               "comunicación, consta como domicilio el indicado en el encabezamiento y el teléfono %s." % (p["naf"], p["tel"]))
y = parrafo(y, "La presente sanción se comunica asimismo a la representación legal de las personas trabajadoras, en la "
               "persona de D. Rayco Perdomo Viera, delegado de personal.")
y = parrafo(y, "Rogamos firme el duplicado de este escrito a los solos efectos de acreditar su recepción.")
y -= 10; c.drawString(55, y, "Atentamente,"); y -= 10
c.drawImage(TMP + "/sello.png", 60, y - 125, 110, 110, mask="auto")
c.drawImage(TMP + "/firma.png", 185, y - 85, 150, 52, mask="auto")
c.setFont("DV", 10); c.drawString(185, y - 100, RRHH[0]); c.drawString(185, y - 113, "Responsable de Recursos Humanos")
c.drawString(380, y - 100, "Recibí: %s" % p["nombre"]); c.drawString(380, y - 113, "Fecha: ____/____/______")
c.setFont("DV", 7); c.setFillColorRGB(0.5, 0.5, 0.5)
c.drawString(40, 30, "Documento con datos ficticios generado para probar Seudónimo. Registro de salida nº 20260045123300871.")
c.setFillColorRGB(0, 0, 0)
c.showPage()
# página 2: certificado de empresa con tabla
q = personas[5]
cabecera()
c.setFont("DVB", 12); c.drawString(55, H - 150, "CERTIFICADO DE EMPRESA Y DE RETRIBUCIONES")
RRHH_DNI = dni()
y = parrafo(H - 180, "Dña. %s, con DNI %s, en calidad de Responsable de Recursos Humanos de %s, CERTIFICA:" % (RRHH[0], RRHH_DNI, EMPRESA))
filas = [("Persona trabajadora", q["completo"]), ("DNI / NIE", q["doc"]), ("N.º afiliación", q["naf"]),
         ("Fecha de nacimiento", q["nac"]), ("Fecha de antigüedad", q["ant"]), ("Puesto / Departamento", "%s · %s" % (q["puesto"], q["depto"])),
         ("Domicilio", "%s, %s %s" % (q["dir"], q["cp"], q["pueblo"])), ("Cuenta de abono de la nómina", q["iban"]),
         ("Salario bruto mensual", "%.2f €" % q["salario"]), ("Correo electrónico", q["email"])]
c.setFont("DV", 10)
for et, v in filas:
    c.setFillColorRGB(0.97, 0.94, 0.87); c.rect(55, y - 5, 175, 18, fill=1, stroke=0); c.setFillColorRGB(0, 0, 0)
    c.setFont("DVB", 9.5); c.drawString(60, y, et); c.setFont("DV", 10); c.drawString(240, y, v); y -= 21
y -= 8
y = parrafo(y, "Y para que conste a los efectos oportunos, a petición de la persona interesada, se expide el presente "
               "certificado en Puerto del Carmen, a 3 de noviembre de 2026. Código Seguro de Verificación: "
               "HVA7K-2Q9PL-M4R8T-ZX61C.")
c.drawImage(TMP + "/sello.png", 380, y - 120, 110, 110, mask="auto")
c.drawImage(TMP + "/firma.png", 200, y - 80, 150, 52, mask="auto")
c.setFont("DV", 7); c.setFillColorRGB(0.5, 0.5, 0.5)
c.drawString(40, 30, "Documento con datos ficticios generado para probar Seudónimo.")
c.save()

# ------------------------------------------------------------------ 5. Tres «capturas» de chat
def chat(ruta, titulo, sub, mensajes):
    Wd, Hd = 720, 1480
    im = Image.new("RGB", (Wd, Hd), (236, 229, 221)); d = ImageDraw.Draw(im)
    f_t = ImageFont.truetype(F + "DejaVuSans-Bold.ttf", 30); f_s = ImageFont.truetype(F + "DejaVuSans.ttf", 21)
    f_m = ImageFont.truetype(F + "DejaVuSans.ttf", 26); f_h = ImageFont.truetype(F + "DejaVuSans.ttf", 18)
    d.rectangle((0, 0, Wd, 60), fill=(7, 94, 84)); d.text((24, 16), "10:47", font=f_s, fill="white")
    d.rectangle((0, 60, Wd, 170), fill=(7, 94, 84))
    d.ellipse((24, 78, 100, 154), fill=(180, 190, 200)); d.text((62, 116), titulo[0], font=f_t, fill="white", anchor="mm")
    d.text((120, 84), titulo, font=f_t, fill="white"); d.text((120, 126), sub, font=f_s, fill=(210, 235, 230))
    y = 200
    import textwrap
    for quien, texto, hora in mensajes:
        lineas = []
        for parte in texto.split("\n"):
            lineas += textwrap.wrap(parte, 30) or [""]
        alto = 30 * len(lineas) + 46
        ancho = min(560, max(d.textlength(l, font=f_m) for l in lineas) + 110)
        if quien == "yo":
            x0, color = Wd - 24 - ancho, (220, 248, 198)
        else:
            x0, color = 24, (255, 255, 255)
        d.rounded_rectangle((x0, y, x0 + ancho, y + alto), 14, fill=color)
        yy = y + 12
        for l in lineas:
            d.text((x0 + 18, yy), l, font=f_m, fill=(20, 20, 20)); yy += 30
        d.text((x0 + ancho - 16, y + alto - 10), hora + (" ✓✓" if quien == "yo" else ""), font=f_h,
               fill=(120, 130, 120), anchor="rs")
        y += alto + 18
    d.rectangle((0, Hd - 90, Wd, Hd), fill=(240, 240, 240))
    d.rounded_rectangle((20, Hd - 76, Wd - 100, Hd - 16), 30, fill="white"); d.text((50, Hd - 58), "Mensaje", font=f_s, fill=(150, 150, 150))
    d.ellipse((Wd - 84, Hd - 80, Wd - 20, Hd - 16), fill=(0, 168, 132))
    im.save(ruta)

a, b, e = personas[0], personas[7], personas[10]
chat(os.path.join(OUT, "Captura chat 1 - datos para el alta.png"), a["completo"], "en línea", [
    ("ella", "Buenos días! Le paso los datos para el alta en la empresa", "10:31"),
    ("ella", "%s\nDNI %s\nNº Seguridad Social %s" % (a["completo"], a["doc"], a["naf"]), "10:32"),
    ("ella", "Vivo en %s, %s %s" % (a["dir"], a["cp"], a["pueblo"]), "10:32"),
    ("yo", "Perfecto, gracias. ¿Y la cuenta para la nómina?", "10:40"),
    ("ella", "%s\nestá a mi nombre" % a["iban"], "10:44"),
    ("yo", "Recibido. Le llamo luego al %s si falta algo" % a["tel"], "10:47"),
])
chat(os.path.join(OUT, "Captura chat 2 - baja médica.png"), b["nombre"] + " " + b["ap1"], "últ. vez hoy a las 9:12", [
    ("ella", "Hola, soy %s, la de %s del hotel" % (b["nombre"], b["depto"].lower()), "08:55"),
    ("ella", "Le aviso de que estoy de baja desde ayer, me dieron el parte en el centro de salud de Valterra", "08:56"),
    ("yo", "Lo siento mucho. Mándeme foto del parte y su DNI por favor", "09:02"),
    ("ella", "Mi DNI es %s. El parte se lo paso ahora, mi médico es el Dr. Armando Rodríguez Feo" % b["doc"], "09:05"),
    ("ella", "Y mi correo nuevo es %s por si me tiene que mandar algo" % b["email"], "09:07"),
    ("yo", "Anotado. Que se mejore 🙏", "09:12"),
])
chat(os.path.join(OUT, "Captura chat 3 - cliente empresa.png"), "Rayco (Volcán Azul)", "en línea", [
    ("ella", "Chema, te mando lo del despido de %s" % e["completo"], "17:20"),
    ("ella", "NIF empresa %s, CCC %s\nAntigüedad %s, salario %.2f brutos" % (CIF, EMP_CCC, e["ant"], e["salario"]), "17:21"),
    ("yo", "Vale. ¿Su domicilio sigue siendo %s?" % e["dir"], "17:30"),
    ("ella", "Sí, en %s. Su móvil %s" % (e["pueblo"], e["tel"]), "17:33"),
    ("ella", "Ah, y la transferencia del finiquito a %s" % e["iban"], "17:34"),
    ("yo", "Perfecto, mañana lo preparo", "17:40"),
])
import shutil; shutil.rmtree(TMP)
