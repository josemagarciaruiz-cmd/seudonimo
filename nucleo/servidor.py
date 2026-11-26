# -*- coding: utf-8 -*-
"""Áurea Asistente Local · servicio local (sidecar) que usa la ventana de escritorio.

Seguridad:
- Escucha solo en 127.0.0.1 (nunca en la red) y en un puerto libre elegido al arrancar.
- Cada petición a /api lleva un token efímero (X-Aurea-Token), generado en cada arranque.
- Se valida el Host (contra DNS rebinding) y el Origin (solo la ventana de la aplicación).
- El modelo solo ve archivos que el usuario ha añadido con el diálogo del sistema.

Uso: python servidor.py [--puerto 0] [--navegador]
Imprime «AUREA_LISTO <puerto>» cuando está preparado (lo lee la ventana de Tauri)."""
import argparse
import json
import os
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

import almacen as almacen_mod  # noqa: E402
import asistente  # noqa: E402
import cifrado  # noqa: E402
import formatos  # noqa: E402
import herramientas  # noqa: E402
import instalacion  # noqa: E402
import motor  # noqa: E402
import multipasada  # noqa: E402
import ocr  # noqa: E402
import proveedores  # noqa: E402
import trabajos  # noqa: E402
from version import VERSION  # noqa: E402

INTERFAZ = os.environ.get("AUREA_INTERFAZ") or os.path.join(os.path.dirname(rutas.APP), "interfaz")
TOKEN = os.environ.get("AUREA_TOKEN") or secrets.token_urlsafe(32)
ORIGENES = {"tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"}

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
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
        if not secrets.compare_digest(request.headers.get("X-Aurea-Token", ""), TOKEN):
            abort(401)


@app.after_request
def _cabeceras(r):
    origen = request.headers.get("Origin")
    if origen in ORIGENES:
        r.headers["Access-Control-Allow-Origin"] = origen
        r.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Aurea-Token"
        r.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
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
    html = html.replace("<head>", "<head><script>window.AUREA_CONEXION={token:%s}</script>" % json.dumps(TOKEN), 1)
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
    pid = ALM.crear_proyecto((d.get("nombre") or "Proyecto sin título").strip()[:120], bool(d.get("temporal")),
                             d.get("modelo") or ALM.ajuste("modelo_defecto", motor.MODELO),
                             d.get("perfil") if d.get("perfil") in multipasada.PERFILES else "estandar",
                             "sin_tabla" if d.get("tabla") == "sin_tabla" else "cifrada")
    return jsonify(ALM.proyecto(pid))


@app.get("/api/proyectos/<int:pid>")
def ver_proyecto(pid):
    p = _proyecto(pid)
    p["carpetas"] = ALM.carpetas(pid)
    p["archivos"] = ALM.archivos(pid)
    p["trabajos_activos"] = GESTOR.activos(pid)
    p["salida_efectiva"] = p.get("salida") or os.path.join(rutas.SALIDAS, trabajos._nombre_carpeta(p["nombre"]))
    p["salida_sincronizada"] = rutas.sincronizada(p["salida_efectiva"])
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
    cid = ALM.crear_conversacion(pid, modelo=p.get("modelo"))
    return jsonify(ALM.conversacion(cid))


@app.get("/api/conversaciones/<int:cid>")
def ver_conversacion(cid):
    c = ALM.conversacion(cid) or abort(404)
    c["mensajes"] = ALM.mensajes(cid)
    return jsonify(c)


@app.patch("/api/conversaciones/<int:cid>")
def renombrar_conversacion(cid):
    ALM.renombrar_conversacion(cid, (_json().get("titulo") or "Conversación")[:120])
    return jsonify(ok=True)


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
    ctx = {"almacen": ALM, "gestor": GESTOR, "proyecto": pr, "trabajo": rutas.TRABAJO}

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
    tid = GESTOR.lanzar(p, elegidos, perfil, modelo, d.get("conversacion"), bool(d.get("solo_ciclos")))
    return jsonify(id=tid, estado=GESTOR.estado(tid))


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
    return jsonify(activos=GESTOR.activos(pid), historial=ALM.trabajos(pid))


# ---------------------------------------------------------------- revisión de hallazgos

@app.get("/api/proyectos/<int:pid>/registro")
def ver_registro(pid):
    p = _proyecto(pid)
    try:
        r = trabajos.registro(pid, p["tabla"])
    except cifrado.ErrorCifrado as e:
        return jsonify(error=str(e)), 400
    return jsonify(entidades=[{k: e[k] for k in ("id", "marcador", "tipo", "formas", "origenes", "docs", "activo", "ambigua")}
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
    nuevas = trabajos.registro(pid, p["tabla"]).anadir_manual(texto, d.get("tipo") or "OTRO")
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


# ---------------------------------------------------------------- sistema

@app.post("/api/abrir")
def abrir():
    ruta = os.path.abspath(_json().get("ruta") or "")
    permitidas = [rutas.SALIDAS] + [p["salida"] for p in ALM.proyectos() if p.get("salida")]
    if not any(ruta == b or ruta.startswith(os.path.abspath(b) + os.sep) for b in permitidas) or not os.path.exists(ruta):
        return jsonify(error="Solo se pueden abrir las carpetas de resultados."), 403
    rutas.abrir_carpeta(ruta)
    return jsonify(ok=True)


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
            s = 'POSIX path of (choose folder with prompt "Elige la carpeta del proyecto")'
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
    ap.add_argument("--puerto", type=int, default=int(os.environ.get("AUREA_PUERTO", "0")))
    ap.add_argument("--navegador", action="store_true", help="abrir la interfaz en el navegador (modo de desarrollo)")
    a = ap.parse_args()
    _limpiar_temporales()
    PUERTO = _puerto_libre(a.puerto) if a.puerto else _puerto_libre(0)
    threading.Thread(target=_al_arrancar, daemon=True).start()
    print("AUREA_LISTO %d" % PUERTO, flush=True)
    if a.navegador:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:%d/" % PUERTO)).start()
    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", PUERTO, app, threaded=True)
    # si la ventana de escritorio se cierra, el servicio se apaga con ella
    padre = os.environ.get("AUREA_PADRE")
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
