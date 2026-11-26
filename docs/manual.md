# Manual de uso

## Requisitos

| | Mac | Windows |
|---|---|---|
| Equipo | Chip Apple (M1 o posterior). Los Mac con Intel no sirven | Windows 10 22H2 u 11, 64 bits |
| Memoria | 16 GB como mínimo; 24 GB o más para trabajar holgado | 16 GB como mínimo. Con una tarjeta gráfica de 12 GB o más va mucho más rápido |
| Disco | 20 GB libres (el modelo ocupa unos 8 GB) | 20 GB libres, mejor en SSD |
| Internet | Solo la primera vez, para descargar Ollama y el modelo | Igual |

## Instalar

**Mac.** Abre `AureaAsistenteLocal-<versión>-Mac.dmg` y arrastra la aplicación a Aplicaciones. La primera vez, macOS la bloquea porque no está certificada por Apple, un trámite de pago que no indica que sea peligrosa. Para permitirla:

1. En el aviso, pulsa «Aceptar».
2. Abre Ajustes del Sistema > Privacidad y seguridad.
3. Pulsa «Abrir igualmente» y confirma con tu contraseña.

**Windows.** Ejecuta `AureaAsistenteLocal-<versión>-Windows.exe`. Si aparece «Windows protegió su PC», pulsa «Más información» y después «Ejecutar de todas formas». La instalación es solo para tu usuario y no pide permisos de administrador.

**Primera puesta en marcha.** Si falta Ollama, la aplicación lo indica con el botón «Instalar Ollama», que lo descarga de ollama.com. Después, en «Modelos», elige un modelo y pulsa «Descargar». Se recomienda **gemma4:12b**, de unos 8 GB. La aplicación comprueba antes el espacio libre y te enseña la licencia del modelo. No descarga nada sin que lo pidas.

## Trabajar

1. **Crea un proyecto** por asunto. Elige el modelo, la verificación por defecto y si quieres guardar la tabla de correspondencias cifrada. Un proyecto temporal se borra al cerrar la aplicación.
2. **Añade la carpeta del expediente** o algunos archivos, con los botones o arrastrándolos a la ventana. Los originales nunca se modifican ni se mueven. La pestaña Archivos indica cuáles se pueden tratar y por qué no los demás.
3. **Pide lo que necesites** en la conversación: «Seudonimiza toda la carpeta y conserva el formato», «¿Qué archivos hay?», «Resume la carta de despido».
4. Cuando la petición crea archivos, Áurea muestra un **plan** con el alcance. Elige la verificación (estándar o intensiva) y pulsa «Seudonimizar».
5. En **Operaciones** se ve cada archivo con su pista de pasadas: D1 y D2 son las detecciones, V1, V2… las verificaciones. El dorado indica que la pasada encontró datos nuevos; el verde, que no encontró nada; el ámbar, que quedan restos o incidencias.
6. En **Revisión** están todos los datos con su marcador:
   - **Descartar** lo que no sea un dato personal: no volverá a proponerse.
   - **Añadir** a mano lo que se haya escapado.
   - **Regenerar copias** vuelve a generarlas y verificarlas sin repetir la detección.

## Resultados

En la carpeta de resultados del proyecto (por defecto `~/Áurea Asistente/<proyecto>/<fecha>`):

- **Aprobados/**: copias sin hallazgos en las comprobaciones configuradas.
- **Para revisar/**: copias con algún motivo de revisión, que se explica en el informe. Revísalas antes de usarlas.
- **Informe de verificación** (HTML y JSON), sin datos originales.

«Sin hallazgos en las comprobaciones configuradas» **no es una garantía**. La seudonimización sigue siendo tratamiento de datos personales, y una persona puede ser identificable por el contexto. Revisa los expedientes de alto riesgo antes de comunicarlos a terceros.

## Tabla de correspondencias

Si el proyecto la guarda, va cifrada en este ordenador, con la clave en el Llavero (Mac) o en el Administrador de credenciales (Windows). «Exportar tabla…», en Revisión, la saca en claro para guardarla en el expediente: **no la subas nunca a ninguna IA**. Al borrar el proyecto se destruyen la tabla y su clave.

## Si algo falla

- **«Falta Ollama»** o **«Ollama detenido»**: abre Ollama, o pulsa «Instalar Ollama».
- **El modelo va muy lento**: cierra programas pesados. Con 16 GB se carga un solo modelo cada vez.
- **Un documento con error**: el informe explica el motivo, por ejemplo que esté cifrado o dañado, o tenga macros.
- **Registro técnico**, sin texto de documentos: en Mac, `~/Library/Application Support/AureaAsistente/registro.log`; en Windows, `%LOCALAPPDATA%\AureaAsistente\registro.log`.
