# Fase 0 · Auditoría del motor de partida (Áurea Anonimus 2.1.0)

Fecha: 26/11/2026. Equipo de referencia: Mac mini M4, 16 GB de memoria unificada, macOS 26.5.

## Entorno comprobado

| Elemento | Valor |
|---|---|
| Ollama | instalado; modelo `gemma4:12b` (ID c7597fc90b86, 7,7 GB) |
| Modelo | arquitectura `gemma4_unified`, 12,4 B parámetros, cuantización **nvfp4**, contexto máximo 262.144 tokens |
| Capacidades declaradas (`ollama show`) | completion, **vision**, audio, **tools**, thinking |
| Licencia del modelo (`ollama show`) | Apache License 2.0 |
| Herramientas de desarrollo | Rust 1.95, Node 25.9, Xcode Command Line Tools, `gh` con la cuenta del repositorio |
| Disco libre | unos 36 GB |

## Inventario del motor heredado

| Módulo | Función | Dependencias |
|---|---|---|
| `motor.py` | Reglas fijas (DNI/NIE, NIF, NAF, CCC, IBAN, teléfono, correo, matrícula, CSV/CEA, registro, domicilio con tipo de vía), llamada al modelo por fragmentos con segunda lectura de costuras, filtro de fechas de nacimiento frente a antigüedad, búsqueda de cada dato en todas sus variantes (orden de nombre y apellidos, tildes, separadores) | requests (ahora vía `proveedores`) |
| `formatos.py` | Lectura y escritura de PDF, OOXML (Word, Excel, PowerPoint, editados directamente en XML), texto y CSV; conversión de .doc/.xls/.ppt/.rtf/.odt e imágenes; tapado de logotipos y sellos | lxml, Pillow |
| `pdfdoc.py` | PDF con **pypdfium2** (no PyMuPDF, por la licencia AGPL): las páginas con datos se **rasterizan y se reconstruyen** con una capa de texto solo con las palabras visibles, de modo que el texto tapado desaparece del contenido extraíble | pypdfium2, Pillow |
| `ocr.py` | Vision (Mac) o Tesseract (Windows, con doble lectura psm 3 + psm 12) | pyobjc-framework-Vision / Tesseract |

**Cómo se detectan, localizan y modifican los datos.** El modelo devuelve fragmentos literales y el programa descarta todo lo que no está en el texto. Cada dato se convierte en una expresión que reconoce sus variantes. En PDF nativos, la posición sale de las palabras de pypdfium2. En páginas escaneadas sale de las cajas del OCR, con un repaso a 360 y 420 ppp tras tapar. En OOXML el texto se sustituye dentro de los *runs*, conservando el formato.

## Decisiones de la Fase 0

1. **No se reinstala nada que funcione.** Se conservan Ollama, gemma4:12b y el motor documental, que pasa a ser una biblioteca del servicio local.
2. **Ventana de escritorio con Tauri 2**, como recomienda el plan: el Mac ya tiene Rust y Node.
3. **Sin PyMuPDF.** La redacción segura de PDF se mantiene con el enfoque actual (rasterizar las páginas afectadas y reconstruirlas desde el original inmutable). La verificación comprueba además que no queden revisiones incrementales, adjuntos ni metadatos con datos.
4. Se eliminan del instalador python-docx, python-pptx y openpyxl: el motor no los usa (edita el XML directamente). Se añaden cryptography y keyring para la tabla cifrada.
5. Marcadores con tres cifras (`[PERSONA_001]`), estables por proyecto.

## Pendiente de medir en el M4 (Fase 2)

Tiempo por página (OCR, extracción e inferencia por separado), memoria y presión de memoria, y nuevas entidades por pasada con 1, 2, 3 y 5 pasadas sobre el corpus sintético (`pruebas/`). Los resultados se anotan en `docs/metricas.md`.
