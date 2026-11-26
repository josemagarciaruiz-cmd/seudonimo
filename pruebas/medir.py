# -*- coding: utf-8 -*-
"""Ejecuta el controlador multipasada sobre una carpeta, con el modelo real, y guarda lo
necesario para evaluar (SOLO para el corpus sintético: el archivo corpus_resultado.json
contiene los datos detectados).

Uso:  python pruebas/medir.py <estandar|intensivo> <carpeta> <salida>   (SEUDONIMO_MODELO para otro modelo)"""
import glob
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nucleo"))
os.environ.setdefault("SEUDONIMO_DATOS", "/tmp/seudonimo-medicion")
import rutas  # noqa: E402

rutas.preparar()
import multipasada  # noqa: E402
import registro  # noqa: E402

perfil, carpeta, salida = sys.argv[1], sys.argv[2], sys.argv[3]
docs = [{"id": i, "ruta": p, "rel": os.path.relpath(p, carpeta), "nombre": os.path.basename(p)}
        for i, p in enumerate(sorted(glob.glob(carpeta + "/**/*", recursive=True)))
        if os.path.isfile(p) and not p.endswith("etiquetas.json")]
reg = registro.Registro(0)
lote = multipasada.TrabajoLote("m", docs, reg, perfil=perfil, modelo=os.environ.get("SEUDONIMO_MODELO", "gemma4:12b"), destino=salida)


def vigilar():
    ultimo = ""
    while lote.estado in ("pendiente", "procesando"):
        if lote.mensaje != ultimo:
            print(time.strftime("%H:%M:%S"), round(lote.progreso, 2), lote.mensaje, flush=True)
            ultimo = lote.mensaje
        time.sleep(5)


threading.Thread(target=vigilar, daemon=True).start()
lote.ejecutar()
print("FIN", lote.estado, json.dumps(lote.informe["recuento"]), "duración", lote.informe["duracion_s"], flush=True)
res = {"perfil": perfil, "modelo": lote.ajustes.get("modelo"), "duracion_s": lote.informe["duracion_s"], "documentos": {},
       "formas": [{"texto": e["texto"], "tipo": e["tipo"], "marcador": e["marcador"]} for e in reg.mapa()]}
for d in lote.docs:
    res["documentos"][d.doc["nombre"]] = {"estado": d.estado, "salida": d.doc.get("rel_salida"), "motivos": d.motivos,
                                          "pasadas": d.pasadas, "tiempos": d.crono.t}
    print("DOC", d.doc["nombre"], d.estado, d.motivos, json.dumps(d.crono.t), flush=True)
    for p in d.pasadas:
        print("    ", json.dumps(p, ensure_ascii=False), flush=True)
with open(os.path.join(salida, "corpus_resultado.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
