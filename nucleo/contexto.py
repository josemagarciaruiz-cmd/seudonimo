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
    "unico": ("Ser la única o la más… del entorno", 3, True),
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
- unico: ser la única persona de su entorno con algo («la única mujer de la plantilla», «el más
  antiguo del centro», «el único que habla alemán»): es lo que más identifica;
- otro: cualquier otro dato singular.

NO incluyas: marcadores entre corchetes, organismos públicos, juzgados, leyes, convenios, importes de
la norma, ni datos que no se refieran a una persona concreta.

Para cada dato devuelve:
- "texto": el fragmento EXACTO tal como aparece (copiado letra a letra, lo más corto posible);
- "categoria": una de edad, fecha, importe, lugar, puesto, centro, salud, familia, nacionalidad, sindical, rasgo, unico, otro;
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


# Unicidad: «la única mujer con categoría de jefa de almacén en la isla», «el más antiguo de la
# plantilla». Por regla, porque es lo que más identifica y el modelo a veces lo deja pasar.
_ENTORNO = (r"isla|plantilla|empresa|centro(?:\s+de\s+trabajo)?|grupo(?:\s+empresarial)?|localidad|municipio|"
            r"pueblo|zona|comarca|provincia|sector|departamento|secci[oó]n|turno|oficina|obra|tienda|hotel|"
            r"almac[eé]n|f[aá]brica|planta|equipo|sede|delegaci[oó]n|comit[eé]|categor[ií]a")
RX_ENTORNO = re.compile(r"(?i)\s*,?\s+(?:en|dentro\s+de(?:l)?|de|del)\s+(?:(?:la|el|toda\s+la|todo\s+el|su|este|esta|ese|esa)\s+)?"
                        r"(?:" + _ENTORNO + r")\b")
RX_ENTORNO_DE = re.compile(r"(?i)\s+de\s+(?:" + _ENTORNO + r")\b")     # «de almacén» no es un entorno
RX_UNICO = re.compile(r"(?i)\b(?:(el|la|los|las)\s+)?(únic[oa]s?)\s+([^.;:()\n\[]{2,160})")
RX_EXTREMO = re.compile(r"(?i)\b(el|la)\s+(?:m[aá]s\s+(antigu[oa]|veteran[oa]|joven|mayor)|de\s+(mayor|menor)\s+(antig[uü]edad|edad))"
                        r"(?=" + RX_ENTORNO.pattern[4:] + r")")
_CORTE = re.compile(r"(?i)\s+(?:que|y|pero|aunque|porque|ya|lo\s+que|por\s+lo\s+que)\s+|,\s+(?!(?:en|dentro)\b)")
_EXTREMOS = {"antiguo": "una de las personas con más antigüedad", "veterano": "una de las personas con más antigüedad",
             "joven": "una de las personas más jóvenes", "mayor": "una de las personas de más edad",
             "antiguedad": "una de las personas con más antigüedad", "edad": "una de las personas de más edad"}


def _sin_entorno(frase):
    """Quita «en la isla», «dentro del grupo empresarial», «de la plantilla»… (pero no «de almacén»)."""
    previa = None
    while previa != frase:
        previa = frase
        m = None
        for m in RX_ENTORNO.finditer(frase):
            pass
        if m and m.end() >= len(frase.rstrip()) - 1 and not RX_ENTORNO_DE.fullmatch(m.group(0)):
            frase = frase[:m.start()].rstrip(" ,")
    return frase


_COPULA = re.compile(r"(?i)\b(?:es|era|fue|ser[aá]|ser[ií]a|siendo|ser|sea|resulta|result[oó]|queda|qued[oó]|sigue\s+siendo|como|soy|eres|somos|son|eran|fueron)\s+$")
_PERSONA = re.compile(r"(?i)^(?:mujer|hombre|persona|chic[oa]|trabajador[a]?|emplead[oa]|delegad[oa]|miembro|representante|"
                      r"t[eé]cnic[oa]|oficial|encargad[oa]|responsable|jef[ea]|director(?:a|es|as)?|trabajador(?:es|as)|madre|padre|extranjer[oa]|"
                      r"que)s?\b")
_NO_PERSONA = re.compile(r"(?i)^(?:prueba|dato|documento|vez|forma|manera|motivo|causa|opci[oó]n|soluci[oó]n|excepci[oó]n|"
                         r"diferencia|cosa|d[ií]a|fecha|requisito|posibilidad|alternativa|v[ií]a|raz[oó]n|objeto|finalidad|"
                         r"cuesti[oó]n|pretensi[oó]n|cantidad|importe|concepto|medio|recurso|acci[oó]n)s?\b")
_PREP_FINAL = re.compile(r"(?i)\s+(?:de|del|en|a|al|con|para|por|y)$")


def _sin_unicidad(frase):
    """Quita «único/única» de una versión general propuesta por el modelo y el entorno que la acota."""
    m = re.match(r"(?i)\s*(?:(el|la|los|las)\s+)?([uú]nic[oa]s?)\s+(.*)", frase)
    if not m:
        return re.sub(r"(?i)\b[uú]nic[oa]s?\s+", "", frase).strip()
    masc = motor.clave(m.group(2)).startswith("unico")
    plural = m.group(2).lower().endswith("s")
    art = ("unos" if masc else "unas") if plural else ("un" if masc else "una")
    return art + " " + _sin_entorno(m.group(3).strip())


def _unicidad(texto):
    res = []
    for m in RX_UNICO.finditer(texto):
        antes = texto[max(0, m.start() - 25):m.start()]
        if re.search(r"(?i)\blo\s*$", antes):
            continue                                  # «lo único que…» no habla de una persona
        resto = m.group(3)
        if not resto.lower().startswith("que "):
            resto = _CORTE.split(resto, maxsplit=1)[0]
        resto = _PREP_FINAL.sub("", resto.rstrip(" ,"))
        palabras = resto.split()
        if not palabras or len(palabras) > 18 or _NO_PERSONA.match(resto):
            continue
        if not (_COPULA.search(antes) or _PERSONA.match(resto)):
            continue                                  # «La única prueba aportada…»: no es una persona
        frag = texto[m.start():m.start(3) + len(resto)]
        nucleo = _sin_entorno(resto)
        if not nucleo.strip():
            continue
        masc = motor.clave(m.group(2)).startswith("unico")
        plural = m.group(2).lower().endswith("s")
        if nucleo.lower().startswith("que "):
            gen = ("personas " if plural else "alguien ") + nucleo
        else:
            gen = (("unos" if masc else "unas") if plural else ("un" if masc else "una")) + " " + nucleo
        res.append({"texto": frag, "categoria": "unico", "generalizado": gen, "origen": "regla"})
    for m in RX_EXTREMO.finditer(texto):
        clave = motor.clave(m.group(2) or m.group(4) or "")
        clave = re.sub(r"[oa]$", "o", clave) if clave not in ("antiguedad", "edad") else clave
        gen = _EXTREMOS.get(clave)
        e = RX_ENTORNO.match(texto, m.end())
        if gen and e:
            res.append({"texto": texto[m.start():e.end()], "categoria": "unico", "generalizado": gen, "origen": "regla"})
    return res


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
    return res + _unicidad(texto)


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
            if cat == "unico" and re.search(r"(?i)\b[uú]nic[oa]s?\b", gen):
                gen = _sin_unicidad(gen)      # «única persona… en la zona» sigue siendo única
            res.append({"texto": t, "categoria": cat, "generalizado": gen[:120], "origen": "modelo"})
    return res


def analizar(texto, modelo=None, progreso=None, cancelado=None, aplicadas=()):
    """{"nivel", "puntos", "categorias", "explicacion", "hallazgos": [...]}.
    «aplicadas»: generalizaciones ya puestas en este proyecto (se muestran marcadas)."""
    hall = por_reglas(texto) + por_modelo(texto, modelo, progreso, cancelado)
    puestos = [motor.clave(a.get("reemplazo", "")) for a in aplicadas if a.get("reemplazo")]
    vistos, unicos = {}, []

    def ya_generalizado(k):
        # el dato es (parte de) una generalización ya aplicada, o solo le añade artículos y preposiciones
        for p in puestos:
            if p and (k in p or (p in k and len(re.sub(r"\b(?:de|del|en|el|la|los|las|un|una|con|por|a)\b", "",
                                                     k.replace(p, "")).strip(" ,.")) < 3)):
                return True
        return False

    # primero lo de las reglas y lo más corto: «12/02/2026» antes que «desde el 12/02/2026»
    for h in sorted(hall, key=lambda x: (x["origen"] != "regla", len(x["texto"]))):
        k = motor.clave(h["texto"])
        if ya_generalizado(k):
            continue          # es una generalización ya aplicada: no es un dato nuevo
        if k in vistos or any(v in k or k in v for v, cat in vistos.items() if cat == h["categoria"]):
            continue          # el mismo dato, o uno de la misma clase que lo contiene o está dentro
        vistos[k] = h["categoria"]
        h["generalizado"] = _ajustar(texto, h["texto"], h["generalizado"])
        unicos.append(h)
    for h in unicos:
        if h["categoria"] == "unico":
            # «la única persona de 54 años»: la versión general lleva también generalizado lo de dentro
            for o in sorted(unicos, key=lambda x: -len(x["texto"])):
                if o is not h and o["texto"] in h["texto"] and o["texto"] in h["generalizado"]:
                    h["generalizado"] = h["generalizado"].replace(o["texto"], o["generalizado"])
    ya = {motor.clave(a["texto"]): a for a in aplicadas}
    for h in unicos:
        h["veces"] = texto.count(h["texto"])
        h["nombre_categoria"] = CATEGORIAS[h["categoria"]][0]
        orig = _al_original(h["texto"], aplicadas)
        if orig != h["texto"]:
            h["original"] = orig      # lo que hay en el documento original (para el mapa de sustitución)
        h["recomendado"] = CATEGORIAS[h["categoria"]][2]
        kk = motor.clave(h.get("original", h["texto"]))
        if kk in ya:
            h["aplicada"] = True
            h["generalizado"] = ya[kk]["reemplazo"]
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


def _al_original(frag, aplicadas):
    """La copia ya lleva generalizaciones («mando intermedio»); el mapa se aplica sobre el original
    («jefa de almacén»), así que un dato que las contenga se guarda con el texto original."""
    for a in sorted(aplicadas, key=lambda x: -len(x.get("reemplazo") or "")):
        r, t = a.get("reemplazo") or "", a.get("texto") or ""
        if r and t and r in frag:
            frag = frag.replace(r, t)
    return frag


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
