# -*- coding: utf-8 -*-
"""Cola de trabajos: una inferencia cada vez (16 GB de memoria), un registro de entidades por
proyecto cargado y guardado cifrado, y estado en vivo para la interfaz."""
import os
import queue
import threading
import time
import traceback
import uuid

import cifrado
import multipasada
import registro as registro_mod
import rutas

_REGISTROS = {}
_CERROJO = threading.RLock()


def _ruta_registro(pid):
    ruta = os.path.join(rutas.PROYECTOS, str(pid), "registro.seudonimo")
    anterior = os.path.join(rutas.PROYECTOS, str(pid), "registro.aurea")     # nombre hasta la 0.1.x
    if not os.path.exists(ruta) and os.path.isfile(anterior):
        try:
            os.rename(anterior, ruta)
        except OSError:
            return anterior
    return ruta


def conservar(proyecto):
    """Tipos de dato que el proyecto no tapa (según la plantilla del asunto)."""
    import json
    c = proyecto.get("conservar") or "[]"
    if isinstance(c, (list, set, tuple)):
        return set(c)
    try:
        return set(json.loads(c))
    except (ValueError, TypeError):
        return set()


def registro(pid, tabla="cifrada"):
    """Registro de entidades del proyecto. En modo «sin_tabla» solo vive en memoria."""
    with _CERROJO:
        if pid in _REGISTROS:
            return _REGISTROS[pid]
        r = None
        ruta = _ruta_registro(pid)
        if tabla == "cifrada" and os.path.isfile(ruta):
            r = registro_mod.Registro.de_bytes(cifrado.descifrar(pid, open(ruta, "rb").read()), pid)
        _REGISTROS[pid] = r or registro_mod.Registro(pid)
        return _REGISTROS[pid]


def guardar_registro(pid, tabla="cifrada"):
    with _CERROJO:
        r = _REGISTROS.get(pid)
        if r is None or tabla != "cifrada":
            return
        os.makedirs(os.path.dirname(_ruta_registro(pid)), exist_ok=True)
        tmp = _ruta_registro(pid) + ".tmp"
        with open(tmp, "wb") as f:
            f.write(cifrado.cifrar(pid, r.a_bytes()))
        os.replace(tmp, _ruta_registro(pid))


def olvidar_registro(pid, borrar=False):
    """Descarta el registro en memoria; con borrar=True destruye también la tabla y su clave."""
    with _CERROJO:
        _REGISTROS.pop(pid, None)
        if borrar:
            try:
                os.remove(_ruta_registro(pid))
            except OSError:
                pass
            cifrado.borrar_clave(pid)


class Gestor:
    def __init__(self, almacen):
        self.almacen = almacen
        self.cola = queue.Queue()
        self.vivos = {}          # id -> TrabajoLote
        self.meta = {}           # id -> {proyecto, conversacion, creado}
        threading.Thread(target=self._bucle, daemon=True, name="trabajos").start()

    def lanzar(self, proyecto, archivos, perfil, modelo, conversacion=None, solo_ciclos=False):
        """archivos: filas del inventario (con «ruta», «rel», «nombre», «id»)."""
        tid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        reg = registro(proyecto["id"], proyecto["tabla"])
        reg.conservar = conservar(proyecto)
        base = proyecto.get("salida") or os.path.join(rutas.SALIDAS, _nombre_carpeta(proyecto["nombre"]))
        destino = os.path.join(base, time.strftime("%Y-%m-%d %H.%M.%S"))
        docs = [{"id": a["id"], "ruta": a["ruta"], "rel": a["rel"] or a["nombre"], "nombre": a["nombre"]} for a in archivos]
        lote = multipasada.TrabajoLote(tid, docs, reg, perfil=perfil, modelo=modelo, logos=bool(proyecto.get("logos", 1)),
                                       destino=destino, al_terminar=self._terminado)
        lote.ajustes["solo_ciclos"] = solo_ciclos
        self.vivos[tid] = lote
        self.meta[tid] = {"proyecto": proyecto["id"], "conversacion": conversacion, "creado": time.time(),
                          "tabla": proyecto["tabla"]}
        for a in archivos:
            self.almacen.marcar_archivo(a["id"], "en_cola", tid)
        self.almacen.guardar_trabajo({"id": tid, "proyecto": proyecto["id"], "conversacion": conversacion,
                                      "estado": "en_cola", "perfil": perfil, "modelo": modelo, "destino": destino})
        self.cola.put(tid)
        return tid

    def _bucle(self):
        while True:
            tid = self.cola.get()
            lote = self.vivos.get(tid)
            if lote is None or lote.cancelar_evento.is_set():
                if lote:
                    lote.estado = "cancelado"
                    self._terminado(lote)
                continue
            try:
                lote.ejecutar()
            except Exception:
                traceback.print_exc()

    def _terminado(self, lote):
        m = self.meta.get(lote.id, {})
        pid = m.get("proyecto")
        try:
            guardar_registro(pid, m.get("tabla", "cifrada"))
        except Exception:
            traceback.print_exc()
        if m.get("tabla") == "sin_tabla":
            olvidar_registro(pid)     # sin tabla persistente: nada sobrevive al lote
        for d in lote.docs:
            self.almacen.marcar_archivo(d.doc["id"], d.estado, lote.id)
        self.almacen.guardar_trabajo({"id": lote.id, "proyecto": pid, "conversacion": m.get("conversacion"),
                                      "estado": lote.estado, "perfil": lote.ajustes["perfil"],
                                      "modelo": lote.ajustes.get("modelo"), "destino": lote.destino,
                                      "resumen": lote.informe and {"recuento": lote.informe["recuento"],
                                                                   "registro": lote.informe["registro"],
                                                                   "duracion_s": lote.informe["duracion_s"],
                                                                   "documentos": [{"id": d["id"], "rel": d["rel"], "estado": d["estado"]}
                                                                                  for d in lote.informe["documentos"]],
                                                                   "certificado": bool(getattr(lote, "certificado", None))},
                                      "creado": m.get("creado"), "terminado": time.time()})

    def estado(self, tid):
        lote = self.vivos.get(tid)
        return lote.estado_publico() if lote else None

    def cancelar(self, tid):
        lote = self.vivos.get(tid)
        if lote:
            lote.cancelar()
            if lote.estado == "pendiente":
                lote.estado = "cancelado"
        return bool(lote)

    def activos(self, pid=None):
        return [l.estado_publico() for t, l in self.vivos.items()
                if l.estado in ("pendiente", "procesando") and (pid is None or self.meta[t]["proyecto"] == pid)]


def _nombre_carpeta(nombre):
    import re
    return re.sub(r"[\x00-\x1f/\\:*?\"<>|]", "_", nombre).strip() or "Proyecto"
