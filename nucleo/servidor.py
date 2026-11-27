# -*- coding: utf-8 -*-
"""Seudónimo · servicio local (sidecar) que usa la ventana de escritorio.

Seguridad:
- Escucha solo en 127.0.0.1 (nunca en la red) y en un puerto libre elegido al arrancar.
- Cada petición a /api lleva un token efímero (X-Seudonimo-Token), generado en cada arranque.
- Se valida el Host (contra DNS rebinding) y el Origin (solo la ventana de la aplicación).
- El modelo solo ve archivos que el usuario ha añadido con el diálogo del sistema.

Uso: python servidor.py [--puerto 0] [--navegador]
Imprime «SEUDONIMO_LISTO <puerto>» cuando está preparado (lo lee la ventana de Tauri)."""
import argparse
import json
import os
import re
import secrets
import shutil
import socket
import sys
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rutas  # noqa: E402

rutas.preparar()
if sys.stdout is None or sys.stderr is None:   # Windows sin consola
    _log = open(rutas.REGISTRO, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log

from flask import Flask, Response, abort, jsonify, request, send_from_directory  # noqa: E402

import actualizar  # noqa: E402
import almacen as almacen_mod  # noqa: E402
import asistente  # noqa: E402
import cifrado  # noqa: E402
import contexto  # noqa: E402
import formatos  # noqa: E402
import herramientas  # noqa: E402
import instalacion  # noqa: E402
import motor  # noqa: E402
import multipasada  # noqa: E402
import ocr  # noqa: E402
import proveedores  # noqa: E402
import registro as registro_mod  # noqa: E402
import trabajos  # noqa: E402
import voz  # noqa: E402
from version import VERSION  # noqa: E402

INTERFAZ = os.environ.get("SEUDONIMO_INTERFAZ") or os.path.join(os.path.dirname(rutas.APP), "interfaz")
TOKEN = os.environ.get("SEUDONIMO_TOKEN") or secrets.token_urlsafe(32)
ORIGENES = {"tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"}

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024    # el dictado envía hasta 3 minutos de audio (unos 6 MB)
ALM = almacen_mod.Almacen()
GESTOR = trabajos.Gestor(ALM)
PUERTO = None


# ---------------------------------------------------------------- seguridad

@app.before_request
def _proteger():
    host = (request.host or "").split(":")[0]
    if host not in ("127.0.0.1", "localhost"):
        abort(403)
    if request.path.startswith("/api/"):
        origen = request.headers.get("Origin")
        if origen and origen not in ORIGENES and origen != "http://%s" % request.host:
            abort(403)
        if request.method == "OPTIONS":
            return None    # comprobación previa CORS de la ventana: no lleva el token (lo lleva la petición real)
        if not secrets.compare_digest(request.headers.get("X-Seudonimo-Token", ""), TOKEN):
            abort(401)


@app.after_request
def _cabeceras(r):
    origen = request.headers.get("Origin")
    if origen in ORIGENES:
        r.headers["Access-Control-Allow-Origin"] = origen
        r.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Seudonimo-Token"
        r.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        r.headers["Access-Control-Max-Age"] = "600"
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Cache-Control"] = "no-store"
    return r


@app.route("/api/<path:_x>", methods=["OPTIONS"])
def _preflight(_x):
    return ("", 204)


def _json():
    return request.get_json(force=True, silent=True) or {}


def _proyecto(pid):
    p = ALM.proyecto(pid)
    if not p:
        abort(404)
    return p


# ---------------------------------------------------------------- interfaz en modo navegador

@app.get("/")
def inicio():
    html = open(os.path.join(INTERFAZ, "index.html"), encoding="utf-8").read()
    # en modo navegador el token va en la propia página (servida solo a 127.0.0.1)
    html = html.replace("<head>", "<head><script>window.SEUDONIMO_CONEXION={token:%s}</script>" % json.dumps(TOKEN), 1)
    return Response(html, mimetype="text/html")


@app.get("/<path:nombre>")
def estaticos(nombre):
    if nombre.startswith("api/"):
        abort(404)
    return send_from_directory(INTERFAZ, nombre)


# ---------------------------------------------------------------- estado y modelos

@app.get("/api/salud")
def salud():
    prov = proveedores.actual()
    return jsonify(app=rutas.NOMBRE, version=VERSION, ollama=prov.disponible(), ollama_version=prov.version(),
                   instalado=instalacion.instalado(), ocr=ocr.DISPONIBLE, motor_ocr=ocr.MOTOR,
                   formatos=sorted(formatos.ADMITIDOS), clave=cifrado.donde_se_guarda_la_clave(),
                   sistema="Windows" if rutas.ES_WINDOWS else ("Mac" if rutas.ES_MAC else "Linux"),
                   salidas=rutas.SALIDAS, modelo_defecto=ALM.ajuste("modelo_defecto", motor.MODELO),
                   perfiles=multipasada.PERFILES)


@app.get("/api/modelos")
def modelos():
    prov = proveedores.actual()
    instalados, error = [], None
    try:
        instalados = prov.listar()
    except proveedores.ErrorProveedor as e:
        error = str(e)
    nombres = {m["nombre"] for m in instalados}
    return jsonify(instalados=instalados, cargados=prov.cargados() if not error else [], error=error,
                   catalogo=[dict(c, instalado=c["nombre"] in nombres) for c in proveedores.CATALOGO],
                   descargas=instalacion.DESCARGAS, defecto=ALM.ajuste("modelo_defecto", motor.MODELO),
                   espacio_libre_gb=round(instalacion.espacio_libre_gb(), 1))


@app.get("/api/modelos/ficha")
def ficha_modelo():
    nombre = request.args.get("nombre", "")
    try:
        f = proveedores.actual().ficha(nombre)
    except Exception as e:  # noqa
        return jsonify(error=str(e)[:200]), 400
    return jsonify(nombre=nombre, capacidades=f.get("capabilities"), detalles=f.get("details"),
                   licencia=(f.get("license") or "")[:20000], parametros=f.get("parameters"))


@app.post("/api/modelos/descargar")
def descargar_modelo():
    d = _json()
    nombre = (d.get("nombre") or "").strip()
    if not nombre or len(nombre) > 120 or any(c in nombre for c in " \n\t;&|`$"):
        return jsonify(error="Nombre de modelo no válido."), 400
    gb = next((c.get("gb") for c in proveedores.CATALOGO if c["nombre"] == nombre), None)
    instalacion.descargar_modelo(nombre, gb)
    return jsonify(instalacion.DESCARGAS.get(nombre))


@app.delete("/api/modelos")
def borrar_modelo():
    try:
        proveedores.actual().borrar(_json().get("nombre", ""))
    except Exception as e:  # noqa
        return jsonify(error=str(e)[:200]), 400
    return jsonify(ok=True)


@app.post("/api/modelos/defecto")
def modelo_defecto():
    ALM.poner_ajuste("modelo_defecto", _json().get("nombre") or motor.MODELO)
    return jsonify(ok=True)


# ---------------------------------------------------------------- dictado por voz

@app.get("/api/voz")
def voz_estado():
    return jsonify(voz.estado(ALM.ajuste("voz_modelo", "small")))


@app.post("/api/voz/descargar")
def voz_descargar():
    try:
        voz.descargar(_json().get("nombre") or "small")
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(voz.DESCARGA)


@app.post("/api/voz/modelo")
def voz_modelo():
    nombre = _json().get("nombre")
    if not any(m["nombre"] == nombre for m in voz.MODELOS):
        return jsonify(error="Modelo de voz desconocido."), 400
    ALM.poner_ajuste("voz_modelo", nombre)
    return jsonify(voz.estado(nombre))


@app.post("/api/voz/transcribir")
def voz_transcribir():
    datos = request.get_data(cache=False)
    if not datos.startswith(b"RIFF"):
        return jsonify(error="El audio no tiene el formato esperado."), 400
    try:
        return jsonify(voz.transcribir(datos, ALM.ajuste("voz_modelo", "small")))
    except RuntimeError as e:
        return jsonify(error=str(e)), 400


@app.get("/api/instalacion")
def instalacion_estado():
    return jsonify(instalacion.comprobar())


@app.post("/api/instalacion/ollama")
def instalacion_ollama():
    instalacion.empezar()
    return jsonify(instalacion.comprobar())


# ---------------------------------------------------------------- proyectos

@app.get("/api/proyectos")
def proyectos():
    return jsonify(ALM.proyectos())


@app.post("/api/proyectos")
def crear_proyecto():
    d = _json()
    pid = ALM.crear_proyecto((d.get("nombre") or "Expediente sin título").strip()[:120], bool(d.get("temporal")),
                             d.get("modelo") or ALM.ajuste("modelo_defecto", motor.MODELO),
                             d.get("perfil") if d.get("perfil") in multipasada.PERFILES else "estandar",
                             "sin_tabla" if d.get("tabla") == "sin_tabla" else "cifrada")
    if d.get("plantilla") or d.get("conservar"):
        ALM.actualizar_proyecto(pid, plantilla=d.get("plantilla"),
                                conservar=json.dumps([t for t in (d.get("conservar") or []) if t in motor.TIPOS]))
    guardar = "carpeta" if d.get("guardar") == "carpeta" and d.get("salida") else "junto"
    ALM.actualizar_proyecto(pid, guardar=guardar, salida=d.get("salida") if guardar == "carpeta" else None)
    return jsonify(ALM.proyecto(pid))


@app.get("/api/proyectos/<int:pid>")
def ver_proyecto(pid):
    p = _proyecto(pid)
    p["carpetas"] = ALM.carpetas(pid)
    p["archivos"] = ALM.archivos(pid)
    p["trabajos_activos"] = GESTOR.activos(pid)
    g = trabajos.modo_guardar(p)
    p["guardar_efectivo"] = g["modo"]
    p["salida_efectiva"] = g["base"] if g["modo"] == "carpeta" else None
    p["salida_sincronizada"] = bool(p["salida_efectiva"]) and rutas.sincronizada(p["salida_efectiva"])
    p["conservar"] = sorted(trabajos.conservar(p))
    return jsonify(p)


@app.patch("/api/proyectos/<int:pid>")
def editar_proyecto(pid):
    _proyecto(pid)
    d = _json()
    if "perfil" in d and d["perfil"] not in multipasada.PERFILES:
        d.pop("perfil")
    if "tabla" in d and d["tabla"] not in ("cifrada", "sin_tabla"):
        d.pop("tabla")
    if d.get("tabla") == "sin_tabla":
        trabajos.olvidar_registro(pid, borrar=True)
    if "conservar" in d:
        d["conservar"] = json.dumps([t for t in (d["conservar"] or []) if t in motor.TIPOS])
    if "guardar" in d:
        d["guardar"] = "carpeta" if d["guardar"] == "carpeta" and (d.get("salida") or _proyecto(pid).get("salida")) else "junto"
        if d["guardar"] == "junto":
            d["salida"] = None
    if "vigilar" in d:          # se guarda desde cuándo: solo se trata lo que llegue después
        d["vigilar"] = (_proyecto(pid).get("vigilar") or time.time()) if d["vigilar"] else 0
    ALM.actualizar_proyecto(pid, **d)
    return jsonify(ALM.proyecto(pid))


@app.delete("/api/proyectos/<int:pid>")
def borrar_proyecto(pid):
    _proyecto(pid)
    _borrar_proyecto(pid)
    return jsonify(ok=True)


def _borrar_proyecto(pid):
    for t in GESTOR.activos(pid):
        GESTOR.cancelar(t["id"])
    trabajos.olvidar_registro(pid, borrar=True)   # tabla cifrada + clave: borrado criptográfico
    shutil.rmtree(os.path.join(rutas.PROYECTOS, str(pid)), ignore_errors=True)
    ALM.borrar_proyecto(pid)


@app.post("/api/proyectos/<int:pid>/carpetas")
def anadir_carpeta(pid):
    _proyecto(pid)
    d = _json()
    rutas_ = d.get("rutas") or ([d["ruta"]] if d.get("ruta") else [])
    añadidas = []
    for r in rutas_:
        r = os.path.abspath(os.path.expanduser(str(r)))
        if not os.path.exists(r):
            continue
        tipo = "archivo" if os.path.isfile(r) else "carpeta"
        c = ALM.anadir_carpeta(pid, r, tipo)
        ALM.guardar_inventario(pid, c["id"], herramientas.inventariar(r, tipo))
        añadidas.append(c)
    if not añadidas:
        return jsonify(error="No encuentro esa carpeta o archivo."), 400
    ALM.tocar(pid)
    return jsonify(carpetas=ALM.carpetas(pid), archivos=ALM.archivos(pid))


@app.post("/api/proyectos/<int:pid>/carpetas/actualizar")
def actualizar_carpetas(pid):
    _proyecto(pid)
    for c in ALM.carpetas(pid):
        if os.path.exists(c["ruta"]):
            ALM.guardar_inventario(pid, c["id"], herramientas.inventariar(c["ruta"], c["tipo"]))
    return jsonify(carpetas=ALM.carpetas(pid), archivos=ALM.archivos(pid))


@app.delete("/api/proyectos/<int:pid>/carpetas/<int:cid>")
def quitar_carpeta(pid, cid):
    ALM.quitar_carpeta(pid, cid)
    return jsonify(carpetas=ALM.carpetas(pid), archivos=ALM.archivos(pid))


# ---------------------------------------------------------------- conversaciones

@app.get("/api/proyectos/<int:pid>/conversaciones")
def conversaciones(pid):
    return jsonify(ALM.conversaciones(pid))


@app.post("/api/proyectos/<int:pid>/conversaciones")
def crear_conversacion(pid):
    p = _proyecto(pid)
    titulo = (str(_json().get("titulo") or "").strip() or "Nueva conversación")[:120]
    cid = ALM.crear_conversacion(pid, titulo, modelo=p.get("modelo"))
    return jsonify(ALM.conversacion(cid))


@app.get("/api/conversaciones/<int:cid>")
def ver_conversacion(cid):
    c = ALM.conversacion(cid) or abort(404)
    c["mensajes"] = ALM.mensajes(cid)
    return jsonify(c)


@app.patch("/api/conversaciones/<int:cid>")
def editar_conversacion(cid):
    """Renombrar y/o mover a otro proyecto."""
    ALM.conversacion(cid) or abort(404)
    d = _json()
    if "titulo" in d:
        ALM.renombrar_conversacion(cid, ((d.get("titulo") or "").strip() or "Conversación")[:120])
    if d.get("proyecto") is not None:
        _proyecto(int(d["proyecto"]))
        c = ALM.conversacion(cid)
        if any(GESTOR.meta.get(t["id"], {}).get("conversacion") == cid for t in GESTOR.activos(c["proyecto"])):
            return jsonify(error="Esta conversación tiene una seudonimización en marcha. Espera a que termine o cancélala antes de moverla."), 409
        ALM.mover_conversacion(cid, int(d["proyecto"]))
    return jsonify(ALM.conversacion(cid))


@app.delete("/api/conversaciones/<int:cid>")
def borrar_conversacion(cid):
    ALM.borrar_conversacion(cid)
    return jsonify(ok=True)


@app.post("/api/conversaciones/<int:cid>/mensajes")
def enviar_mensaje(cid):
    conv = ALM.conversacion(cid) or abort(404)
    pr = _proyecto(conv["proyecto"])
    d = _json()
    texto = (d.get("texto") or "").strip()
    if not texto:
        return jsonify(error="Mensaje vacío."), 400
    modelo = d.get("modelo") or pr.get("modelo") or ALM.ajuste("modelo_defecto", motor.MODELO)
    ctx = {"almacen": ALM, "gestor": GESTOR, "proyecto": pr, "trabajo": rutas.TRABAJO, "resultados": resultados_de,
           "destino": _destino}

    def flujo():
        alm_hilo = almacen_mod.Almacen()          # conexión propia de este hilo
        c2 = dict(ctx, almacen=alm_hilo)
        for ev in asistente.responder(c2, cid, texto, modelo):
            yield json.dumps(ev, ensure_ascii=False) + "\n"
    return Response(flujo(), mimetype="application/x-ndjson")


@app.patch("/api/mensajes/<int:mid>")
def actualizar_plan(mid):
    """La interfaz anota en el mensaje si el plan se confirmó o se descartó."""
    ALM.actualizar_mensaje(mid, datos=_json().get("datos"))
    return jsonify(ok=True)


# ---------------------------------------------------------------- trabajos

@app.post("/api/proyectos/<int:pid>/trabajos")
def lanzar_trabajo(pid):
    p = _proyecto(pid)
    d = _json()
    ids = set(d.get("archivos") or [])
    elegidos = [a for a in ALM.archivos(pid) if a["admitido"] and (not ids or a["id"] in ids)]
    if not elegidos:
        return jsonify(error="No hay archivos admitidos que tratar."), 400
    faltan = [a["rel"] for a in elegidos if not os.path.isfile(a["ruta"])]
    if faltan:
        return jsonify(error="Estos archivos ya no están en su carpeta: %s" % ", ".join(faltan[:5])), 400
    perfil = d.get("perfil") if d.get("perfil") in multipasada.PERFILES else p["perfil"]
    modelo = d.get("modelo") or p.get("modelo") or ALM.ajuste("modelo_defecto", motor.MODELO)
    paginas = {}
    if d.get("paginas"):
        try:
            if isinstance(d["paginas"], dict):
                paginas = {int(k): sorted({int(x) for x in v})[:300] for k, v in d["paginas"].items() if v}
            elif len(elegidos) == 1:
                paginas = {elegidos[0]["id"]: sorted({int(x) for x in d["paginas"]})[:300]}
            else:
                return jsonify(error="Para repasar páginas concretas, elige un solo documento."), 400
        except (TypeError, ValueError):
            return jsonify(error="Números de página no válidos."), 400
        if any(x < 1 for v in paginas.values() for x in v):
            return jsonify(error="Las páginas se numeran desde la 1."), 400
    tid = GESTOR.lanzar(p, elegidos, perfil, modelo, d.get("conversacion"), bool(d.get("solo_ciclos")) and not paginas, paginas,
                        solo_paginas=bool(d.get("solo_paginas")) and bool(paginas))
    return jsonify(id=tid, estado=GESTOR.estado(tid))


@app.post("/api/proyectos/<int:pid>/tapar")
def tapar_y_rehacer(pid):
    """Plan «tapar» del chat, confirmado: añade los datos que indica el usuario al registro y
    rehace la copia de ese documento con el mismo alcance que la última (entera o solo unas páginas)."""
    p = _proyecto(pid)
    d = _json()
    a = next((x for x in ALM.archivos(pid) if x["id"] == d.get("archivo") and x["admitido"]), None)
    if not a:
        return jsonify(error="Ese documento ya no está en el expediente."), 400
    if not os.path.isfile(a["ruta"]):
        return jsonify(error="El documento ya no está en su carpeta: %s" % a["rel"]), 400
    datos = [re.sub(r"\s+", " ", str(x or "")).strip() for x in (d.get("datos") or [])]
    datos = [x for x in datos if 2 <= len(x) <= 120][:20]
    if not datos:
        return jsonify(error="No hay ningún dato que tapar."), 400
    tipo = d.get("tipo") if d.get("tipo") in motor.TIPOS else "OTRO"
    reg = trabajos.registro(pid, p["tabla"])
    for x in datos:
        reg.anadir_manual(x, tipo, a["id"])
    trabajos.guardar_registro(pid, p["tabla"])
    tid = _rehacer(p, a, d.get("perfil"), d.get("conversacion"))
    return jsonify(id=tid, estado=GESTOR.estado(tid))


def _rehacer(p, a, perfil=None, conversacion=None):
    """Rehace la copia de un documento con el mismo alcance que la última (entera o solo unas páginas)."""
    paginas = None
    if a.get("estado") == "parcial":          # la última copia era de solo unas páginas: se repite igual
        for t in ALM.trabajos(p["id"]):
            doc = next((x for x in ((t.get("resumen") or {}).get("documentos") or []) if x.get("id") == a["id"]), None)
            if doc is not None:
                paginas = doc.get("paginas")
                break
    perfil = perfil if perfil in multipasada.PERFILES else p["perfil"]
    modelo = p.get("modelo") or ALM.ajuste("modelo_defecto", motor.MODELO)
    ya_tratado = a.get("estado") in ("sin_hallazgos", "revision")
    return GESTOR.lanzar(p, [a], perfil, modelo, conversacion, solo_ciclos=ya_tratado and not paginas,
                         paginas={a["id"]: paginas} if paginas else None, solo_paginas=bool(paginas))


# ---------------------------------------------------------------- riesgo por contexto (opcional)

@app.post("/api/proyectos/<int:pid>/contexto/<int:aid>/analizar")
def analizar_contexto(pid, aid):
    """Solo cuando el profesional pulsa «Riesgo por contexto»: busca en la copia seudonimizada los
    datos indirectos que, juntos, podrían identificar a la persona, y propone cómo generalizarlos."""
    p = _proyecto(pid)
    c = _copias(pid).get(aid)
    if not c:
        return jsonify(error="Ese documento todavía no tiene una copia seudonimizada."), 400
    texto = _texto_copia(c)
    modelo = p.get("modelo") or ALM.ajuste("modelo_defecto", motor.MODELO)
    gens = trabajos.generalizaciones(p)
    try:
        r = contexto.analizar(texto, modelo, aplicadas=gens)
    except Exception as e:  # noqa
        return jsonify(error="No se ha podido analizar: %s" % str(e)[:200]), 500
    r["aplicadas"] = gens
    r["documento"] = c["copia"]
    return jsonify(r)


@app.post("/api/proyectos/<int:pid>/contexto/aplicar")
def aplicar_contexto(pid):
    """Guarda las generalizaciones que el profesional ha elegido (y quita las que ha desmarcado) y
    rehace la copia del documento. Valen para todo el proyecto: la misma persona en otros documentos."""
    p = _proyecto(pid)
    d = _json()
    a = next((x for x in ALM.archivos(pid) if x["id"] == d.get("archivo") and x["admitido"]), None)
    if not a:
        return jsonify(error="Ese documento ya no está en el expediente."), 400
    gens = {motor.clave(g["texto"]): g for g in trabajos.generalizaciones(p)}
    for q in d.get("quitar") or []:
        gens.pop(motor.clave(str(q)), None)
    for g in d.get("poner") or []:
        t = re.sub(r"\s+", " ", str(g.get("texto") or "")).strip()
        r = re.sub(r"\s+", " ", str(g.get("reemplazo") or "")).strip()
        if 2 <= len(t) <= 200 and 1 <= len(r) <= 120 and "[" not in t:
            gens[motor.clave(t)] = {"texto": t, "reemplazo": r, "categoria": g.get("categoria") or "otro"}
    ALM.actualizar_proyecto(pid, generalizaciones=json.dumps(list(gens.values()), ensure_ascii=False))
    p = _proyecto(pid)
    tid = _rehacer(p, a, d.get("perfil"), d.get("conversacion"))
    return jsonify(id=tid, estado=GESTOR.estado(tid), generalizaciones=len(gens))


@app.get("/api/trabajos/activos")
def trabajos_activos():
    """Lo que está en marcha y en cola en TODOS los proyectos (la cola es única: un trabajo cada vez)."""
    nombres = {p["id"]: p["nombre"] for p in ALM.proyectos()}
    res = []
    for t in GESTOR.activos():
        m = GESTOR.meta.get(t["id"], {})
        res.append({"id": t["id"], "proyecto": m.get("proyecto"), "nombre_proyecto": nombres.get(m.get("proyecto"), ""),
                    "estado": t["estado"], "progreso": t["progreso"], "documentos": len(t["docs"]),
                    "creado": m.get("creado", 0)})
    res.sort(key=lambda x: (x["estado"] != "procesando", x["creado"]))
    return jsonify(res)


@app.get("/api/trabajos/<tid>")
def estado_trabajo(tid):
    e = GESTOR.estado(tid)
    if e is None:
        abort(404)
    return jsonify(e)


@app.post("/api/trabajos/<tid>/cancelar")
def cancelar_trabajo(tid):
    return jsonify(ok=GESTOR.cancelar(tid))


@app.get("/api/proyectos/<int:pid>/trabajos")
def historial(pid):
    import certificado
    hist = ALM.trabajos(pid)
    for h in hist:
        c = (h.get("resumen") or {}).get("certificado")
        if not isinstance(c, str):
            c = os.path.join(h["destino"], certificado.NOMBRE) if h.get("destino") else None
        h["certificado"] = c if c and os.path.isfile(c) else None
        h["carpeta"] = (h.get("resumen") or {}).get("carpeta") or h.get("destino")
    return jsonify(activos=GESTOR.activos(pid), historial=hist)


# ---------------------------------------------------------------- revisión de hallazgos

@app.get("/api/proyectos/<int:pid>/registro")
def ver_registro(pid):
    p = _proyecto(pid)
    try:
        r = _registro(p)
    except cifrado.ErrorCifrado as e:
        return jsonify(error=str(e)), 400
    return jsonify(entidades=[dict({k: e[k] for k in ("id", "marcador", "tipo", "formas", "origenes", "docs", "activo", "ambigua")},
                                   conservado=e["tipo"] in r.conservar,
                                   en_lista=any(motor.clave_dato(f) in registro_mod.NUNCA for f in e["formas"]))
                              for e in r.entidades],
                   etiquetas=motor.ETIQUETAS, resumen=r.resumen(), version=r.version)


@app.post("/api/proyectos/<int:pid>/registro/<int:eid>/<accion>")
def cambiar_entidad(pid, eid, accion):
    p = _proyecto(pid)
    r = trabajos.registro(pid, p["tabla"])
    if eid >= len(r.entidades):
        abort(404)
    if accion == "descartar":
        r.descartar(eid)
    elif accion == "reactivar":
        r.reactivar(eid)
    else:
        abort(400)
    trabajos.guardar_registro(pid, p["tabla"])
    return jsonify(ok=True, version=r.version)


@app.post("/api/proyectos/<int:pid>/registro")
def anadir_entidad(pid):
    p = _proyecto(pid)
    d = _json()
    texto = (d.get("texto") or "").strip()
    if len(texto) < 2:
        return jsonify(error="Escribe el dato que quieres seudonimizar."), 400
    doc = d.get("doc") if isinstance(d.get("doc"), int) else None
    nuevas = trabajos.registro(pid, p["tabla"]).anadir_manual(texto, d.get("tipo") or "OTRO", doc)
    trabajos.guardar_registro(pid, p["tabla"])
    return jsonify(nuevas=[{"marcador": n["marcador"], "tipo": n["tipo"]} for n in nuevas])


@app.post("/api/proyectos/<int:pid>/tabla/exportar")
def exportar_tabla(pid):
    """Exportación EXPLÍCITA de la tabla con los datos originales, a la ruta elegida por el usuario."""
    p = _proyecto(pid)
    ruta = _json().get("ruta")
    if not ruta:
        return jsonify(error="Falta la ruta."), 400
    import csv
    r = trabajos.registro(pid, p["tabla"])
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Marcador", "Tipo", "Formas originales", "Detectado por", "Documentos", "Ambigua"])
        for fila in r.tabla():
            w.writerow([fila["marcador"], fila["tipo"], " | ".join(fila["formas"]), ", ".join(fila["detectado_por"]),
                        fila["documentos"], "sí" if fila["ambigua"] else ""])
    return jsonify(ok=True, ruta=ruta, sincronizada=rutas.sincronizada(ruta))


# ---------------------------------------------------------------- copias y mesa de revisión

_TEXTOS = {}          # (ruta, mtime) -> texto de la copia (en memoria; nunca se guarda en disco)


def _registro(p):
    r = trabajos.registro(p["id"], p["tabla"])
    r.conservar = trabajos.conservar(p)
    return r


def _copias(pid):
    """La copia más reciente de cada archivo tratado: {id_archivo: {...}}."""
    res = {}
    por_id = {t["id"]: t for t in ALM.trabajos(pid)}
    informes = {}
    for a in ALM.archivos(pid):
        if a["estado"] not in ("sin_hallazgos", "revision", "parcial") or not a.get("ultimo_trabajo"):
            continue
        t = por_id.get(a["ultimo_trabajo"])
        if not t or not t.get("destino"):
            continue
        docs = (t.get("resumen") or {}).get("documentos")
        if docs is None:
            if t["id"] not in informes:
                try:
                    with open(os.path.join(t["destino"], "Informe de verificación.json"), encoding="utf-8") as f:
                        informes[t["id"]] = json.load(f)["documentos"]
                except (OSError, ValueError, KeyError):
                    informes[t["id"]] = []
            docs = informes[t["id"]]
        d = next((x for x in docs if x.get("id") == a["id"]), None)
        if not d:
            continue
        ruta = d.get("copia") or os.path.join(t["destino"], d["rel"])
        if os.path.isfile(ruta):
            res[a["id"]] = {"id": a["id"], "original": a["rel"], "copia": os.path.basename(ruta) if d.get("copia") else d["rel"],
                            "ruta": ruta, "carpeta": os.path.dirname(ruta),
                            "estado": a["estado"], "trabajo": t["id"], "fecha": t.get("terminado") or t.get("creado")}
    return res


def _paginas_copia(c):
    clave = (c["ruta"], os.path.getmtime(c["ruta"]))
    if clave not in _TEXTOS:
        if len(_TEXTOS) > 40:
            _TEXTOS.clear()
        ext = os.path.splitext(c["ruta"])[1].lower()
        _TEXTOS[clave] = formatos.extraer_paginas(c["ruta"], ext)
    return _TEXTOS[clave]


SEPARADOR_PAGINAS = "\n\n"


def _texto_copia(c):
    return SEPARADOR_PAGINAS.join(_paginas_copia(c))


@app.get("/api/proyectos/<int:pid>/copias")
def ver_copias(pid):
    _proyecto(pid)
    return jsonify(sorted(_copias(pid).values(), key=lambda c: c["original"].lower()))


@app.get("/api/proyectos/<int:pid>/copias/<int:aid>")
def texto_copia(pid, aid):
    """Texto de la copia seudonimizada, con los datos conocidos que siguen a la vista."""
    p = _proyecto(pid)
    c = _copias(pid).get(aid)
    if not c:
        return jsonify(error="Este archivo todavía no tiene una copia seudonimizada."), 404
    try:
        paginas = _paginas_copia(c)
    except Exception as e:  # noqa
        return jsonify(error="No he podido leer la copia: %s" % str(e)[:200]), 400
    texto = SEPARADOR_PAGINAS.join(paginas)
    cortes, pos = [], 0
    for pg in paginas:               # dónde empieza cada página dentro del texto
        cortes.append(pos)
        pos += len(pg) + len(SEPARADOR_PAGINAS)
    r = _registro(p)
    escapados = []
    for e in r.mapa():
        for m in motor.patron(e["texto"], e["tipo"]).finditer(texto):
            escapados.append({"ini": m.start(), "fin": m.end(), "marcador": e["marcador"]})
            if len(escapados) > 500:
                break
    ext = os.path.splitext(c["ruta"])[1].lower()
    return jsonify(dict(c, texto=texto, escapados=escapados, paginas=cortes if len(paginas) > 1 else [],
                        unidad=formatos.unidad(ext), unidades=formatos.unidad(ext, True)))


def _texto_para_ia(pid, ids=None):
    copias = _copias(pid)
    partes = []
    for aid, c in sorted(copias.items(), key=lambda x: x[1]["copia"].lower()):
        if ids and aid not in ids:
            continue
        partes.append("### Documento: %s\n\n%s" % (os.path.basename(c["copia"]), _texto_copia(c).strip()))
    return partes


@app.post("/api/proyectos/<int:pid>/copias/texto")
def copiar_para_ia(pid):
    """Texto seudonimizado de las copias, listo para pegar en un chat de IA."""
    _proyecto(pid)
    ids = set(int(x) for x in (_json().get("archivos") or []))
    try:
        partes = _texto_para_ia(pid, ids or None)
    except Exception as e:  # noqa
        return jsonify(error="No he podido leer una de las copias: %s" % str(e)[:200]), 400
    if not partes:
        return jsonify(error="Todavía no hay copias seudonimizadas en este expediente."), 400
    texto = ("Los documentos siguientes están seudonimizados: los datos personales se han sustituido por marcadores "
             "entre corchetes, como [PERSONA_001]. Conserva los marcadores tal cual en tu respuesta.\n\n" + "\n\n".join(partes))
    return jsonify(texto=texto, documentos=len(partes), caracteres=len(texto))


_MARCA_LIBRE = re.compile(r"\[\s*([A-Z][A-Z_]*_\d{1,4})\s*\]|(?<![\w\[])([A-Z][A-Z]+(?:_[A-Z]+)*_\d{3})(?![\w\]])")


@app.post("/api/proyectos/<int:pid>/reidentificar")
def reidentificar(pid):
    """Vuelve a poner los datos reales en un texto con marcadores (la respuesta de una IA)."""
    p = _proyecto(pid)
    texto = _json().get("texto") or ""
    if p["tabla"] != "cifrada":
        return jsonify(error="Este expediente no guarda la tabla de correspondencias, así que no se pueden recuperar los datos. "
                             "Actívala en «Ajustes del expediente» para los próximos trabajos."), 400
    r = trabajos.registro(pid, p["tabla"])
    hechos, desconocidos = [], set()

    def poner(m):
        marca = "[%s]" % (m.group(1) or m.group(2))
        e = r.por_marcador(marca)
        if not e or not e["formas"]:
            desconocidos.add(marca)
            return m.group(0)
        hechos.append(marca)
        return max(e["formas"], key=len)     # la forma más completa (el nombre con apellidos)
    res = _MARCA_LIBRE.sub(poner, texto)
    return jsonify(texto=res, sustituidos=len(hechos), distintos=len(set(hechos)), desconocidos=sorted(desconocidos))


# ---------------------------------------------------------------- listas del despacho y plantillas

PLANTILLAS = [
    {"id": "general", "nombre": "General", "conservar": [],
     "descripcion": "Tapa todos los datos identificativos."},
    {"id": "despido", "nombre": "Despido o sanción", "conservar": ["DEPARTAMENTO"],
     "descripcion": "Conserva el departamento o centro de trabajo, útil para valorar la causa. Las fechas, importes, "
                    "categorías y el convenio no se tapan nunca."},
    {"id": "cantidad", "nombre": "Reclamación de cantidad", "conservar": ["DEPARTAMENTO"],
     "descripcion": "Conserva el departamento o centro de trabajo. Importes, periodos, categorías y convenio quedan a la vista."},
    {"id": "seguridad_social", "nombre": "Incapacidad o Seguridad Social", "conservar": ["EXPEDIENTE"],
     "descripcion": "Conserva el número de expediente administrativo para seguir el trámite. Los diagnósticos no se "
                    "tapan: revisa si hace falta compartirlos."},
    {"id": "empresa", "nombre": "Consulta sobre la empresa", "conservar": ["EMPRESA", "DEPARTAMENTO"],
     "descripcion": "Para preguntar por la empresa y no por personas: conserva el nombre de la empresa y sus departamentos."},
]


def _cargar_listas():
    listas = ALM.ajuste("listas", {"nunca": [], "siempre": []})
    registro_mod.fijar_listas(listas.get("nunca", []), listas.get("siempre", []))
    return listas


@app.get("/api/listas")
def ver_listas():
    return jsonify(_cargar_listas())


@app.put("/api/listas")
def guardar_listas():
    d = _json()
    nunca = [{"texto": str(x.get("texto", "")).strip()[:200]} for x in d.get("nunca", []) if str(x.get("texto", "")).strip()]
    siempre = [{"texto": str(x.get("texto", "")).strip()[:200], "tipo": x.get("tipo") if x.get("tipo") in motor.TIPOS else "OTRO"}
               for x in d.get("siempre", []) if len(str(x.get("texto", "")).strip()) >= 2]
    ALM.poner_ajuste("listas", {"nunca": nunca[:2000], "siempre": siempre[:2000]})
    return jsonify(_cargar_listas())


@app.get("/api/plantillas")
def ver_plantillas():
    return jsonify(plantillas=PLANTILLAS, etiquetas=motor.ETIQUETAS)


_cargar_listas()


def _reparar_interrumpidos():
    """Si la aplicación se cerró con un trabajo en marcha, ese trabajo queda «interrumpido» y sus
    archivos recuperan el estado de su última copia terminada (o vuelven a «Sin tratar»)."""
    try:
        for p in ALM.proyectos():
            hist = ALM.trabajos(p["id"])
            for t in hist:
                if t["estado"] in ("en_cola", "pendiente", "procesando"):
                    t["estado"] = "interrumpido"
                    t["terminado"] = t.get("terminado") or time.time()
                    ALM.guardar_trabajo(t)
            for a in ALM.archivos(p["id"]):
                if a["estado"] not in ("en_cola", "procesando", "pendiente"):
                    continue
                previo = None
                for t in hist:            # del más reciente al más antiguo
                    docs = (t.get("resumen") or {}).get("documentos") or []
                    d = next((x for x in docs if x.get("id") == a["id"]), None)
                    if d and t["estado"] != "interrumpido":
                        previo = (d["estado"], t["id"])
                        break
                if previo:
                    ALM.marcar_archivo(a["id"], previo[0], previo[1])
                else:
                    ALM.marcar_archivo(a["id"], "nuevo")
    except Exception:
        traceback.print_exc()


_reparar_interrumpidos()


# ---------------------------------------------------------------- carpeta vigilada

def _vigilancia():
    """Seudonimiza lo que entra en las carpetas de los proyectos vigilados, mientras la aplicación
    está abierta. Solo trata archivos que han aparecido o cambiado después de activar la vigilancia."""
    while True:
        time.sleep(20)
        try:
            for p in ALM.proyectos():
                desde = p.get("vigilar") or 0
                if not desde:
                    continue
                for c in ALM.carpetas(p["id"]):
                    if os.path.exists(c["ruta"]):
                        ALM.guardar_inventario(p["id"], c["id"], herramientas.inventariar(c["ruta"], c["tipo"]))
                salida = os.path.abspath(p.get("salida") or os.path.join(rutas.SALIDAS, trabajos._nombre_carpeta(p["nombre"])))
                ocupados = {d["id"] for t in GESTOR.activos(p["id"]) for d in t["docs"]}
                ahora = time.time()
                nuevos = [a for a in ALM.archivos(p["id"])
                          if a["admitido"] and a["estado"] == "nuevo" and (a.get("visto") or 0) > desde
                          and ahora - (a.get("visto") or 0) > 15 and a["id"] not in ocupados
                          and not os.path.abspath(a["ruta"]).startswith(salida + os.sep)
                          and "(seudonimizado" not in a["nombre"]
                          and os.sep + "Seudonimizados" + os.sep not in a["ruta"]]
                if nuevos:
                    modelo = p.get("modelo") or ALM.ajuste("modelo_defecto", motor.MODELO)
                    GESTOR.lanzar(p, nuevos, p["perfil"], modelo, None)
        except Exception:
            traceback.print_exc()


# ---------------------------------------------------------------- actualizaciones

# repositorio público: las versiones (también las previas, «pre-release») se consultan sin cuenta
URL_ACTUALIZACIONES = "https://api.github.com/repos/josemagarciaruiz-cmd/seudonimo/releases?per_page=5"


def _version(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3])


@app.get("/api/actualizacion")
def buscar_actualizacion():
    url = ALM.ajuste("url_actualizaciones", URL_ACTUALIZACIONES)
    try:
        import requests
        r = requests.get(url, timeout=6, headers={"Accept": "application/json"})
        if r.status_code != 200:
            return jsonify(nueva=False, motivo="no_disponible")
        d = r.json()
    except Exception:
        return jsonify(nueva=False, motivo="sin_conexion")
    if isinstance(d, list):      # lista de versiones de GitHub: la más reciente publicada
        d = next((x for x in d if not x.get("draft")), {})
    if "tag_name" in d:          # formato de las versiones de GitHub
        enlaces = [a.get("browser_download_url", "") for a in d.get("assets", [])]
        d = {"version": d["tag_name"], "notas": d.get("body") or "", "pagina": d.get("html_url"),
             "mac": next((u for u in enlaces if u.endswith(".dmg")), None),
             "windows": next((u for u in enlaces if u.endswith(".exe")), None)}
    instalador = d.get("windows") if rutas.ES_WINDOWS else d.get("mac")
    descarga = instalador or d.get("pagina")
    if descarga and not str(descarga).startswith("https://"):
        descarga = None
    version = str(d.get("version", "")).lstrip("v")
    nueva = _version(version) > _version(VERSION)
    _ULTIMA.clear()
    if nueva and instalador and str(instalador).startswith(actualizar.ORIGEN):
        _ULTIMA.update(url=instalador, version=version)
    return jsonify(nueva=nueva, version=version, notas=str(d.get("notas", ""))[:2000], descarga=descarga, actual=VERSION,
                   instalable=bool(_ULTIMA) and actualizar.instalable(), pagina=d.get("pagina"))


_ULTIMA = {}     # la última versión nueva encontrada (la instalación usa esta, nunca una dirección del cliente)


@app.post("/api/actualizacion/instalar")
def instalar_actualizacion():
    if not _ULTIMA or not actualizar.instalable():
        return jsonify(error="No hay ninguna actualización que instalar desde aquí."), 400
    if GESTOR.activos():
        return jsonify(error="Hay una seudonimización en marcha. Espera a que termine o cancélala antes de actualizar."), 409
    try:
        actualizar.iniciar(_ULTIMA["url"], _ULTIMA["version"], int(os.environ["SEUDONIMO_PADRE"]))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(actualizar.ESTADO)


@app.get("/api/actualizacion/estado")
def estado_actualizacion():
    return jsonify(actualizar.ESTADO)


@app.post("/api/actualizacion/descargar")
def descargar_actualizacion():
    url = _json().get("url") or ""
    if not url.startswith("https://"):
        return jsonify(error="Dirección de descarga no válida."), 400
    import webbrowser
    webbrowser.open(url)
    return jsonify(ok=True)


# ---------------------------------------------------------------- sistema

GUARDADOS = set()      # carpetas a las que el usuario ha copiado resultados en esta sesión


def _resultados_conocidos():
    """Carpetas y archivos de resultados que la aplicación ha creado: lo único que se puede abrir,
    mostrar o copiar desde la interfaz o el chat."""
    bases = [rutas.SALIDAS] + [p["salida"] for p in ALM.proyectos() if p.get("salida")]
    for p in ALM.proyectos():
        for t in ALM.trabajos(p["id"]):
            r = t.get("resumen") or {}
            if r.get("carpeta"):
                bases.append(r["carpeta"])
            if isinstance(r.get("certificado"), str):
                bases.append(os.path.dirname(r["certificado"]))
            for d in r.get("documentos") or []:
                if d.get("copia"):
                    bases.append(os.path.dirname(d["copia"]))
            if t.get("destino"):
                bases.append(t["destino"])
    return [os.path.abspath(b) for b in bases + sorted(GUARDADOS) if b]


def _permitida(ruta):
    ruta = os.path.abspath(ruta or "")
    return os.path.exists(ruta) and any(ruta == b or ruta.startswith(b + os.sep) for b in _resultados_conocidos())


@app.post("/api/abrir")
def abrir():
    ruta = os.path.abspath(_json().get("ruta") or "")
    if not _permitida(ruta):
        return jsonify(error="Solo se pueden abrir los resultados de Seudónimo."), 403
    rutas.abrir_carpeta(ruta)
    return jsonify(ok=True)


@app.post("/api/mostrar")
def mostrar():
    """Muestra el archivo seleccionado en el Finder o en el Explorador de archivos."""
    ruta = os.path.abspath(_json().get("ruta") or "")
    if not _permitida(ruta):
        return jsonify(error="Solo se pueden mostrar los resultados de Seudónimo."), 403
    rutas.mostrar_en_carpeta(ruta)
    return jsonify(ok=True)


DESTINOS_COMUNES = {"escritorio": ("Desktop", "Escritorio"), "documentos": ("Documents", "Documentos"),
                    "descargas": ("Downloads", "Descargas")}


def _destino(texto):
    """«Escritorio», «Documentos», «Descargas» o una carpeta que exista en este ordenador."""
    t = (texto or "").strip()
    clave = motor.clave(t).strip()
    if clave in DESTINOS_COMUNES:
        for n in DESTINOS_COMUNES[clave]:
            r = os.path.join(os.path.expanduser("~"), n)
            if os.path.isdir(r):
                return r
    r = os.path.abspath(os.path.expanduser(t)) if t else ""
    return r if r and os.path.isdir(r) else None


@app.post("/api/guardar_en")
def guardar_en():
    """Copia resultados (copias seudonimizadas o certificados) a una carpeta que elige el usuario."""
    d = _json()
    destino = _destino(d.get("destino"))
    if not destino:
        return jsonify(error="No encuentro esa carpeta en este ordenador."), 400
    hechos = []
    for r in d.get("rutas") or []:
        r = os.path.abspath(r)
        if not os.path.isfile(r) or not _permitida(r):
            return jsonify(error="Solo se pueden copiar los resultados de Seudónimo."), 403
        final = multipasada._ruta_libre(os.path.join(destino, os.path.basename(r)))
        shutil.copyfile(r, final)
        hechos.append(final)
    GUARDADOS.add(destino)
    return jsonify(copiados=hechos, carpeta=destino)


def resultados_de(pid):
    """Lo que el usuario necesita saber de un proyecto: sus copias, dónde están y los certificados."""
    p = _proyecto(pid)
    copias = sorted(_copias(pid).values(), key=lambda c: c["original"].lower())
    certificados = []
    for t in ALM.trabajos(pid):
        r = t.get("resumen") or {}
        c = r.get("certificado") if isinstance(r.get("certificado"), str) else None
        if c and os.path.isfile(c):
            certificados.append({"ruta": c, "nombre": os.path.basename(c), "fecha": t.get("terminado") or t.get("creado")})
    carpetas = sorted({c["carpeta"] for c in copias})
    g = trabajos.modo_guardar(p)
    return {"copias": copias, "carpetas": carpetas, "certificados": certificados[:20], "modo": g["modo"],
            "base": g["base"] if g["modo"] == "carpeta" else None}


@app.get("/api/proyectos/<int:pid>/resultados")
def resultados(pid):
    return jsonify(resultados_de(pid))


@app.post("/api/sistema/elegir")
def elegir():
    """Solo en modo navegador (en la ventana de escritorio se usa el diálogo de Tauri)."""
    tipo = _json().get("tipo", "carpeta")
    try:
        return jsonify(rutas=_dialogo(tipo))
    except Exception as e:  # noqa
        return jsonify(error=str(e)[:200]), 400


def _dialogo(tipo):
    import subprocess
    if rutas.ES_MAC:
        if tipo == "carpeta":
            s = 'POSIX path of (choose folder with prompt "Elige la carpeta del expediente")'
        elif tipo == "guardar":
            s = 'POSIX path of (choose file name with prompt "Guardar la tabla de correspondencias" default name "Tabla de correspondencias.csv")'
        else:
            s = ('set fs to choose file with prompt "Elige los archivos" with multiple selections allowed\n'
                 'set out to ""\nrepeat with f in fs\nset out to out & POSIX path of f & linefeed\nend repeat\nreturn out')
        r = subprocess.run(["osascript", "-e", s], capture_output=True, text=True, timeout=600)
        return [l for l in r.stdout.splitlines() if l.strip()]
    if rutas.ES_WINDOWS:
        if tipo == "carpeta":
            ps = ("Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog;"
                  "if($d.ShowDialog() -eq 'OK'){$d.SelectedPath}")
        elif tipo == "guardar":
            ps = ("Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.SaveFileDialog;"
                  "$d.FileName='Tabla de correspondencias.csv'; if($d.ShowDialog() -eq 'OK'){$d.FileName}")
        else:
            ps = ("Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog;"
                  "$d.Multiselect=$true; if($d.ShowDialog() -eq 'OK'){$d.FileNames}")
        r = rutas.ejecutar(["powershell", "-NoProfile", "-STA", "-Command", ps], text=True, timeout=600)
        return [l for l in r.stdout.splitlines() if l.strip()]
    raise RuntimeError("Diálogo no disponible en este sistema.")


@app.post("/api/apagar")
def apagar():
    threading.Timer(0.3, lambda: os._exit(0)).start()
    return jsonify(ok=True)


# ---------------------------------------------------------------- arranque

def _limpiar_temporales():
    """Proyectos temporales de la sesión anterior y restos de trabajo: fuera."""
    for p in ALM.proyectos():
        if p["temporal"]:
            _borrar_proyecto(p["id"])
    shutil.rmtree(rutas.TRABAJO, ignore_errors=True)
    os.makedirs(rutas.TRABAJO, exist_ok=True)


def _puerto_libre(preferido):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", preferido))
    except OSError:
        s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _al_arrancar():
    try:
        if instalacion.instalado() and not instalacion.activo():
            instalacion.arrancar_ollama(espera=30)
    except Exception:
        traceback.print_exc()


def main():
    global PUERTO
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=int(os.environ.get("SEUDONIMO_PUERTO", "0")))
    ap.add_argument("--navegador", action="store_true", help="abrir la interfaz en el navegador (modo de desarrollo)")
    a = ap.parse_args()
    _limpiar_temporales()
    if os.environ.get("SEUDONIMO_PUERTO"):
        PUERTO = int(os.environ["SEUDONIMO_PUERTO"])     # lo elige la ventana de escritorio
    else:
        PUERTO = _puerto_libre(a.puerto) if a.puerto else _puerto_libre(0)
    threading.Thread(target=_al_arrancar, daemon=True).start()
    threading.Thread(target=_vigilancia, daemon=True, name="vigilancia").start()
    print("SEUDONIMO_LISTO %d" % PUERTO, flush=True)
    if a.navegador:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:%d/" % PUERTO)).start()
    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", PUERTO, app, threaded=True)
    # si la ventana de escritorio se cierra, el servicio se apaga con ella
    padre = os.environ.get("SEUDONIMO_PADRE")
    if padre:
        threading.Thread(target=_vigilar_padre, args=(int(padre),), daemon=True).start()
    srv.serve_forever()


def _vigilar_padre(pid):
    while True:
        time.sleep(3)
        try:
            if rutas.ES_WINDOWS:
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                vivo = bool(h)
                if h:
                    code = ctypes.c_ulong()
                    ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
                    vivo = code.value == 259
                    ctypes.windll.kernel32.CloseHandle(h)
            else:
                os.kill(pid, 0)
                vivo = True
        except OSError:
            vivo = False
        if not vivo:
            os._exit(0)


if __name__ == "__main__":
    main()
