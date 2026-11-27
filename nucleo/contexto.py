# -*- coding: utf-8 -*-
"""Riesgo de identificación por contexto (opcional: solo cuando el profesional lo pide).

Una copia sin nombres ni DNI puede seguir identificando a la persona por la suma de datos
indirectos: «jefa de almacén de 54 años, única de su categoría, en el centro de Arrecife, de
baja desde el 3 de marzo por un trastorno adaptativo» (considerando 26 RGPD: medios que
razonablemente pueden utilizarse). Este módulo:

1. Busca en el texto YA SEUDONIMIZADO esos datos indirectos: con reglas (edad, fechas, importes)
   y con el modelo local (puesto, lugar, salud, familia, nacionalidad, representación sindical,
   rasgos singulares). Lo que el modelo devuelve tiene que estar literalmente en el texto.
2. Calcula un nivel de riesgo por la combinación de categorías presentes.
3. Propone para cada dato una versión más general que conserve la utilidad jurídica
   («54 años» → «entre 50 y 59 años»; «3 de marzo de 2025» → «marzo de 2025»).

Nada se aplica solo: el profesional elige qué generalizar y la copia se rehace."""
import re

import motor
import proveedores

CATEGORIAS = {
    # clave: (nombre, peso en el riesgo, se propone marcada)
    "edad": ("Edad", 1, True),
    "fecha": ("Fecha de un hecho personal", 1, False),
    "importe": ("Salario o importe exacto", 1, False),
    "lugar": ("Municipio, barrio o lugar", 1, True),
    "puesto": ("Puesto, cargo o categoría concreta", 2, False),
    "centro": ("Centro de trabajo o empresa concreta", 1, False),
    "salud": ("Salud o diagnóstico", 2, False),
    "familia": ("Situación familiar", 1, True),
    "nacionalidad": ("Nacionalidad u origen", 1, True),
    "sindical": ("Representación o afiliación sindical", 2, False),
    "rasgo": ("Rasgo físico o personal singular", 2, True),
    "otro": ("Otro dato singular", 1, False),
}

PROMPT = """Eres un experto en protección de datos que revisa documentos jurídicos YA seudonimizados:
los nombres y números identificativos ya están sustituidos por marcadores como [PERSONA_001].

Busca los datos INDIRECTOS que siguen a la vista y que, combinados entre sí, permitirían a alguien
del entorno reconocer a la persona aunque no aparezca su nombre:
- edad: la edad de una persona («54 años»);
- fecha: fechas de hechos personales (nacimiento de un hijo, inicio de una baja, un accidente);
- importe: salario o importe exacto ligado a la persona;
- lugar: municipio, barrio, calle sin número, isla pequeña, lugar concreto;
- puesto: puesto, cargo o categoría concreta («jefa de almacén», «único electricista de la planta»);
- centro: centro de trabajo, sede o empresa concreta que no esté ya sustituida;
- salud: enfermedad, diagnóstico, discapacidad, tratamiento;
- familia: situación familiar («madre de trillizos», «viudo», «hija a cargo con discapacidad»);
- nacionalidad: nacionalidad, origen, idioma materno;
- sindical: afiliación sindical, ser delegado o miembro del comité;
- rasgo: rasgo físico o personal singular (tatuaje, estatura, apodo, aficiones conocidas);
- otro: cualquier otro dato singular.

NO incluyas: marcadores entre corchetes, organismos públicos, juzgados, leyes, convenios, importes de
la norma, ni datos que no se refieran a una persona concreta.

Para cada dato devuelve:
- "texto": el fragmento EXACTO tal como aparece (copiado letra a letra, lo más corto posible);
- "categoria": una de edad, fecha, importe, lugar, puesto, centro, salud, familia, nacionalidad, sindical, rasgo, otro;
- "generalizado": una versión más general que conserve lo jurídicamente útil y no identifique
  («Arrecife» → «un municipio de Lanzarote»; «jefa de almacén» → «mando intermedio»;
  «trastorno adaptativo» → «un proceso de salud mental»; «madre de trillizos» → «con hijos a cargo»).
La versión general tiene que poder sustituir al texto en la MISMA frase sin romper la gramática:
si el texto es «nacionalidad colombiana», la versión es «nacionalidad extranjera»; si va precedido de
«un» o «una», no repitas el artículo.
Responde solo en JSON."""

ESQUEMA = {
    "type": "object",
    "properties": {"datos": {"type": "array", "items": {
        "type": "object",
        "properties": {"texto": {"type": "string"},
                       "categoria": {"type": "string", "enum": list(CATEGORIAS)},
                       "generalizado": {"type": "string"}},
        "required": ["texto", "categoria", "generalizado"]}}},
    "required": ["datos"],
}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
RX_EDAD = re.compile(r"(?i)(?:\b(?:edad\s+de|de|con|tiene|ten[ií]a|cumpli[oó]|cuenta\s+con)\s+)(\d{2})\s+años(?:\s+de\s+edad)?\b"
                     r"|\b(\d{2})\s+años\s+de\s+edad\b")
RX_NO_EDAD = re.compile(r"(?i)(antig[uü]edad|contrato|plazo|duraci[oó]n|hace|durante|despu[eé]s|antes|prestaci[oó]n|cotiz)\W+(?:\w+\W+){0,3}$")
RX_FECHA_NUM = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
RX_FECHA_LARGA = re.compile(r"(?i)\b(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+(?:de|del)\s+(\d{4})\b")
RX_IMPORTE = re.compile(r"\b(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s?(?:€|euros|EUR)(?!\w)")


def _decada(n):
    a = (n // 10) * 10
    return "entre %d y %d años" % (a, a + 9)


def _importe(texto):
    entero = int(re.sub(r"\D", "", texto.split(",")[0]) or 0)
    paso = 1000 if entero >= 20000 else 100 if entero >= 1000 else 10
    a = (entero // paso) * paso
    fmt = lambda x: "{:,}".format(x).replace(",", ".")
    return "entre %s y %s €" % (fmt(a), fmt(a + paso))


def por_reglas(texto):
    res = []
    for m in RX_EDAD.finditer(texto):
        n = int(m.group(1) or m.group(2))
        if not 14 <= n <= 99 or RX_NO_EDAD.search(texto[max(0, m.start() - 60):m.start()]) or \
                re.search(r"(?i)entre\s+\d+\s+y\s*$", texto[max(0, m.start() - 20):m.start() + m.group(0).find(str(n))]):
            continue        # «entre 50 y 59 años» ya es una edad generalizada
        frag = re.search(r"\d{2}\s+años(?:\s+de\s+edad)?", m.group(0)).group(0)
        res.append({"texto": frag, "categoria": "edad", "generalizado": _decada(n), "origen": "regla"})
    for m in RX_FECHA_NUM.finditer(texto):
        d, mes, a = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= d <= 31 and 1 <= mes <= 12:
            res.append({"texto": m.group(0), "categoria": "fecha", "generalizado": "%s de %s" % (MESES[mes - 1], a), "origen": "regla"})
    for m in RX_FECHA_LARGA.finditer(texto):
        res.append({"texto": m.group(0), "categoria": "fecha", "generalizado": "%s de %s" % (m.group(2).lower(), m.group(3)), "origen": "regla"})
    for m in RX_IMPORTE.finditer(texto):
        res.append({"texto": m.group(0), "categoria": "importe", "generalizado": _importe(m.group(0)), "origen": "regla"})
    return res


def por_modelo(texto, modelo=None, progreso=None, cancelado=None):
    res = []
    trozos = motor.fragmentar(texto)
    for i, frag in enumerate(trozos, 1):
        if cancelado and cancelado():
            break
        if progreso:
            progreso(i, len(trozos))
        mensajes = [{"role": "system", "content": PROMPT},
                    {"role": "user", "content": 'TEXTO:\n"""\n' + frag + '\n"""'}]
        try:
            datos = proveedores.actual().estructurado(modelo or motor.MODELO, mensajes, ESQUEMA)
        except Exception:  # noqa  (un fragmento que falla no tumba el análisis)
            continue
        for d in (datos.get("datos", []) if isinstance(datos, dict) else []):
            t = str(d.get("texto", "")).strip().strip(" ,.;:()\"'«»\n\t")
            cat = d.get("categoria") if d.get("categoria") in CATEGORIAS else "otro"
            gen = str(d.get("generalizado", "")).strip()
            if len(t) < 3 or t not in frag or motor.MARCADOR.search(t) or "[" in t or "]" in t:
                continue          # inventado, reescrito o encima de un marcador: fuera
            if motor.PUBLICO.search(t) or not gen or motor.clave(gen) == motor.clave(t):
                continue
            res.append({"texto": t, "categoria": cat, "generalizado": gen[:120], "origen": "modelo"})
    return res


def analizar(texto, modelo=None, progreso=None, cancelado=None, aplicadas=()):
    """{"nivel", "puntos", "categorias", "explicacion", "hallazgos": [...]}.
    «aplicadas»: generalizaciones ya puestas en este proyecto (se muestran marcadas)."""
    hall = por_reglas(texto) + por_modelo(texto, modelo, progreso, cancelado)
    puestos = [motor.clave(a.get("reemplazo", "")) for a in aplicadas if a.get("reemplazo")]
    vistos, unicos = {}, []
    # primero lo de las reglas y lo más corto: «12/02/2026» antes que «desde el 12/02/2026»
    for h in sorted(hall, key=lambda x: (x["origen"] != "regla", len(x["texto"]))):
        k = motor.clave(h["texto"])
        if any(p and (p in k or k in p) for p in puestos):
            continue          # es (o contiene) una generalización ya aplicada: no es un dato nuevo
        if k in vistos or any(v in k for v, cat in vistos.items() if cat == h["categoria"]):
            continue          # el mismo dato, o uno de la misma clase que ya lo contiene
        vistos[k] = h["categoria"]
        h["generalizado"] = _ajustar(texto, h["texto"], h["generalizado"])
        unicos.append(h)
    ya = {motor.clave(a["texto"]): a for a in aplicadas}
    for h in unicos:
        h["veces"] = texto.count(h["texto"])
        h["nombre_categoria"] = CATEGORIAS[h["categoria"]][0]
        h["recomendado"] = CATEGORIAS[h["categoria"]][2]
        if motor.clave(h["texto"]) in ya:
            h["aplicada"] = True
            h["generalizado"] = ya[motor.clave(h["texto"])]["reemplazo"]
    cats = sorted({h["categoria"] for h in unicos})
    puntos = sum(CATEGORIAS[c][1] for c in cats)
    nivel = "bajo" if puntos <= 2 else "medio" if puntos <= 4 else "alto"
    nombres = [CATEGORIAS[c][0].lower() for c in cats]
    if not cats:
        expl = "No se han encontrado datos indirectos que, combinados, permitan reconocer a la persona."
    elif nivel == "bajo":
        expl = "Quedan pocos datos indirectos (%s). Por sí solos difícilmente identifican a nadie." % ", ".join(nombres)
    else:
        expl = ("Quedan a la vista %s. Juntos, alguien del entorno de la persona (compañeros, vecinos, la empresa) "
                "podría reconocerla aunque no aparezca su nombre." % _lista(nombres))
    return {"nivel": nivel, "puntos": puntos, "categorias": cats, "explicacion": expl,
            "hallazgos": sorted(unicos, key=lambda h: (list(CATEGORIAS).index(h["categoria"]), h["texto"].lower()))}


_ARTICULOS = ("un", "una", "el", "la", "los", "las", "unos", "unas")


def _ajustar(texto, dato, general):
    """Que la sustitución no rompa la frase: si el dato ya va precedido de artículo («por un
    trastorno…»), la versión general no lo repite («por un un proceso…»)."""
    i = texto.find(dato)
    if i <= 0:
        return general
    previa = texto[:i].rstrip().rsplit(None, 1)[-1].lower() if texto[:i].strip() else ""
    palabras = general.split(None, 1)
    if previa in _ARTICULOS and len(palabras) == 2 and palabras[0].lower() in _ARTICULOS:
        return palabras[1]
    return general


def _lista(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


def como_mapa(generalizaciones):
    """Entradas extra para el mapa de sustitución: el texto se cambia por su versión general."""
    return [{"texto": g["texto"], "tipo": "GENERALIZACION", "marcador": g["reemplazo"]}
            for g in generalizaciones if g.get("texto") and g.get("reemplazo")]
