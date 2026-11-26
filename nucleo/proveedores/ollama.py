# -*- coding: utf-8 -*-
"""Adaptador de Ollama (https://github.com/ollama/ollama/blob/main/docs/api.md).

Solo se conecta a 127.0.0.1: los documentos nunca salen del ordenador."""
import json
import re
import os
import threading

import requests

from .base import ErrorProveedor, ProveedorModelos, json_de_texto

URL = os.environ.get("SEUDONIMO_OLLAMA", "http://127.0.0.1:11434")
CONTEXTO = 8192          # hipótesis inicial del plan (4.096–8.192 tokens); ajustable por modelo
MANTENER = "15m"          # el modelo sigue cargado durante el lote


class Ollama(ProveedorModelos):
    nombre = "ollama"

    def __init__(self, url=URL):
        self.url = url.rstrip("/")
        self._caps = {}
        self._cerrojo = threading.Lock()   # una inferencia cada vez (16 GB de memoria)

    # ------------------------------------------------------------ inventario
    def disponible(self):
        try:
            return requests.get(self.url + "/api/version", timeout=2).ok
        except Exception:
            return False

    def version(self):
        try:
            return requests.get(self.url + "/api/version", timeout=2).json().get("version")
        except Exception:
            return None

    def listar(self):
        try:
            r = requests.get(self.url + "/api/tags", timeout=5)
            r.raise_for_status()
        except Exception as e:
            raise ErrorProveedor("Ollama no responde: %s" % e)
        res = []
        for m in r.json().get("models", []):
            d = m.get("details") or {}
            nombre = m.get("name") or m.get("model")
            res.append({"nombre": nombre, "tamano": m.get("size", 0), "familia": d.get("family"),
                        "parametros": d.get("parameter_size"), "cuantizacion": d.get("quantization_level"),
                        "capacidades": sorted(self.capacidades(nombre))})
        return res

    def ficha(self, modelo):
        r = requests.post(self.url + "/api/show", json={"model": modelo}, timeout=10)
        r.raise_for_status()
        return r.json()

    def capacidades(self, modelo):
        if modelo not in self._caps:
            try:
                caps = set(self.ficha(modelo).get("capabilities") or [])
            except Exception:
                caps = set()
            self._caps[modelo] = caps or {"completion"}
        return self._caps[modelo]

    def cargados(self):
        try:
            return [m.get("name") for m in requests.get(self.url + "/api/ps", timeout=3).json().get("models", [])]
        except Exception:
            return []

    # ------------------------------------------------------------ inferencia
    def _cuerpo(self, modelo, mensajes, opciones, **extra):
        op = {"temperature": 0, "num_ctx": CONTEXTO}
        op.update(opciones or {})
        cuerpo = {"model": modelo, "messages": mensajes, "keep_alive": MANTENER, "options": op}
        if "thinking" in self.capacidades(modelo):
            cuerpo["think"] = False   # respuestas directas: el razonamiento largo no mejora la extracción
        cuerpo.update(extra)
        return cuerpo

    def _post(self, cuerpo, flujo=False):
        try:
            r = requests.post(self.url + "/api/chat", json=cuerpo, stream=flujo, timeout=(10, 1800))
            if r.status_code == 400 and "think" in r.text.lower():
                cuerpo.pop("think", None)
                r = requests.post(self.url + "/api/chat", json=cuerpo, stream=flujo, timeout=(10, 1800))
            if r.status_code >= 400:
                raise ErrorProveedor(r.text[:300])
            return r
        except requests.exceptions.ConnectionError:
            raise ErrorProveedor("No consigo hablar con Ollama. Comprueba que está abierto.")

    def chat(self, modelo, mensajes, herramientas=None, opciones=None, flujo=False):
        extra = {"stream": bool(flujo)}
        if herramientas and "tools" in self.capacidades(modelo):
            extra["tools"] = herramientas
        cuerpo = self._cuerpo(modelo, mensajes, opciones, **extra)
        if not flujo:
            with self._cerrojo:
                msg = self._post(cuerpo).json().get("message", {})
            return {"contenido": limpiar_pensamiento(msg.get("content", "")), "llamadas": _llamadas(msg)}
        return self._flujo(cuerpo)

    def _flujo(self, cuerpo):
        return _sin_pensamiento(self._flujo_bruto(cuerpo))

    def _flujo_bruto(self, cuerpo):
        with self._cerrojo:
            r = self._post(cuerpo, flujo=True)
            llamadas = []
            for linea in r.iter_lines():
                if not linea:
                    continue
                d = json.loads(linea)
                if d.get("error"):
                    raise ErrorProveedor(d["error"])
                msg = d.get("message") or {}
                llamadas += _llamadas(msg)
                if msg.get("content"):
                    yield {"contenido": msg["content"]}
                if d.get("done"):
                    yield {"fin": True, "llamadas": llamadas,
                           "tokens": d.get("eval_count"), "tokens_entrada": d.get("prompt_eval_count")}
                    return

    def estructurado(self, modelo, mensajes, esquema, opciones=None):
        cuerpo = self._cuerpo(modelo, mensajes, opciones, stream=False, format=esquema)
        with self._cerrojo:
            contenido = self._post(cuerpo).json().get("message", {}).get("content", "")
        return json_de_texto(contenido)

    # ------------------------------------------------------------ gestión
    def descargar(self, modelo, progreso=None):
        totales, hechos = {}, {}
        try:
            with requests.post(self.url + "/api/pull", json={"model": modelo, "stream": True},
                               stream=True, timeout=(10, 3600)) as r:
                r.raise_for_status()
                for linea in r.iter_lines():
                    if not linea:
                        continue
                    d = json.loads(linea)
                    if d.get("error"):
                        raise ErrorProveedor(d["error"])
                    if d.get("digest") and d.get("total"):
                        totales[d["digest"]] = d["total"]
                        hechos[d["digest"]] = d.get("completed", 0)
                    if progreso:
                        progreso(sum(hechos.values()), sum(totales.values()), d.get("status", ""))
                    if d.get("status") == "success":
                        break
        except requests.exceptions.ConnectionError:
            raise ErrorProveedor("No consigo hablar con Ollama. Comprueba que está abierto.")
        self._caps.pop(modelo, None)

    def borrar(self, modelo):
        r = requests.delete(self.url + "/api/delete", json={"model": modelo}, timeout=30)
        if r.status_code >= 400:
            raise ErrorProveedor(r.text[:300])
        self._caps.pop(modelo, None)

    def descargar_de_memoria(self, modelo):
        try:
            requests.post(self.url + "/api/chat", json={"model": modelo, "messages": [], "keep_alive": 0}, timeout=10)
        except Exception:
            pass


def _llamadas(msg):
    res = []
    for c in msg.get("tool_calls") or []:
        f = c.get("function") or {}
        args = f.get("arguments") or {}
        if isinstance(args, str):
            args = json_de_texto(args)
        res.append({"nombre": f.get("name"), "argumentos": args})
    return res


# Algunos modelos (Gemma 4) a veces devuelven su razonamiento interno al principio de la respuesta,
# con la forma «thought … <channel|>texto». Eso no es para el usuario: se quita.
_PENSAMIENTO = re.compile(r"(?s)^\s*(?:thought|thinking|<\|?channel\|?>\s*thought)\b.*?<\|?channel\|?>")
_MARCAS_CANAL = re.compile(r"<\|?(?:channel|message|start|end|turn)\|?>")


def limpiar_pensamiento(texto):
    return _MARCAS_CANAL.sub("", _PENSAMIENTO.sub("", texto or ""))


def _sin_pensamiento(trozos, limite=6000):
    """Filtro para el flujo: retiene el principio hasta saber si es razonamiento interno."""
    retenido, decidido = "", False
    for t in trozos:
        if decidido or not t.get("contenido"):
            if t.get("contenido"):
                t = dict(t, contenido=_MARCAS_CANAL.sub("", t["contenido"]))
                if not t["contenido"]:
                    continue
            if t.get("fin") and retenido:
                yield {"contenido": limpiar_pensamiento(retenido)}
                retenido = ""
            yield t
            continue
        retenido += t["contenido"]
        inicio = retenido.lstrip().lower()
        posible = ("thought".startswith(inicio[:7]) or inicio.startswith("<")) if inicio else True
        if not posible:
            decidido = True
            yield {"contenido": _MARCAS_CANAL.sub("", retenido)}
            retenido = ""
        elif _PENSAMIENTO.search(retenido) or len(retenido) > limite:
            decidido = True
            limpio = limpiar_pensamiento(retenido).lstrip()
            retenido = ""
            if limpio:
                yield {"contenido": limpio}
    if retenido:
        yield {"contenido": limpiar_pensamiento(retenido)}
