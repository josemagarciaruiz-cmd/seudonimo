# -*- coding: utf-8 -*-
"""Controlador multipasada de seudonimización (MultipassRedactionJob).

Implementa el anexo técnico: el controlador es código determinista, no una conversación
abierta con el modelo. El modelo identifica entidades; el motor documental modifica los
archivos y es el controlador quien decide cuándo repetir y cuándo parar.

Por documento:
  1. Copia inmutable del original (solo lectura). Nunca se toca el archivo del usuario.
  2. Pasada de detección 1: texto nativo + OCR, reglas y modelo (prompt de detección, con
     segunda lectura de las costuras entre fragmentos).
  3. Pasada de detección 2: el texto con lo ya hallado sustituido por marcadores se entrega a
     un auditor (prompt distinto, otros cortes). Mínimo dos pasadas completas de detección.
  4. Ciclos de transformación y verificación: se reconstruye SIEMPRE desde el original
     inmutable con el registro actualizado (sin degradar el PDF ni rasterizar sobre lo ya
     rasterizado) y se verifica de forma independiente (ver verificacion.py). Cada ciclo usa
     un método de verificación distinto.
  5. Parada:
       - «sin_hallazgos»: N verificaciones consecutivas sin nuevos hallazgos, sin restos y sin
         incidencias graves (N = 2 en verificación intensiva, 1 en estándar);
       - «revision»: máximo de ciclos, tiempo agotado, datos que no se pueden localizar o
         eliminar, incidencias estructurales o bucle sin progreso;
       - «error»: el documento no se puede leer o escribir.

Por lote (carpeta): un registro de entidades compartido. Cuando un documento posterior aporta
una variante nueva, se vuelven a comprobar los anteriores (con un máximo de rondas globales)."""
import json
import os
import re
import shutil
import stat
import threading
import time
import traceback

import formatos
import motor
import registro as registro_mod
import rutas
import verificacion

ESTADOS = {
    "pendiente": "Pendiente",
    "procesando": "Procesando",
    "sin_hallazgos": "Sin hallazgos en las comprobaciones configuradas",
    "revision": "Requiere revisión",
    "error": "Error de procesamiento",
    "cancelado": "Cancelado",
}

PERFILES = {
    # parámetros de ingeniería provisionales, no umbrales validados: se ajustan con el corpus
    "estandar": {"min_detecciones": 2, "max_ciclos": 3, "limpias": 1, "modelo_auditor": False,
                 "tiempo_max": 3600, "rondas_globales": 2},
    "intensivo": {"min_detecciones": 2, "max_ciclos": 5, "limpias": 2, "modelo_auditor": True,
                  "tiempo_max": 3 * 3600, "rondas_globales": 2},
}


class Cancelado(Exception):
    pass


class _Cronometro:
    def __init__(self):
        self.t = {}

    def medir(self, clave):
        crono = self

        class _C:
            def __enter__(self):
                self.t0 = time.time()

            def __exit__(self, *a):
                crono.t[clave] = round(crono.t.get(clave, 0) + time.time() - self.t0, 2)
        return _C()


def _localizable(texto, original):
    """El hallazgo procede de la versión transformada: antes de editar se comprueba que
    también está en el original (con sus variantes), que es de donde se reconstruye."""
    return motor.patron(texto).search(original) is not None


def nombre_salida(nombre, mapa):
    base, ext = os.path.splitext(nombre)
    base = motor.reemplazar_texto(base, mapa)
    base = re.sub(r"[\x00-\x1f/\\:*?\"<>|]", "_", base).strip() or "documento"
    return "%s (seudonimizado)%s" % (base, ext)


class TrabajoDocumento:
    def __init__(self, doc, registro, ajustes, carpeta, avisar=None, cancelado=None):
        """doc: {"id", "ruta", "rel", "nombre"}; ajustes: perfil + {"modelo", "logos"}."""
        self.doc = doc
        self.registro = registro
        self.ajustes = ajustes
        self.carpeta = carpeta
        self._avisar = avisar or (lambda *a, **k: None)
        self._cancelado = cancelado or (lambda: False)
        self.crono = _Cronometro()
        self.estado = "pendiente"
        self.motivos = []
        self.pasadas = []          # [{tipo, ciclo, metodo, nuevos, restos, incidencias}]
        self.incidencias = []
        self.salida = None
        self.ext = None
        self.ext_original = os.path.splitext(doc["nombre"])[1].lower()
        self.texto_original = None  # solo en memoria; nunca se guarda en disco
        self.paginas_texto = None   # texto por página (PDF), para repasar solo unas páginas
        self.version_registro = -1
        self.aplicado = set()       # (forma, marcador) aplicados en el último ciclo
        self.aviso = None
        self.t0 = None

    # ------------------------------------------------------------ utilidades
    def avisar(self, frac, mensaje):
        self._avisar(self, frac, mensaje)

    def comprobar(self):
        if self._cancelado():
            raise Cancelado()
        if self.t0 and time.time() - self.t0 > self.ajustes["tiempo_max"]:
            raise TimeoutError("Se ha agotado el tiempo máximo por documento.")

    def resumen(self):
        """Sin datos originales: apto para el informe exportable."""
        return {"id": self.doc["id"], "rel": self.doc.get("rel_salida") or self.doc["rel"], "estado": self.estado,
                "estado_texto": ESTADOS[self.estado], "motivos": self.motivos, "pasadas": [
                    {k: v for k, v in p.items() if k != "detalle"} for p in self.pasadas],
                "incidencias": [{k: v for k, v in i.items()} for i in self.incidencias],
                "aviso": self.aviso, "tiempos": self.crono.t,
                "ciclos": sum(1 for p in self.pasadas if p["tipo"] == "verificacion")}

    # ------------------------------------------------------------ flujo
    def ejecutar(self):
        self.t0 = time.time()
        self.estado = "procesando"
        try:
            self._preparar()
            if not self.ajustes.get("solo_ciclos"):
                self._detectar()      # al regenerar tras la revisión humana, el registro ya está completo
            self._ciclos()
        except Cancelado:
            self.estado = "cancelado"
        except TimeoutError as e:
            self.estado = "revision"
            self.motivos.append(str(e))
        except formatos.ErrorFormato as e:
            self.estado = "error"
            self.motivos.append(str(e))
        except Exception as e:  # noqa
            traceback.print_exc()
            self.estado = "error"
            self.motivos.append("Error inesperado: %s" % str(e)[:200])
        return self.estado

    def _preparar(self):
        self.avisar(0.0, "preparando una copia de trabajo…")
        orig = os.path.join(self.carpeta, "original")
        os.makedirs(orig, exist_ok=True)
        copia = os.path.join(orig, self.doc["nombre"])
        shutil.copy2(self.doc["ruta"], copia)
        os.chmod(copia, stat.S_IRUSR | stat.S_IRGRP)        # copia inmutable
        with self.crono.medir("preparacion"):
            self.ruta, self.ext, self.aviso = formatos.preparar(copia, orig)
        with self.crono.medir("extraccion_ocr"):
            self.paginas_texto = formatos.extraer_paginas(
                self.ruta, self.ext,
                progreso=lambda i, t: self.avisar(0.02 + 0.13 * i / t, "OCR de la página escaneada %d de %d" % (i, t)))
            self.texto_original = "\n".join(self.paginas_texto)
        if not self.texto_original.strip():
            raise formatos.ErrorFormato("El documento no contiene texto que seudonimizar.")

    def _modelo(self, texto, prompt, frac0, frac1, etiqueta, desfase=0, costura=True):
        def avance(i, t):
            self.avisar(frac0 + (frac1 - frac0) * (i - 1) / max(t, 1), "%s: fragmento %d de %d" % (etiqueta, i, t))
        with self.crono.medir("inferencia"):
            return motor.detectar_gemma(texto, avance, costura=costura, prompt=prompt, modelo=self.ajustes.get("modelo"),
                                        desfase=desfase, cancelado=self._cancelado,
                                        origen="Modelo · %s" % etiqueta.split(":")[0])

    def _detectar(self):
        texto = self.texto_original
        pags = self.doc.get("paginas")
        if pags and self.paginas_texto and len(self.paginas_texto) > 1:
            # repaso de unas páginas concretas: el modelo solo lee esas páginas; la copia se
            # regenera entera desde el original con todo lo que ya sabe el registro
            validas = [p for p in pags if 1 <= p <= len(self.paginas_texto)]
            if not validas:
                raise formatos.ErrorFormato("El documento tiene %d páginas: no existe la página %s." % (
                    len(self.paginas_texto), ", ".join(map(str, pags))))
            texto = "\n".join(self.paginas_texto[p - 1] for p in validas)
        # Pasada de detección 1: reglas + modelo con el prompt de detección
        self.comprobar()
        ents = motor.detectar_regex(texto) + registro_mod.de_la_lista(texto)
        ents += self._modelo(texto, motor.PROMPT, 0.15, 0.45, "detección 1")
        self.comprobar()
        nuevas = self.registro.incorporar(motor.filtrar_fechas(ents, texto), self.doc["id"])
        self.pasadas.append({"tipo": "deteccion", "n": 1, "nuevos": len(nuevas), "tiempo": round(time.time() - self.t0, 1)})

        # Pasada de detección 2: el texto ya enmascarado, a un auditor con otro prompt y otros cortes
        for n in range(2, self.ajustes["min_detecciones"] + 1):
            enmascarado = motor.reemplazar_texto(texto, self.registro.mapa())
            ents = motor.detectar_regex(enmascarado)
            prompt = motor.PROMPT_AUDITORIA if n % 2 == 0 else motor.PROMPT_AUDITORIA_B
            ents += self._modelo(enmascarado, prompt, 0.45, 0.7, "detección %d" % n, desfase=1250 * (n - 1), costura=False)
            self.comprobar()
            ents = [e for e in ents if _localizable(e["texto"], texto)]
            nuevas = self.registro.incorporar(motor.filtrar_fechas(ents, texto), self.doc["id"])
            self.pasadas.append({"tipo": "deteccion", "n": n, "nuevos": len(nuevas), "tiempo": round(time.time() - self.t0, 1)})

    def _ciclos(self, ciclo0=0):
        """Transformación desde el original + verificación independiente, hasta converger."""
        lim = self.ajustes
        limpias = 0
        ciclo = ciclo0
        while ciclo < ciclo0 + lim["max_ciclos"]:
            self.comprobar()
            mapa = self.registro.mapa()
            version = self.registro.version
            dest = os.path.join(self.carpeta, "ciclo-%d" % ciclo)
            shutil.rmtree(dest, ignore_errors=True)
            os.makedirs(dest)
            salida = os.path.join(dest, "salida" + self.ext)
            self.avisar(0.72, "ciclo %d: generando la copia seudonimizada desde el original…" % (ciclo + 1))
            with self.crono.medir("transformacion"):
                info = formatos.aplicar(self.ruta, salida, self.ext, mapa, {"logos": lim.get("logos", True)})
            self.salida = salida
            self.version_registro = version
            self.aplicado = {(e["texto"], e["marcador"]) for e in mapa}

            def avance(f, msg):
                self.avisar(0.75 + 0.24 * f, "ciclo %d · %s" % (ciclo + 1, msg))
            with self.crono.medir("verificacion"):
                v = verificacion.verificar(salida, self.ext, self.registro,
                                           {"ciclo": ciclo, "modelo_auditor": lim["modelo_auditor"],
                                            "modelo": lim.get("modelo")}, avance, self._cancelado)
            self.comprobar()
            # Lo hallado en la copia que también está en la lectura del original se incorpora con
            # normalidad. Lo que solo aparece en la copia (el OCR del original lo leyó mal) se
            # incorpora igualmente: la reconstrucción vuelve a leer las páginas escaneadas a otras
            # resoluciones y lo tapa; si aun así sigue en la siguiente copia, pasa a «restos» y el
            # documento queda para revisión humana.
            localizables = [d for d in v["nuevos"] if _localizable(d["texto"], self.texto_original)]
            ajenos, ruido = [], []
            for d in v["nuevos"]:
                if d in localizables or d["tipo"] == "F_NACIMIENTO":
                    continue   # una fecha que no está en la lectura del original es un artefacto del OCR
                variante = motor.variante_en(d["texto"], self.texto_original)
                if variante:
                    # el mismo dato leído de otra forma: se registran las dos lecturas
                    ajenos += [d, dict(d, texto=variante)]
                elif "regla" in (d.get("origen") or "") and motor.valido(d["texto"], d["tipo"]):
                    ajenos.append(d)      # identificador con forma válida que el OCR del original leyó mal
                else:
                    ruido.append(d)       # ruido del OCR sobre los propios tachones («TELEO0 008», «Diña»)
            nuevas = self.registro.incorporar(motor.filtrar_fechas(localizables, self.texto_original) + ajenos,
                                              self.doc["id"])
            graves = [i for i in v["incidencias"] if i.get("grave")]
            restos = sorted({r["marcador"] for r in v["restos"]})
            self.incidencias = v["incidencias"]
            self.pasadas.append({"tipo": "verificacion", "ciclo": ciclo + 1, "metodo": v["metodo"],
                                 "nuevos": len(nuevas), "restos": len(restos), "fuera_del_original": len(ajenos),
                                 "ruido_ocr": len(ruido),
                                 "incidencias_graves": len(graves), "tiempo": round(time.time() - self.t0, 1)})
            if nuevas:
                limpias = 0
            elif restos:
                # mismo registro aplicado y el dato sigue ahí: repetir no cambia nada (bucle sin progreso)
                self.estado = "revision"
                self.motivos.append("Hay %d dato(s) conocido(s) que siguen en la copia y no se han podido "
                                    "localizar para taparlos: %s." % (len(restos), ", ".join(restos)))
                return
            else:
                limpias += 1
            if graves and not nuevas:
                self.estado = "revision"
                self.motivos += [i["detalle"] for i in graves]
                return
            if limpias >= lim["limpias"] and not graves and not restos:
                self.estado = "sin_hallazgos"
                return
            ciclo += 1
        self.estado = "revision"
        self.motivos.append("Se ha alcanzado el máximo de %d ciclos sin dos verificaciones limpias seguidas."
                            % lim["max_ciclos"] if lim["limpias"] > 1 else
                            "Se ha alcanzado el máximo de %d ciclos sin una verificación limpia." % lim["max_ciclos"])

    def revisar_de_nuevo(self):
        """Coherencia de lote: el registro ha crecido después de cerrar este documento."""
        if self.estado not in ("sin_hallazgos", "revision") or self.texto_original is None:
            return False
        presentes = [e for e in self.registro.mapa()
                     if (e["texto"], e["marcador"]) not in self.aplicado
                     and motor.patron(e["texto"], e["tipo"]).search(self.texto_original)]
        if not presentes:
            self.version_registro = self.registro.version
            return False
        self.motivos = []
        self.estado = "procesando"
        try:
            self._ciclos(ciclo0=sum(1 for p in self.pasadas if p["tipo"] == "verificacion"))
        except Cancelado:
            self.estado = "cancelado"
        except TimeoutError as e:
            self.estado = "revision"
            self.motivos.append(str(e))
        return True


class TrabajoLote:
    """Seudonimización de un conjunto de archivos con un registro compartido."""

    def __init__(self, id_trabajo, documentos, registro, perfil="estandar", modelo=None, logos=True,
                 destino=None, al_terminar=None):
        self.id = id_trabajo
        self.registro = registro
        self.ajustes = dict(PERFILES[perfil], modelo=modelo, logos=logos, perfil=perfil)
        self.destino = destino
        self.carpeta = os.path.join(rutas.TRABAJO, "lote-%s" % id_trabajo)
        self.cancelar_evento = threading.Event()
        self.al_terminar = al_terminar
        self.estado = "pendiente"
        self.mensaje = ""
        self.progreso = 0.0
        self.inicio = None
        self.fin = None
        self.informe = None
        self.docs = [TrabajoDocumento(d, registro, self.ajustes, os.path.join(self.carpeta, str(i)),
                                      self._avisar, self.cancelar_evento.is_set)
                     for i, d in enumerate(documentos)]
        self._actual = 0

    def _avisar(self, tdoc, frac, mensaje):
        n = len(self.docs)
        i = self.docs.index(tdoc)
        self._actual = i
        self.progreso = min(0.99, (i + max(0.0, min(1.0, frac))) / max(n, 1))
        self.mensaje = "%s — %s" % (tdoc.doc["nombre"], mensaje) if n == 1 else \
            "Documento %d de %d · %s — %s" % (i + 1, n, tdoc.doc["nombre"], mensaje)

    def cancelar(self):
        self.cancelar_evento.set()

    def estado_publico(self):
        return {"id": self.id, "estado": self.estado, "mensaje": self.mensaje, "progreso": round(self.progreso, 3),
                "perfil": self.ajustes["perfil"], "modelo": self.ajustes.get("modelo"),
                "docs": [{"id": d.doc["id"], "nombre": d.doc["nombre"], "rel": d.doc["rel"], "estado": d.estado,
                          "estado_texto": ESTADOS[d.estado], "motivos": d.motivos, "pasadas": d.pasadas,
                          "incidencias": d.incidencias, "aviso": d.aviso, "paginas": d.doc.get("paginas")} for d in self.docs],
                "registro": self.registro.resumen(), "destino": self.destino, "informe": self.informe}

    def ejecutar(self):
        self.inicio = time.time()
        self.estado = "procesando"
        try:
            for d in self.docs:
                if self.cancelar_evento.is_set():
                    d.estado = "cancelado"
                    continue
                d.ejecutar()
            # coherencia entre documentos: una variante aparecida después obliga a revisar los anteriores
            for _ in range(self.ajustes["rondas_globales"]):
                if self.cancelar_evento.is_set():
                    break
                cambios = False
                for d in self.docs:
                    if d.version_registro < self.registro.version:
                        self.mensaje = "Coherencia del lote: revisando de nuevo «%s»…" % d.doc["nombre"]
                        cambios |= d.revisar_de_nuevo()
                if not cambios:
                    break
            self.mensaje = "Exportando las copias y el informe…"
            self.exportar()
            self.estado = "cancelado" if self.cancelar_evento.is_set() else "terminado"
            self.mensaje = ""
            self.progreso = 1.0
        except Exception as e:  # noqa
            traceback.print_exc()
            self.estado = "error"
            self.mensaje = "Error inesperado: %s" % str(e)[:200]
        finally:
            self.fin = time.time()
            shutil.rmtree(self.carpeta, ignore_errors=True)   # temporales con datos originales
            if self.al_terminar:
                try:
                    self.al_terminar(self)
                except Exception:
                    traceback.print_exc()

    # ------------------------------------------------------------ exportación
    def exportar(self):
        """Copias aprobadas y copias para revisión en carpetas separadas, nunca mezcladas.
        Los archivos con error no se exportan. El informe no contiene datos originales."""
        mapa = self.registro.mapa()
        os.makedirs(self.destino, exist_ok=True)
        for d in self.docs:
            if d.estado not in ("sin_hallazgos", "revision") or not d.salida:
                continue
            sub = "Aprobados" if d.estado == "sin_hallazgos" else "Para revisar"
            partes = [motor.reemplazar_texto(p, mapa) for p in os.path.dirname(d.doc["rel"]).replace("\\", "/").split("/") if p]
            carpeta = os.path.join(self.destino, sub, *partes)
            os.makedirs(carpeta, exist_ok=True)
            nombre = nombre_salida(os.path.splitext(d.doc["nombre"])[0] + d.ext, mapa)
            final = _ruta_libre(os.path.join(carpeta, nombre))
            shutil.copyfile(d.salida, final)
            d.final = final
            d.doc["rel_salida"] = os.path.relpath(final, self.destino)
            if d.ext_original in formatos.IMAGENES:
                # llegó como foto: también la imagen, re-renderizada y sin metadatos EXIF
                base = os.path.splitext(final)[0]
                formatos.pdf_a_imagenes(final, base)
        resumen = [d.resumen() for d in self.docs]
        cuenta = {k: sum(1 for d in self.docs if d.estado == k) for k in ESTADOS}
        self.informe = {
            "aplicacion": rutas.NOMBRE, "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "perfil": self.ajustes["perfil"], "modelo": self.ajustes.get("modelo"),
            "parametros": {k: self.ajustes[k] for k in ("min_detecciones", "max_ciclos", "limpias", "modelo_auditor")},
            "documentos": resumen, "recuento": cuenta, "registro": self.registro.resumen(),
            "duracion_s": round(time.time() - self.inicio, 1),
            "advertencia": ("«Sin hallazgos en las comprobaciones configuradas» no equivale a anonimización garantizada: "
                            "la ausencia de coincidencias no demuestra la ausencia de datos desconocidos, y la persona "
                            "puede seguir siendo identificable por el contexto. La seudonimización sigue siendo un "
                            "tratamiento de datos personales (art. 4.5 y considerando 26 RGPD). Revise los documentos "
                            "de alto riesgo antes de comunicarlos a terceros."),
        }
        with open(os.path.join(self.destino, "Informe de verificación.json"), "w", encoding="utf-8") as f:
            json.dump(self.informe, f, ensure_ascii=False, indent=2)
        with open(os.path.join(self.destino, "Informe de verificación.html"), "w", encoding="utf-8") as f:
            f.write(informe_html(self.informe))
        try:
            import certificado
            docs = []
            for d in self.docs:
                if getattr(d, "final", None):
                    docs.append({"copia": d.doc["rel_salida"], "estado_texto": ESTADOS[d.estado],
                                 "ciclos": sum(1 for p in d.pasadas if p["tipo"] == "verificacion"),
                                 "sha_original": certificado.huella(d.doc["ruta"]) if os.path.isfile(d.doc["ruta"]) else "—",
                                 "sha_copia": certificado.huella(d.final)})
            self.certificado = certificado.generar(self.informe, self.destino, docs)
        except Exception:
            traceback.print_exc()        # el certificado no debe impedir la entrega de las copias


def _ruta_libre(ruta):
    base, ext = os.path.splitext(ruta)
    i = 2
    while os.path.exists(ruta):
        ruta = "%s (%d)%s" % (base, i, ext)
        i += 1
    return ruta


def informe_html(inf):
    from html import escape as e
    filas = []
    for d in inf["documentos"]:
        pas = " · ".join(("D%d: %d" % (p["n"], p["nuevos"])) if p["tipo"] == "deteccion" else
                         ("V%d(%s): %d nuevos, %d restos" % (p["ciclo"], p["metodo"], p["nuevos"], p["restos"]))
                         for p in d["pasadas"])
        mot = "<br>".join(e(m) for m in d["motivos"]) or "—"
        filas.append("<tr class='%s'><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            d["estado"], e(d["rel"]), e(d["estado_texto"]), e(pas), mot))
    tipos = ", ".join("%s: %d" % (motor.ETIQUETAS.get(k, k), v) for k, v in sorted(inf["registro"]["por_tipo"].items()))
    return """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Informe de verificación</title>
<style>body{font:14px/1.5 -apple-system,Segoe UI,sans-serif;margin:32px;color:#1d1d1f}table{border-collapse:collapse;width:100%%}
td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}.sin_hallazgos td:nth-child(2){color:#1a7f37}
.revision td:nth-child(2){color:#b35900}.error td:nth-child(2){color:#c62828}.nota{background:#f6f3ea;padding:12px;border-radius:8px}</style></head>
<body><h1>Informe de verificación</h1><p>%s · perfil %s · modelo %s · %s s</p>
<p>Sin hallazgos: %d · Requieren revisión: %d · Error: %d · Cancelados: %d</p>
<p>Entidades seudonimizadas: %d (%s). Ambiguas para revisión: %d.</p>
<table><tr><th>Documento (nombre seudonimizado)</th><th>Estado</th><th>Pasadas</th><th>Motivos</th></tr>%s</table>
<p class="nota">%s</p></body></html>""" % (
        e(inf["fecha"]), e(inf["perfil"]), e(str(inf["modelo"])), inf["duracion_s"],
        inf["recuento"]["sin_hallazgos"], inf["recuento"]["revision"], inf["recuento"]["error"], inf["recuento"]["cancelado"],
        inf["registro"]["entidades"], e(tipos), inf["registro"]["ambiguas"], "".join(filas), e(inf["advertencia"]))
