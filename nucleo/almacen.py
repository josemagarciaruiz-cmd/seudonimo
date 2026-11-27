# -*- coding: utf-8 -*-
"""Persistencia local en SQLite: proyectos, carpetas autorizadas, inventario de archivos,
conversaciones, mensajes, trabajos y ajustes.

No se guarda aquí el texto de los documentos ni la tabla de correspondencias (esta va cifrada
en la carpeta del proyecto). Los resultados de las herramientas se guardan resumidos, sin datos
originales. Un proyecto «temporal» se borra entero al cerrarlo."""
import json
import os
import sqlite3
import threading
import time

import rutas

ESQUEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS proyectos (
  id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, creado REAL, actualizado REAL,
  temporal INTEGER DEFAULT 0, modelo TEXT, perfil TEXT DEFAULT 'estandar',
  tabla TEXT DEFAULT 'cifrada', salida TEXT, instrucciones TEXT DEFAULT '', logos INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS carpetas (
  id INTEGER PRIMARY KEY, proyecto INTEGER REFERENCES proyectos(id) ON DELETE CASCADE,
  ruta TEXT NOT NULL, tipo TEXT DEFAULT 'carpeta', anadido REAL, UNIQUE(proyecto, ruta));
CREATE TABLE IF NOT EXISTS archivos (
  id INTEGER PRIMARY KEY, proyecto INTEGER REFERENCES proyectos(id) ON DELETE CASCADE,
  carpeta INTEGER REFERENCES carpetas(id) ON DELETE CASCADE, ruta TEXT NOT NULL, rel TEXT, nombre TEXT,
  ext TEXT, tamano INTEGER, modificado REAL, admitido INTEGER, motivo TEXT,
  estado TEXT DEFAULT 'nuevo', ultimo_trabajo TEXT, UNIQUE(proyecto, ruta));
CREATE TABLE IF NOT EXISTS conversaciones (
  id INTEGER PRIMARY KEY, proyecto INTEGER REFERENCES proyectos(id) ON DELETE CASCADE,
  titulo TEXT, creado REAL, actualizado REAL, modelo TEXT);
CREATE TABLE IF NOT EXISTS mensajes (
  id INTEGER PRIMARY KEY, conversacion INTEGER REFERENCES conversaciones(id) ON DELETE CASCADE,
  rol TEXT, contenido TEXT, datos TEXT, creado REAL);
CREATE TABLE IF NOT EXISTS trabajos (
  id TEXT PRIMARY KEY, proyecto INTEGER REFERENCES proyectos(id) ON DELETE CASCADE,
  conversacion INTEGER, tipo TEXT, estado TEXT, perfil TEXT, modelo TEXT, destino TEXT,
  resumen TEXT, creado REAL, terminado REAL);
CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT);
"""


class Almacen:
    def __init__(self, ruta=None):
        self.ruta = ruta or rutas.BASE_DATOS
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        self._local = threading.local()
        with self._c() as c:
            c.executescript(ESQUEMA)
            # columnas añadidas en la 0.3.0 (bases de datos creadas con versiones anteriores)
            for tabla, col, defin in (("proyectos", "conservar", "TEXT DEFAULT '[]'"), ("proyectos", "plantilla", "TEXT"),
                                      ("proyectos", "vigilar", "REAL DEFAULT 0"), ("archivos", "visto", "REAL"),
                                      ("proyectos", "guardar", "TEXT"), ("proyectos", "generalizaciones", "TEXT DEFAULT '[]'"),
                                      ("proyectos", "zonas", "TEXT DEFAULT '{}'")):
                if col not in [r[1] for r in c.execute("PRAGMA table_info(%s)" % tabla)]:
                    c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tabla, col, defin))

    def _c(self):
        c = getattr(self._local, "c", None)
        if c is None:
            c = sqlite3.connect(self.ruta, timeout=30)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            self._local.c = c
        return c

    def _q(self, sql, args=(), uno=False):
        cur = self._c().execute(sql, args)
        filas = [dict(r) for r in cur.fetchall()]
        return (filas[0] if filas else None) if uno else filas

    def _x(self, sql, args=()):
        c = self._c()
        try:
            cur = c.execute(sql, args)
            c.commit()
        except Exception:
            # Sin esto, una escritura fallida (p. ej. un trabajo que escribe en un proyecto recién
            # borrado) deja la transacción abierta en la conexión de ese hilo y bloquea la base.
            c.rollback()
            raise
        return cur.lastrowid

    # ------------------------------------------------------------ proyectos
    def proyectos(self):
        return self._q("SELECT * FROM proyectos ORDER BY actualizado DESC")

    def proyecto(self, pid):
        return self._q("SELECT * FROM proyectos WHERE id=?", (pid,), uno=True)

    def crear_proyecto(self, nombre, temporal=False, modelo=None, perfil="estandar", tabla="cifrada"):
        ahora = time.time()
        return self._x("INSERT INTO proyectos(nombre, creado, actualizado, temporal, modelo, perfil, tabla) "
                       "VALUES (?,?,?,?,?,?,?)", (nombre, ahora, ahora, int(temporal), modelo, perfil, tabla))

    CAMPOS_PROYECTO = ("nombre", "modelo", "perfil", "tabla", "salida", "instrucciones", "logos", "temporal",
                       "conservar", "plantilla", "vigilar", "guardar", "generalizaciones", "zonas")

    def actualizar_proyecto(self, pid, **campos):
        campos = {k: v for k, v in campos.items() if k in self.CAMPOS_PROYECTO}
        if campos:
            sets = ", ".join("%s=?" % k for k in campos)
            self._x("UPDATE proyectos SET %s, actualizado=? WHERE id=?" % sets, (*campos.values(), time.time(), pid))

    def tocar(self, pid):
        self._x("UPDATE proyectos SET actualizado=? WHERE id=?", (time.time(), pid))

    def borrar_proyecto(self, pid):
        self._x("DELETE FROM proyectos WHERE id=?", (pid,))

    # ------------------------------------------------------------ carpetas y archivos
    def carpetas(self, pid):
        return self._q("SELECT * FROM carpetas WHERE proyecto=? ORDER BY anadido", (pid,))

    def anadir_carpeta(self, pid, ruta, tipo="carpeta"):
        self._x("INSERT OR IGNORE INTO carpetas(proyecto, ruta, tipo, anadido) VALUES (?,?,?,?)",
                (pid, ruta, tipo, time.time()))
        return self._q("SELECT * FROM carpetas WHERE proyecto=? AND ruta=?", (pid, ruta), uno=True)

    def quitar_carpeta(self, pid, cid):
        self._x("DELETE FROM carpetas WHERE proyecto=? AND id=?", (pid, cid))

    def archivos(self, pid):
        return self._q("SELECT * FROM archivos WHERE proyecto=? ORDER BY rel", (pid,))

    def archivo(self, pid, aid):
        return self._q("SELECT * FROM archivos WHERE proyecto=? AND id=?", (pid, aid), uno=True)

    def guardar_inventario(self, pid, cid, filas):
        """Sustituye el inventario de una carpeta conservando el estado de los que siguen igual."""
        previos = {r["ruta"]: r for r in self._q("SELECT * FROM archivos WHERE proyecto=? AND carpeta=?", (pid, cid))}
        c = self._c()
        try:
            self._inventario(c, pid, cid, filas, previos)
        except Exception:
            c.rollback()
            raise

    def _inventario(self, c, pid, cid, filas, previos):
        vistos = set()
        for f in filas:
            vistos.add(f["ruta"])
            p = previos.get(f["ruta"])
            if p and p["tamano"] == f["tamano"] and p["modificado"] == f["modificado"]:
                continue
            # «visto»: cuándo apareció (o cambió) el archivo en la carpeta; lo usa la carpeta vigilada
            c.execute("INSERT OR REPLACE INTO archivos(id, proyecto, carpeta, ruta, rel, nombre, ext, tamano, modificado, "
                      "admitido, motivo, estado, visto) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (p["id"] if p else None, pid, cid, f["ruta"], f["rel"], f["nombre"], f["ext"], f["tamano"],
                       f["modificado"], int(f["admitido"]), f.get("motivo"), "nuevo" if f["admitido"] else "no_admitido",
                       time.time()))
        for ruta in set(previos) - vistos:
            c.execute("DELETE FROM archivos WHERE id=?", (previos[ruta]["id"],))
        c.commit()

    def marcar_archivo(self, aid, estado, trabajo=None):
        self._x("UPDATE archivos SET estado=?, ultimo_trabajo=COALESCE(?, ultimo_trabajo) WHERE id=?", (estado, trabajo, aid))

    # ------------------------------------------------------------ conversaciones
    def conversaciones(self, pid):
        return self._q("SELECT * FROM conversaciones WHERE proyecto=? ORDER BY actualizado DESC", (pid,))

    def conversacion(self, cid):
        return self._q("SELECT * FROM conversaciones WHERE id=?", (cid,), uno=True)

    def crear_conversacion(self, pid, titulo="Nueva conversación", modelo=None):
        ahora = time.time()
        self.tocar(pid)
        return self._x("INSERT INTO conversaciones(proyecto, titulo, creado, actualizado, modelo) VALUES (?,?,?,?,?)",
                       (pid, titulo, ahora, ahora, modelo))

    def renombrar_conversacion(self, cid, titulo):
        self._x("UPDATE conversaciones SET titulo=? WHERE id=?", (titulo, cid))

    def mover_conversacion(self, cid, pid):
        """Pasa la conversación a otro proyecto. Los planes sin confirmar se anulan: se referían a
        archivos del proyecto de origen, que el nuevo proyecto no tiene."""
        c = self.conversacion(cid)
        if not c:
            return False
        for m in self.mensajes(cid):
            d = m["datos"] or {}
            cambiado = False
            for plan in d.get("planes") or []:
                if not plan.get("estado"):
                    plan["estado"] = "otro_proyecto"
                    cambiado = True
            if cambiado:
                self.actualizar_mensaje(m["id"], datos=d)
        ahora = time.time()
        self._x("UPDATE conversaciones SET proyecto=?, actualizado=? WHERE id=?", (pid, ahora, cid))
        self.tocar(pid)
        self.tocar(c["proyecto"])
        return True

    def borrar_conversacion(self, cid):
        self._x("DELETE FROM conversaciones WHERE id=?", (cid,))

    def mensajes(self, cid):
        filas = self._q("SELECT * FROM mensajes WHERE conversacion=? ORDER BY id", (cid,))
        for f in filas:
            f["datos"] = json.loads(f["datos"]) if f["datos"] else None
        return filas

    def anadir_mensaje(self, cid, rol, contenido, datos=None):
        ahora = time.time()
        self._x("UPDATE conversaciones SET actualizado=? WHERE id=?", (ahora, cid))
        return self._x("INSERT INTO mensajes(conversacion, rol, contenido, datos, creado) VALUES (?,?,?,?,?)",
                       (cid, rol, contenido, json.dumps(datos, ensure_ascii=False) if datos is not None else None, ahora))

    def actualizar_mensaje(self, mid, contenido=None, datos=None):
        if contenido is not None:
            self._x("UPDATE mensajes SET contenido=? WHERE id=?", (contenido, mid))
        if datos is not None:
            self._x("UPDATE mensajes SET datos=? WHERE id=?", (json.dumps(datos, ensure_ascii=False), mid))

    # ------------------------------------------------------------ trabajos
    def guardar_trabajo(self, t):
        self._x("INSERT OR REPLACE INTO trabajos(id, proyecto, conversacion, tipo, estado, perfil, modelo, destino, resumen, "
                "creado, terminado) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (t["id"], t["proyecto"], t.get("conversacion"), t.get("tipo", "seudonimizacion"), t["estado"],
                 t.get("perfil"), t.get("modelo"), t.get("destino"),
                 json.dumps(t.get("resumen"), ensure_ascii=False) if t.get("resumen") is not None else None,
                 t.get("creado", time.time()), t.get("terminado")))

    def trabajos(self, pid):
        filas = self._q("SELECT * FROM trabajos WHERE proyecto=? ORDER BY creado DESC", (pid,))
        for f in filas:
            f["resumen"] = json.loads(f["resumen"]) if f["resumen"] else None
        return filas

    # ------------------------------------------------------------ ajustes
    def ajuste(self, clave, defecto=None):
        r = self._q("SELECT valor FROM ajustes WHERE clave=?", (clave,), uno=True)
        return json.loads(r["valor"]) if r else defecto

    def poner_ajuste(self, clave, valor):
        self._x("INSERT OR REPLACE INTO ajustes(clave, valor) VALUES (?,?)", (clave, json.dumps(valor, ensure_ascii=False)))
