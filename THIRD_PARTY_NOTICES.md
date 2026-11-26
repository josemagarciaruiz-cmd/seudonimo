# Componentes de terceros

Inventario de lo que se redistribuye en los instaladores. Las versiones exactas son las de `requisitos/` y `escritorio/src-tauri/Cargo.lock`. El SBOM en formato CycloneDX se genera en cada versión (`empaquetado/sbom.py`) y se adjunta a la *release*.

## Incluidos en el instalador

| Componente | Uso | Licencia |
|---|---|---|
| Python 3.13 (python-build-standalone en Mac; distribución *embeddable* oficial en Windows) | Intérprete del servicio local | PSF License 2.0 |
| Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, click | Servicio HTTP local | BSD-3-Clause |
| blinker | Dependencia de Flask | MIT |
| requests, urllib3, idna, charset-normalizer, certifi | Conexión con Ollama en 127.0.0.1 y descargas | Apache-2.0, MIT, BSD-3-Clause, MIT y MPL-2.0 |
| lxml (con libxml2 y libxslt) | Lectura y escritura de OOXML | BSD-3-Clause (libxml2: MIT) |
| Pillow | Imágenes y rasterizado | MIT-CMU (HPND) |
| pypdfium2 con PDFium | PDF | Apache-2.0 o BSD-3-Clause; PDFium: BSD-3-Clause y componentes propios |
| cryptography (con cffi y pycparser) | Cifrado de las tablas de correspondencias | Apache-2.0 o BSD-3-Clause |
| keyring y jaraco.* | Clave en el Llavero o el Administrador de credenciales | MIT |
| pywin32-ctypes (Windows) | Administrador de credenciales | BSD-3-Clause |
| pyobjc-framework-Vision (Mac) | OCR de macOS | MIT |
| Tesseract OCR 5 con los datos `spa`, `eng` y `osd` (Windows) | OCR | Apache-2.0 |
| Source Serif 4 | Tipografía de la interfaz | SIL Open Font License 1.1 (`interfaz/fuentes/OFL-SourceSerif4.txt`) |
| Tauri 2 y sus *crates* | Ventana de escritorio | MIT o Apache-2.0 (los detalles por *crate* van en el SBOM) |
| whisper.cpp b5454 (`whisper-cli`, con ggml) | Dictado por voz, transcripción en el propio ordenador | MIT (`licencias/LICENSE-whisper.cpp.txt`) |

**No se usa PyMuPDF** (AGPL-3.0 o licencia comercial).

## No incluidos: se descargan de sus fuentes oficiales solo cuando el usuario lo pide

| Componente | Origen | Licencia |
|---|---|---|
| Ollama | ollama.com | MIT |
| Modelos de voz Whisper `small` y `large-v3-turbo` en formato ggml | huggingface.co/ggerganov/whisper.cpp (pesos de OpenAI Whisper) | MIT |
| Gemma 4 (`gemma4:12b` y otros tamaños) | Biblioteca de Ollama | Apache License 2.0, según la ficha del modelo (`ollama show`). La aplicación muestra la licencia de cada modelo instalado antes de usarlo |
| Otros modelos (Qwen 3.5…) | Biblioteca de Ollama | La de su ficha. Código abierto no equivale a pesos abiertos: compruébese antes de un uso profesional |
