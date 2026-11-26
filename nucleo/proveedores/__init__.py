# -*- coding: utf-8 -*-
"""Proveedores de modelos locales. Hoy: Ollama. La interfaz está en base.py."""
from .base import ErrorProveedor, ProveedorModelos  # noqa: F401
from .ollama import Ollama

_ACTUAL = Ollama()


def actual():
    return _ACTUAL


# Catálogo orientativo para el gestor de modelos. Las etiquetas y sus licencias deben
# comprobarse en https://ollama.com/library antes de cada versión; el usuario puede escribir
# cualquier otra etiqueta. «memoria» es la memoria del equipo recomendada, en GB.
# Etiquetas comprobadas en ollama.com el 26/11/2026; la licencia de cada modelo instalado se
# lee de su propia ficha (/api/show) y se muestra antes de usarlo.
CATALOGO = [
    {"nombre": "gemma4:12b", "descripcion": "Gemma 4 · 12B (Google). Modelo de referencia: texto e imágenes, herramientas. Unos 8 GB.",
     "memoria": 16, "gb": 7.7, "recomendado": True},
    {"nombre": "gemma4:e4b", "descripcion": "Gemma 4 · E4B. Más ligero y rápido, algo menos preciso. Para equipos justos de memoria. Unos 9,5 GB.",
     "memoria": 16, "gb": 9.5},
    {"nombre": "gemma4:26b", "descripcion": "Gemma 4 · 26B (mezcla de expertos). Más preciso; solo con 32 GB de memoria o más. Unos 18 GB.",
     "memoria": 32, "gb": 18},
    {"nombre": "qwen3.5:9b", "descripcion": "Qwen 3.5 · 9B (Alibaba). Alternativa con texto, imágenes y herramientas, para comparar resultados.",
     "memoria": 16, "gb": None},
]
