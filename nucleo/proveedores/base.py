# -*- coding: utf-8 -*-
"""Interfaz común de los proveedores de modelos locales.

El resto de la aplicación solo habla con esta interfaz, de modo que cambiar de modelo (o de
motor: Ollama hoy, llama.cpp o LM Studio mañana) no exige tocar el motor documental. Cada
modelo declara sus capacidades; la aplicación decide el flujo según ellas (por ejemplo, si el
modelo no admite llamadas a herramientas, el asistente usa un clasificador de intención)."""
import json
import re


class ErrorProveedor(Exception):
    """El motor de modelos no responde o ha devuelto un error."""


class ProveedorModelos:
    nombre = "base"

    # -- inventario
    def disponible(self) -> bool:
        raise NotImplementedError

    def listar(self) -> list:
        """[{nombre, tamano, familia, parametros, cuantizacion, capacidades:[...]}]"""
        raise NotImplementedError

    def capacidades(self, modelo) -> set:
        """Subconjunto de {"completion", "tools", "vision", "thinking", "embedding"}."""
        raise NotImplementedError

    # -- inferencia
    def chat(self, modelo, mensajes, herramientas=None, opciones=None, flujo=False):
        """Sin flujo devuelve {"contenido": str, "llamadas": [{"nombre", "argumentos"}]}.
        Con flujo devuelve un generador de trozos {"contenido": str} y un último {"fin": True, ...}."""
        raise NotImplementedError

    def estructurado(self, modelo, mensajes, esquema, opciones=None) -> dict:
        """Respuesta que cumple un JSON Schema. Si el modelo no lo cumple, se intenta
        rescatar el primer objeto JSON del texto; si tampoco, se devuelve {}."""
        raise NotImplementedError

    # -- gestión
    def descargar(self, modelo, progreso=None):
        raise NotImplementedError

    def borrar(self, modelo):
        raise NotImplementedError

    def descargar_de_memoria(self, modelo):
        """Libera la memoria del modelo cuando termina un lote."""


def json_de_texto(contenido):
    try:
        return json.loads(contenido)
    except Exception:
        m = re.search(r"\{.*\}", contenido or "", re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}
