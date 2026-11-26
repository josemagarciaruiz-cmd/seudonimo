# Manual de uso

## Requisitos

| | Mac | Windows |
|---|---|---|
| Equipo | Chip Apple (M1 o posterior). Los Mac con Intel no sirven | Windows 10 22H2 u 11, 64 bits |
| Memoria | 16 GB como mínimo; 24 GB o más para trabajar holgado | 16 GB como mínimo. Con una tarjeta gráfica de 12 GB o más va mucho más rápido |
| Disco | 20 GB libres (el modelo ocupa unos 8 GB) | 20 GB libres, mejor en SSD |
| Internet | Solo la primera vez, para descargar Ollama y el modelo | Igual |

## Instalar

**Mac.** Abre `Seudonimo-<versión>-Mac.dmg` y arrastra la aplicación a Aplicaciones. La primera vez, macOS la bloquea porque no está certificada por Apple, un trámite de pago que no indica que sea peligrosa. Para permitirla:

1. En el aviso, pulsa «Aceptar».
2. Abre Ajustes del Sistema > Privacidad y seguridad.
3. Pulsa «Abrir igualmente» y confirma con tu contraseña.

**Windows.** Ejecuta `Seudonimo-<versión>-Windows.exe`. Si aparece «Windows protegió su PC», pulsa «Más información» y después «Ejecutar de todas formas». La instalación es solo para tu usuario y no pide permisos de administrador.

**Primera puesta en marcha.** Si falta Ollama, la aplicación lo indica con el botón «Instalar Ollama», que lo descarga de ollama.com. Después, en «Modelos», elige un modelo y pulsa «Descargar». Se recomienda **gemma4:12b**, de unos 8 GB. La aplicación comprueba antes el espacio libre y te enseña la licencia del modelo. No descarga nada sin que lo pidas.

## Trabajar

1. **Crea un proyecto** por asunto. Elige el modelo, la verificación por defecto y si quieres guardar la tabla de correspondencias cifrada. Un proyecto temporal se borra al cerrar la aplicación.
2. **Añade la carpeta del expediente** o algunos archivos, con los botones o arrastrándolos a la ventana. Los originales nunca se modifican ni se mueven. La pestaña Archivos indica cuáles se pueden tratar y por qué no los demás.
3. **Pide lo que necesites** en la conversación: «Seudonimiza toda la carpeta y conserva el formato», «¿Qué archivos hay?», «Resume la carta de despido».
4. Cuando la petición crea archivos, Seudónimo muestra un **plan** con el alcance. Elige la verificación (estándar o intensiva) y pulsa «Seudonimizar».
5. En **Operaciones** se ve cada archivo con su pista de pasadas: D1 y D2 son las detecciones, V1, V2… las verificaciones. El dorado indica que la pasada encontró datos nuevos; el verde, que no encontró nada; el ámbar, que quedan restos o incidencias.
6. En **Revisión** están todos los datos con su marcador:
   - **Descartar** lo que no sea un dato personal: no volverá a proponerse.
   - **Añadir** a mano lo que se haya escapado.
   - **Regenerar copias** vuelve a generarlas y verificarlas sin repetir la detección.

## Revisar las copias: la mesa de revisión

Pulsa **«Abrir la mesa de revisión»** (en Documentos o en Datos tapados) o «Revisar la copia» junto a un archivo. Verás la copia seudonimizada entera:

- Los **marcadores** ([PERSONA_001]…) aparecen como tachones. Haz clic en uno para ver qué dato tapa. Si no es un dato personal, pulsa «No es un dato personal: dejarlo a la vista».
- Lo que aparece **en rojo** es un dato que ya está en la lista pero sigue a la vista en esa copia: rehazla.
- Si ves un dato que **se ha escapado**, selecciónalo con el ratón, elige su tipo y pulsa **«Tapar»**. Se tapará en todas las copias del proyecto.
- Los cambios se aplican al pulsar **«Rehacer esta copia»** o **«Rehacer todas»**. La copia se vuelve a generar desde el original y se verifica de nuevo, en una carpeta de resultados nueva.

**Repasar solo unas páginas.** En los PDF, la mesa muestra el documento por páginas; las que tienen datos conocidos sin tapar llevan el número en rojo. Si en una o dos páginas se han quedado datos, marca «Repasar esta página» en ellas y pulsa «Repasar»: el modelo vuelve a buscar solo en esas páginas (mucho más rápido que el documento entero) y la copia se regenera y se verifica. También puedes pedirlo en el chat: «Repasa las páginas 6 y 7 del informe del INSS».

El panel de la derecha se ensancha arrastrando su borde izquierdo (doble clic para alternar entre estrecho y ancho).

## Usar las copias con otra IA

En **«Usar con otra IA»** (arriba):
1. **Copiar las copias seudonimizadas** copia al portapapeles el texto de todas las copias del proyecto, listo para pegarlo en Claude o ChatGPT.
2. Cuando la IA responda, **Poner los nombres en una respuesta…**: pega su respuesta y Seudónimo cambia los marcadores por los datos reales, en este ordenador. Necesita que el proyecto guarde la tabla de correspondencias.

El resultado con los nombres ya contiene datos personales: no lo vuelvas a pegar en ninguna IA.

## Listas del despacho y tipo de asunto

- **Listas** (abajo a la izquierda): «Nunca tapar» para lo que debe quedar a la vista en todos los proyectos (magistrados, organismos, tu despacho) y «Siempre tapar» para lo que debe taparse siempre que aparezca (clientes habituales).
- **Tipo de asunto** (al crear el proyecto o en sus ajustes): elige despido, reclamación de cantidad, Seguridad Social, consulta sobre la empresa o general. Cada uno propone qué datos dejar a la vista, y puedes cambiarlo en «Qué datos se dejan a la vista».

## Correos, chats y carpeta vigilada

- Puedes añadir **correos de Outlook** (.eml, .msg) y **chats exportados de WhatsApp** (el .zip de «Exportar chat»). Se entregan como texto; los adjuntos, fotos y audios no se tratan y se avisa.
- **Carpeta vigilada** (en los ajustes del proyecto): lo que llegue a partir de ese momento a las carpetas del proyecto se seudonimiza solo, mientras Seudónimo esté abierto.

## Certificado de seudonimización

Cada carpeta de resultados lleva un **«Certificado de seudonimización.pdf»** para el expediente: método, resultado por documento y huellas SHA-256 del original y de la copia, sin datos personales. También se abre desde Progreso, botón «Certificado».

## Organizar proyectos y conversaciones

Al pasar el ratón por un proyecto o una conversación de la barra lateral aparece el botón «⋯»:

- **Proyecto**: renombrar, abrir sus ajustes o eliminarlo. Eliminar un proyecto borra sus conversaciones, su tabla de correspondencias y la clave; los documentos originales y los resultados ya generados no se tocan.
- **Conversación**: renombrar, moverla a otro proyecto o eliminarla. Al moverla se lleva todos sus mensajes; los planes que no se hubieran confirmado quedan anulados, porque se referían a los archivos del proyecto de origen.

## Dictar en lugar de escribir

1. Pulsa **«Dictar»** junto a la caja de mensaje (o ⌘⇧D en Mac, Ctrl+Mayús+D en Windows).
2. La primera vez, la aplicación pide descargar el **modelo de voz** (unos 190 MB, una sola vez) y el sistema pide **permiso para usar el micrófono**. Concédelo.
3. Habla. El botón pasa a rojo y muestra el tiempo. Vuelve a pulsarlo para terminar (Esc cancela). Máximo, 3 minutos seguidos.
4. El texto aparece en la caja de mensaje. **Revísalo y pulsa Enviar**: nunca se envía solo.

La voz se transcribe en este ordenador con Whisper y el audio no se guarda. En «Modelos > Dictado por voz» puedes cambiar al modelo `large-v3-turbo` (574 MB), más preciso con ruido o acentos marcados.

Si en Mac el dictado dice que no hay permiso: Ajustes del Sistema > Privacidad y seguridad > Micrófono, y activa Seudónimo.

## Resultados

En la carpeta de resultados del proyecto (por defecto `~/Seudónimo/<proyecto>/<fecha>`):

- **Aprobados/**: copias sin hallazgos en las comprobaciones configuradas.
- **Para revisar/**: copias con algún motivo de revisión, que se explica en el informe. Revísalas antes de usarlas.
- **Informe de verificación** (HTML y JSON), sin datos originales.

«Sin hallazgos en las comprobaciones configuradas» **no es una garantía**. La seudonimización sigue siendo tratamiento de datos personales, y una persona puede ser identificable por el contexto. Revisa los expedientes de alto riesgo antes de comunicarlos a terceros.

## Tabla de correspondencias

Si el proyecto la guarda, va cifrada en este ordenador, con la clave en el Llavero (Mac) o en el Administrador de credenciales (Windows). «Exportar tabla…», en Revisión, la saca en claro para guardarla en el expediente: **no la subas nunca a ninguna IA**. Al borrar el proyecto se destruyen la tabla y su clave.

## Actualizar

Cuando hay una versión nueva, aparece un **aviso amarillo** con el botón **«Actualizar»**. Al pulsarlo, Seudónimo descarga la versión nueva, comprueba que el archivo es exactamente el publicado, se cierra y se vuelve a abrir actualizado en un minuto. Tus proyectos y datos se conservan. La versión instalada se ve bajo el nombre «Seudónimo», arriba a la izquierda; un clic ahí comprueba si hay otra más reciente.

## Si algo falla

- **«Falta Ollama»** o **«Ollama detenido»**: abre Ollama, o pulsa «Instalar Ollama».
- **El modelo va muy lento**: cierra programas pesados. Con 16 GB se carga un solo modelo cada vez.
- **Un documento con error**: el informe explica el motivo, por ejemplo que esté cifrado o dañado, o tenga macros.
- **Registro técnico**, sin texto de documentos: en Mac, `~/Library/Application Support/Seudonimo/registro.log`; en Windows, `%LOCALAPPDATA%\Seudonimo\registro.log`.
