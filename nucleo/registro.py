# -*- coding: utf-8 -*-
"""Registro de entidades de un proyecto.

Un mismo registro se comparte entre todos los documentos del proyecto, de modo que
[PERSONA_001] es la misma persona en los veinte expedientes. Las etiquetas son estables: una
vez asignadas, no cambian aunque aparezcan datos nuevos.

Reglas de agrupación (evitar fusionar homónimos):
- Dos formas de PERSONA se agrupan solo si las palabras de una están contenidas en las de la
  otra y la coincidencia apunta a UNA sola persona ya registrada. «Ferrer» suelto con dos
  personas apellidadas Ferrer no se agrupa con ninguna: recibe su propia etiqueta y se marca
  como ambigua para revisión humana.
- Los identificadores (DNI, IBAN, teléfonos…) se comparan sin separadores.

Lo que el usuario descarta (un falso positivo) queda anotado y no vuelve a proponerse en las
pasadas siguientes; así la multipasada no reintroduce lo que se revisó a mano."""
import json
import threading
import time

import motor


def _orden_natural(m):
    import re
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", m)]


def _apellidos(forma):
    """Palabras en posición de apellido: «Lucía Ferrer Gil» → {ferrer, gil};
    «FERRER GIL, LUCÍA» → {ferrer, gil}; «Lucía Ferrer» → {ferrer}."""
    k = motor.clave(forma)
    if "," in k:
        return set(k.split(",", 1)[0].split())
    pal = k.split()
    if len(pal) >= 3:
        return set(pal[-2:])
    return set(pal[-1:]) if len(pal) == 2 else set()


class Registro:
    def __init__(self, proyecto=None):
        self.proyecto = proyecto
        self.entidades = []        # [{id, marcador, tipo, formas:[...], origenes:[...], docs:[...], activo, ambigua}]
        self.contadores = {}
        self.descartados = set()   # claves de datos que el usuario ha dicho que no son personales
        self.version = 0           # sube cada vez que entra una entidad o forma nueva
        self._cerrojo = threading.RLock()
        self._indice = {}          # clave_dato(forma) -> entidad

    # ------------------------------------------------------------ consulta
    def buscar(self, texto):
        return self._indice.get(motor.clave_dato(texto))

    def por_marcador(self, marcador):
        for e in self.entidades:
            if e["marcador"] == marcador:
                return e
        return None

    def mapa(self, solo_activas=True):
        """Lista plana de formas con su marcador, en el formato que usa el motor."""
        res = []
        for e in self.entidades:
            if solo_activas and not e["activo"]:
                continue
            for f in e["formas"]:
                res.append({"texto": f, "tipo": e["tipo"], "marcador": e["marcador"], "id": e["id"]})
        return res

    def resumen(self):
        """Sin datos originales: solo marcadores, tipos y recuentos (apto para informes)."""
        por_tipo = {}
        for e in self.entidades:
            if e["activo"]:
                por_tipo[e["tipo"]] = por_tipo.get(e["tipo"], 0) + 1
        return {"entidades": sum(por_tipo.values()), "por_tipo": por_tipo,
                "ambiguas": sum(1 for e in self.entidades if e.get("ambigua") and e["activo"])}

    # ------------------------------------------------------------ alta
    def _nuevo_marcador(self, tipo):
        self.contadores[tipo] = self.contadores.get(tipo, 0) + 1
        return "[%s_%03d]" % (tipo, self.contadores[tipo])

    def _persona_compatible(self, palabras):
        """Personas registradas cuyas palabras contienen estas, o están contenidas en ellas."""
        candidatas = []
        conj = set(palabras)
        for e in self.entidades:
            if e["tipo"] != "PERSONA" or not e["activo"]:
                continue
            for f in e["formas"]:
                pal_f = motor.clave(f).replace(",", " ").split()
                if conj <= set(pal_f):
                    pequena, grande = palabras, pal_f
                elif set(pal_f) <= conj:
                    pequena, grande = pal_f, palabras
                else:
                    continue
                if len(set(pequena)) == 1 and pequena[0] not in _apellidos(f if pequena is palabras else " ".join(palabras)):
                    continue  # un nombre de pila suelto no basta: «Lucía» puede ser otra Lucía
                candidatas.append(e)
                break
        return candidatas

    def incorporar(self, entidades, doc=None):
        """Añade entidades detectadas. Devuelve las que son NUEVAS (entidad o forma nueva)."""
        nuevas = []
        with self._cerrojo:
            # las formas largas primero: «María López Herrera» antes que «López Herrera»
            orden = sorted(entidades, key=lambda e: (e.get("tipo") != "PERSONA", -len(e.get("texto", ""))))
            for d in orden:
                texto = str(d.get("texto", "")).strip()
                tipo = d.get("tipo") if d.get("tipo") in motor.TIPOS else "OTRO"
                k = motor.clave_dato(texto)
                if not k or len(texto) < 2 or k in self.descartados or motor.MARCADOR.search(texto):
                    continue
                ya = self._indice.get(k)
                if ya:
                    if doc is not None and doc not in ya["docs"]:
                        ya["docs"].append(doc)
                    continue
                destino = None
                if tipo == "PERSONA":
                    cand = self._persona_compatible(motor.clave(texto).replace(",", " ").split())
                    if len(cand) == 1:
                        destino = cand[0]
                    elif len(cand) > 1:
                        d = dict(d, ambigua=True)
                if destino is None:
                    destino = {"id": len(self.entidades), "marcador": self._nuevo_marcador(tipo), "tipo": tipo,
                               "formas": [], "origenes": [], "docs": [], "activo": True,
                               "ambigua": bool(d.get("ambigua")), "alta": time.time()}
                    self.entidades.append(destino)
                destino["formas"].append(texto)
                origen = d.get("origen") or "Regla"
                if origen not in destino["origenes"]:
                    destino["origenes"].append(origen)
                if doc is not None and doc not in destino["docs"]:
                    destino["docs"].append(doc)
                self._indice[k] = destino
                nuevas.append({"texto": texto, "tipo": tipo, "marcador": destino["marcador"],
                               "origen": origen, "id": destino["id"]})
            if nuevas:
                self.version += 1
        return nuevas

    # ------------------------------------------------------------ revisión humana
    def descartar(self, id_entidad):
        """El usuario dice que no es un dato personal: se desactiva y no vuelve a proponerse."""
        with self._cerrojo:
            e = self.entidades[id_entidad]
            e["activo"] = False
            for f in e["formas"]:
                self.descartados.add(motor.clave_dato(f))
            self.version += 1

    def reactivar(self, id_entidad):
        with self._cerrojo:
            e = self.entidades[id_entidad]
            e["activo"] = True
            for f in e["formas"]:
                self.descartados.discard(motor.clave_dato(f))
            self.version += 1

    def anadir_manual(self, texto, tipo, doc=None):
        return self.incorporar([{"texto": texto, "tipo": tipo, "origen": "Manual"}], doc)

    # ------------------------------------------------------------ persistencia (siempre cifrada)
    def a_bytes(self):
        return json.dumps({"entidades": self.entidades, "contadores": self.contadores,
                           "descartados": sorted(self.descartados), "version": self.version},
                          ensure_ascii=False).encode("utf-8")

    @classmethod
    def de_bytes(cls, datos, proyecto=None):
        d = json.loads(datos.decode("utf-8"))
        r = cls(proyecto)
        r.entidades = d.get("entidades", [])
        r.contadores = d.get("contadores", {})
        r.descartados = set(d.get("descartados", []))
        r.version = d.get("version", 0)
        for e in r.entidades:
            for f in e["formas"]:
                r._indice[motor.clave_dato(f)] = e
        return r

    def tabla(self):
        """Tabla de correspondencias (CON datos originales): solo para exportación explícita."""
        filas = []
        for e in sorted(self.entidades, key=lambda e: _orden_natural(e["marcador"])):
            if not e["activo"]:
                continue
            filas.append({"marcador": e["marcador"], "tipo": motor.ETIQUETAS.get(e["tipo"], e["tipo"]),
                          "formas": e["formas"], "detectado_por": e["origenes"], "documentos": len(e["docs"]),
                          "ambigua": bool(e.get("ambigua"))})
        return filas
