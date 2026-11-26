# Áurea Asistente Local

Asistente documental jurídico **de escritorio**, al estilo de las aplicaciones de Claude o ChatGPT, que funciona **entero en el ordenador del usuario** con modelos locales. Tiene proyectos, conversaciones y carpetas adjuntas, y su primer caso de uso es la **seudonimización de expedientes jurídico-laborales con auditoría multipasada verificable**.

Ningún documento sale del equipo: la lectura, el OCR, el modelo (por defecto Gemma 4 · 12B a través de Ollama) y la verificación son locales.

> Estado: **en desarrollo** (versión 0.x). Plan técnico de referencia: correos «Plan técnico detallado» y «Anexo al plan técnico: seudonimización autónoma multipasada» (25/11/2026), resumidos en `docs/`.

## Qué hace

- **Proyectos** con carpetas y archivos autorizados por el usuario (diálogo del sistema), **conversaciones** y **selector de modelo**.
- El asistente entiende órdenes como «Seudonimiza toda esta carpeta, mantén la coherencia de las etiquetas y conserva el formato». Prepara un **plan** con su alcance y el usuario lo confirma.
- **Motor multipasada** (anexo técnico): dos pasadas de detección y ciclos de transformación y verificación independiente desde el original inmutable. Termina por convergencia, por límites o por error, nunca porque el modelo diga que está limpio.
- Estados honestos: «Sin hallazgos en las comprobaciones configuradas», «Requiere revisión» o «Error de procesamiento». Nunca «anonimización garantizada».
- **Etiquetas estables por proyecto** (`[PERSONA_001]`, `[DNI_002]`…) compartidas entre todos los documentos. La tabla de correspondencias es **opcional y va cifrada**, con la clave en el Llavero de Mac o en el Administrador de credenciales de Windows.
- **Gestor de modelos**: ver los instalados, descargar otros (con comprobación de espacio y la licencia a la vista) y elegir el modelo por proyecto.

## Arquitectura

| Capa | Dónde | Qué |
|---|---|---|
| Ventana de escritorio | `escritorio/` | Tauri 2 (WebView del sistema). Arranca el servicio local y abre los diálogos nativos. |
| Interfaz | `interfaz/` | HTML, CSS y JS sin frameworks: proyectos, conversaciones, archivos, operaciones, revisión y modelos. |
| Servicio local | `nucleo/servidor.py` | Flask en 127.0.0.1, puerto libre y token efímero; valida Host y Origin. |
| Asistente | `nucleo/asistente.py`, `nucleo/herramientas.py` | Llamadas a herramientas registradas con esquema; clasificador de intención si el modelo no las admite. |
| Proveedores | `nucleo/proveedores/` | Interfaz común (`listar`, `chat`, `estructurado`, `descargar`…). Primer adaptador: Ollama. |
| Multipasada | `nucleo/multipasada.py`, `nucleo/verificacion.py`, `nucleo/registro.py` | Controlador determinista, verificación independiente y registro de entidades del proyecto. |
| Motor documental | `nucleo/motor.py`, `formatos.py`, `ocr.py`, `pdfdoc.py` | Heredado de Áurea Anonimus 2.1.0: reglas, OCR (Vision en Mac, Tesseract en Windows) y PDF con pypdfium2. |
| Persistencia | `nucleo/almacen.py`, `nucleo/cifrado.py` | SQLite sin texto de documentos; tabla de correspondencias cifrada (Fernet). |

## Desarrollo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requisitos/mac.txt          # o requisitos/windows.txt
python nucleo/servidor.py --navegador      # interfaz en el navegador, sin Tauri
```

Ventana de escritorio: `cd escritorio && npm install && npm run tauri dev` (necesita Rust y Node).

Pruebas: `python -m pytest pruebas` (unitarias) y `python pruebas/evaluar.py` (métricas sobre el corpus sintético).

## Privacidad

- Los datos de trabajo van a la carpeta de datos de la aplicación y los resultados a `~/Áurea Asistente`, fuera de carpetas sincronizadas con la nube. Si el usuario elige una carpeta sincronizada, la aplicación lo advierte.
- La base de datos no guarda el texto de los documentos. Los temporales con datos originales se borran al terminar cada lote. Los proyectos temporales se borran al cerrar.
- **No subas nunca a este repositorio documentos de clientes ni resultados con datos reales.**

© José María García Ruiz · josemaria.ai. Todos los derechos reservados. Licencias de terceros en `THIRD_PARTY_NOTICES.md`.
