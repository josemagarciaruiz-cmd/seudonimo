# -*- coding: utf-8 -*-
"""Métricas de seudonimización sobre el corpus sintético etiquetado.

Uso:  python pruebas/evaluar.py <carpeta del corpus> <carpeta del lote> [--json salida.json]

La carpeta del lote es la que deja pruebas/medir.py: «Aprobados», «Para revisar» y
«corpus_resultado.json» (correspondencia de archivos, estados y formas del registro; solo se
genera para el corpus sintético).

Mide:
- recall crítico por categoría = datos sensibles que ya no aparecen / datos sensibles etiquetados
  (búsqueda con las mismas variantes que usa el motor: tildes, separadores, orden de apellidos);
- restos parciales y cuasi-identificadores (se informan aparte);
- conservación = datos que debían quedarse y siguen en la copia;
- precisión = formas detectadas que corresponden a un dato etiquetado / formas detectadas;
- acierto de estado = documentos cuyo estado final coincide con el esperado."""
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nucleo"))
from lxml import etree  # noqa: E402

import formatos  # noqa: E402
import motor  # noqa: E402


def texto_completo(ruta):
    """Todo el texto recuperable del archivo: el visible, el OCR y, en Office, cada parte interna."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext in formatos.ZIP:
        partes = []
        with zipfile.ZipFile(ruta) as z:
            for n in z.namelist():
                if n.endswith((".xml", ".rels")):
                    try:
                        root = etree.fromstring(z.read(n), formatos.PARSER)
                        partes.append(" ".join(root.itertext()))
                        partes.append(" ".join(v for el in root.iter() for v in el.attrib.values()))
                    except Exception:
                        partes.append(z.read(n).decode("utf-8", "ignore"))
        return "\n".join(partes)
    return formatos.extraer_texto(ruta, ext, comprobar=False, verificar=True)


def _norm(s):
    return re.sub(r"\s+", " ", motor.clave(s))


def evaluar(corpus, lote):
    et = json.load(open(os.path.join(corpus, "etiquetas.json"), encoding="utf-8"))
    res = json.load(open(os.path.join(lote, "corpus_resultado.json"), encoding="utf-8"))
    cat, docs = {}, []
    conservar_ok = conservar_tot = 0
    for nombre, e in et.items():
        r = res["documentos"].get(nombre)
        fila = {"archivo": nombre, "esperado": e["esperado"], "estado": r["estado"] if r else "sin_resultado",
                "fugas": [], "parciales": [], "cuasi": [], "perdidos": []}
        if not r or not r.get("salida"):
            fila["error"] = "sin copia exportada"
            for s in e["sensibles"]:
                c = cat.setdefault(s["tipo"], [0, 0]); c[1] += 1
            docs.append(fila)
            continue
        salida = os.path.join(lote, r["salida"])
        txt = texto_completo(salida)
        # el nombre del archivo exportado también cuenta
        txt_nombre = os.path.basename(salida)
        for s in e["sensibles"]:
            c = cat.setdefault(s["tipo"], [0, 0]); c[1] += 1
            rx = motor.patron(s["texto"], s["tipo"])
            if rx.search(txt) or rx.search(txt_nombre):
                fila["fugas"].append(s)
            else:
                c[0] += 1
        for k in ("parciales", "cuasi"):
            for s in e.get(k, []):
                if motor.patron(s["texto"], s["tipo"]).search(txt):
                    fila[k].append(s["texto"])
        plano = _norm(txt)
        for x in e.get("conservar", []):
            conservar_tot += 1
            if _norm(x) in plano:
                conservar_ok += 1
            else:
                fila["perdidos"].append(x)
        docs.append(fila)

    etiquetados = set()
    for e in et.values():
        for k in ("sensibles", "parciales", "cuasi", "oculto"):
            for s in e.get(k, []):
                etiquetados.add(motor.clave_dato(s["texto"]))
    formas = res.get("formas", [])
    correctas, dudosas = 0, []
    for f in formas:
        k = motor.clave_dato(f["texto"])
        if k in etiquetados or any(k in x or x in k for x in etiquetados if len(x) >= 4 and len(k) >= 4):
            correctas += 1
        else:
            dudosas.append(f)
    total_s = sum(v[1] for v in cat.values())
    ok_s = sum(v[0] for v in cat.values())
    return {
        "recall_critico": round(ok_s / total_s, 4) if total_s else None,
        "fugas_criticas": total_s - ok_s,
        "por_categoria": {k: {"ok": v[0], "total": v[1], "recall": round(v[0] / v[1], 3)} for k, v in sorted(cat.items())},
        "conservacion": round(conservar_ok / conservar_tot, 3) if conservar_tot else None,
        "precision_detecciones": round(correctas / len(formas), 3) if formas else None,
        "detecciones": len(formas), "dudosas": dudosas,
        "estado_correcto": sum(1 for d in docs if d["estado"] == d["esperado"]), "documentos": len(docs),
        "detalle": docs, "duracion_s": res.get("duracion_s"), "perfil": res.get("perfil"), "modelo": res.get("modelo"),
    }


def imprimir(m):
    print("Perfil %s · modelo %s · %s s" % (m["perfil"], m["modelo"], m["duracion_s"]))
    print("RECALL CRÍTICO: %.1f %% (%d fugas)" % (100 * m["recall_critico"], m["fugas_criticas"]))
    for k, v in m["por_categoria"].items():
        print("  %-14s %3d/%3d  %.1f %%" % (k, v["ok"], v["total"], 100 * v["recall"]))
    print("Conservación de datos necesarios: %.1f %%" % (100 * (m["conservacion"] or 0)))
    print("Precisión de las detecciones: %.1f %% de %d" % (100 * (m["precision_detecciones"] or 0), m["detecciones"]))
    print("Estado final correcto: %d de %d" % (m["estado_correcto"], m["documentos"]))
    for d in m["detalle"]:
        marca = "OK " if d["estado"] == d["esperado"] else "!! "
        print("%s%-58s %-14s fugas=%d parciales=%d cuasi=%d perdidos=%d" % (
            marca, d["archivo"][:58], d["estado"], len(d["fugas"]), len(d["parciales"]), len(d["cuasi"]), len(d["perdidos"])))
        for s in d["fugas"]:
            print("      FUGA %s: %s" % (s["tipo"], s["texto"]))
        for x in d["perdidos"]:
            print("      PERDIDO: %s" % x)
    if m["dudosas"]:
        print("Detecciones sin etiqueta (revisar si son falsos positivos):")
        for f in m["dudosas"][:40]:
            print("   %s · %s" % (f["tipo"], f["texto"]))


if __name__ == "__main__":
    m = evaluar(sys.argv[1], sys.argv[2])
    imprimir(m)
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
