# Seudónimo

Asistente documental jurídico **de escritorio**, al estilo de las aplicaciones de Claude o ChatGPT, que funciona **entero en el ordenador del usuario** con modelos locales. Tiene expedientes, conversaciones (también por voz) y carpetas adjuntas, y su primer caso de uso es la **seudonimización de expedientes jurídico-laborales con auditoría multipasada verificable**.

Ningún documento sale del equipo: la lectura, el OCR, el modelo (por defecto Gemma 4 · 12B a través de Ollama) y la verificación son locales.

> Estado: **en desarrollo** (versión 0.x). Plan técnico de referencia: correos «Plan técnico detallado» y «Anexo al plan técnico: seudonimización autónoma multipasada» (25/11/2026), resumidos en `docs/`.

## Qué hace

- **Expedientes** (en el código, «proyectos») con carpetas y archivos autorizados por el usuario, **conversaciones** con el asistente, por escrito o dictadas, y una sola **lista de documentos** con «Abrir copia» y «⋯». Expedientes y conversaciones se renombran y se eliminan desde su menú «⋯», y una conversación puede **moverse a otro expediente**.
- **Mesa de revisión** a pantalla completa para tapar a mano lo que se escape (seleccionándolo) y descartar falsos positivos; **listas del despacho**, **tipo de asunto**, **correos y chats de WhatsApp**, **carpeta vigilada**, **certificado de seudonimización** en PDF y **«Usar con otra IA»** (copiar las copias y volver a poner los nombres en la respuesta).
- **Dictado por voz**: el botón «Dictar» (⌘⇧D) transcribe con Whisper (whisper.cpp) en el propio ordenador y deja el texto en la caja de mensaje para revisarlo antes de enviarlo. El modelo de voz se descarga una sola vez, cuando se pide.
- El asistente entiende órdenes como «Seudonimiza toda esta carpeta, mantén la coherencia de las etiquetas y conserva el formato». Prepara un **plan** con su alcance y el usuario lo confirma.
- **Motor multipasada** (anexo técnico): dos pasadas de detección y ciclos de transformación y verificación independiente desde el original inmutable. Termina por convergencia, por límites o por error, nunca porque el modelo diga que está limpio.
- Estados honestos: «Sin hallazgos en las comprobaciones configuradas», «Requiere revisión» o «Error de procesamiento». Nunca «anonimización garantizada».
- **Etiquetas estables por proyecto** (`[PERSONA_001]`, `[DNI_002]`…) compartidas entre todos los documentos. La tabla de correspondencias es **opcional y va cifrada**, con la clave en el Llavero de Mac o en el Administrador de credenciales de Windows.
- **Gestor de modelos**: ver los instalados, descargar otros (con comprobación de espacio y la licencia a la vista) y elegir el modelo por expediente.

## Arquitectura

| Capa | Dónde | Qué |
|---|---|---|
| Ventana de escritorio | `escritorio/` | Tauri 2 (WebView del sistema). Arranca el servicio local y abre los diálogos nativos. |
| Interfaz | `interfaz/` | HTML, CSS y JS sin frameworks: expedientes, chat, lista de documentos, revisión de copias y modelos. |
| Servicio local | `nucleo/servidor.py` | Flask en 127.0.0.1, puerto libre y token efímero; valida Host y Origin. |
| Asistente | `nucleo/asistente.py`, `nucleo/herramientas.py` | Llamadas a herramientas registradas con esquema; clasificador de intención si el modelo no las admite. |
| Proveedores | `nucleo/proveedores/` | Interfaz común (`listar`, `chat`, `estructurado`, `descargar`…). Primer adaptador: Ollama. |
| Multipasada | `nucleo/multipasada.py`, `nucleo/verificacion.py`, `nucleo/registro.py` | Controlador determinista, verificación independiente y registro de entidades del proyecto. |
| Motor documental | `nucleo/motor.py`, `formatos.py`, `ocr.py`, `pdfdoc.py` | Heredado de Áurea Anonimus 2.1.0, la versión anterior de la herramienta: reglas, OCR (Vision en Mac, Tesseract en Windows) y PDF con pypdfium2. |
| Dictado | `nucleo/voz.py` | whisper-cli incluido en el instalador; el audio solo existe en un temporal que se borra al transcribir. |
| Persistencia | `nucleo/almacen.py`, `nucleo/cifrado.py` | SQLite sin texto de documentos; tabla de correspondencias cifrada (Fernet). |

## Desarrollo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requisitos/mac.txt          # o requisitos/windows.txt
python nucleo/servidor.py --navegador      # interfaz en el navegador, sin Tauri
```

Ventana de escritorio: `cd escritorio && npm install && npm run tauri dev` (necesita Rust y Node).

Pruebas:

```bash
python -m pytest pruebas                                                    # unitarias
python pruebas/corpus/generar_corpus.py /tmp/corpus                         # corpus sintético etiquetado
python pruebas/medir.py estandar /tmp/corpus /tmp/lote                      # con el modelo real
python pruebas/evaluar.py /tmp/corpus /tmp/lote                             # recall, conservación y precisión
```

## Instaladores

- **Mac** (en un Mac con chip Apple): `zsh empaquetado/mac/construir.sh` → `salida/Seudonimo-<versión>-Mac.dmg` y el SBOM. El dictado usa `whisper-cli`, que compila `empaquetado/mac/whisper.sh` (cmake) si no está en `descargas/`.
- **Windows** (desde un Mac, con MinGW-w64): `bash empaquetado/windows/preparar_recursos.sh` y después `zsh empaquetado/windows/construir_desde_mac.sh` → `salida/Seudonimo-<versión>-Windows.exe`. Instalación por usuario, sin permisos de administrador.

Los instaladores no están firmados con certificado de Apple ni de Microsoft (firmar y notarizar tiene coste y requisitos de cuenta), así que el sistema avisa la primera vez. Ver `docs/manual.md`.

Documentación: `docs/00-auditoria-motor.md`, `docs/multipasada.md`, `docs/matriz-formatos.md`, `docs/proteccion-datos.md`, `docs/manual.md` y `docs/metricas.md`.

## Privacidad

- Los datos de trabajo van a la carpeta de datos de la aplicación y los resultados a `~/Seudónimo`, fuera de carpetas sincronizadas con la nube. Si el usuario elige una carpeta sincronizada, la aplicación lo advierte.
- La base de datos no guarda el texto de los documentos. Los temporales con datos originales se borran al terminar cada lote. Los proyectos temporales se borran al cerrar.
- **No subas nunca a este repositorio documentos de clientes ni resultados con datos reales.**

## Licencia

© 2026 José María García Ruiz · josemaria.ai. Se distribuye con la **PolyForm Shield License 1.0.0** (texto completo en inglés en `LICENSE.md`; el texto en inglés es el que vale).

En resumen y sin valor legal:
- **Puedes** usar Seudónimo gratis para cualquier fin, también en tu despacho o empresa, modificarlo para tu propio uso y compartirlo.
- **No puedes** usarlo, ni una versión modificada, para ofrecer un producto o servicio que compita con Seudónimo, aunque sea gratis. Por ejemplo, no puedes cambiarle el nombre y venderlo, ni montar con él un servicio de seudonimización para terceros.

Licencias de terceros en `THIRD_PARTY_NOTICES.md`.

Hasta la versión 0.1.1 la aplicación se llamaba «Áurea Asistente Local». La 0.2.0 traslada sola sus datos, resultados y claves al nombre nuevo la primera vez que se abre.
