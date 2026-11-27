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

1. **Crea un proyecto** por expediente. Al crearlo eliges dónde se guardan los documentos seudonimizados: junto a los originales (recomendado) o en una carpeta que elijas. El resto (modelo, tipo de revisión, tabla de correspondencias) está en «Opciones avanzadas».
2. **Añade los documentos**: una carpeta entera o archivos sueltos, con los botones o arrastrándolos a la ventana. Los originales nunca se modifican ni se mueven.
3. **Pulsa «Seudonimizar»**: el botón grande de la pestaña Documentos trata todos los pendientes. También puedes pedirlo en el chat («seudonimiza solo la página 3 del informe»).
4. **Al terminar** aparece en el chat una tarjeta «Listo» con cada documento y sus botones: Abrir, Mostrar en el Finder (o en su carpeta en Windows), Guardar en… y Revisar.
5. La pestaña **Resultados** reúne siempre todos los documentos seudonimizados del proyecto, dónde están, los certificados y, plegado, el detalle técnico de cada seudonimización (D = lectura del documento, V = comprobación de la copia).
6. En **Datos tapados** están todos los datos con su marcador: descartar lo que no sea un dato personal, añadir a mano lo que se haya escapado o rehacer las copias.

## Revisar las copias: la mesa de revisión

Pulsa **«Abrir la mesa de revisión»** (en Documentos o en Datos tapados) o «Revisar la copia» junto a un archivo. Verás la copia seudonimizada entera:

- Los **marcadores** ([PERSONA_001]…) aparecen como tachones. Haz clic en uno para ver qué dato tapa. Si no es un dato personal, pulsa «No es un dato personal: dejarlo a la vista».
- Lo que aparece **en rojo** es un dato que ya está en la lista pero sigue a la vista en esa copia: rehazla.
- Si ves un dato que **se ha escapado**, selecciónalo con el ratón, elige su tipo y pulsa **«Tapar»**. Se tapará en todas las copias del proyecto.
- Los cambios se aplican al pulsar **«Rehacer esta copia»** o **«Rehacer todas»**. La copia se vuelve a generar desde el original y se verifica de nuevo, en una carpeta de resultados nueva.

**Seudonimizar solo unas páginas.** Pide en el chat «Seudonimiza solo la página 6 del informe»: el plan te deja elegir «Solo esas páginas» (la copia solo tiene esas páginas) o «Documento completo». Vale para PDF, Word (las páginas que Word apuntó al guardar el documento), PowerPoint (diapositivas) y Excel (hojas): «sácame solo la hoja 2 del Excel de nóminas».

**Imágenes, caras, logotipos y hojas de Excel.** El texto que va dentro de las imágenes se lee y se tapa en los PDF, Word, PowerPoint y Excel. Las caras de las fotos se tapan con «[CARA]» y las imágenes pequeñas (logotipos, sellos, firmas) se sustituyen enteras por «[LOGO O SELLO]»; se puede desactivar en «Opciones avanzadas» del proyecto. Si el nombre de una hoja de Excel lleva un dato, la hoja se renombra («Nóminas PERSONA_001») y sus fórmulas se ajustan solas.

**Pedir que tape algo que se ha quedado a la vista.** Si al revisar ves un dato sin tapar, sobre todo dentro de una imagen (la firma de un correo, un sello con un nombre), díselo al asistente: «en la página 2 se ve "Rodríguez" en la firma, tápalo». Te enseña una tarjeta con lo que va a tapar; al confirmarla lo añade a los datos del proyecto y rehace la copia, también dentro de las imágenes.

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

## Dónde quedan los documentos

Por defecto, **junto a los originales**, en una carpeta **«Seudonimizados»** dentro de la carpeta de cada documento:

- `Carta de despido (seudonimizado).docx`: copia sin hallazgos en las comprobaciones configuradas.
- `Nóminas (seudonimizado - revisar).xlsx`: copia con algún motivo de revisión. Revísala antes de usarla.
- `Certificados/`: el certificado de cada seudonimización, con la fecha.
- `Anteriores/`: las versiones anteriores de cada copia, con la fecha en el nombre. En la carpeta solo queda la última.

Si eliges otra carpeta en los ajustes del proyecto, la estructura es la misma dentro de esa carpeta. Si la carpeta de un original no admite escritura (una unidad de red de solo lectura), esas copias van a `~/Seudónimo/<proyecto>` y la tarjeta «Listo» lo avisa. La carpeta «Seudonimizados» nunca se vuelve a leer como si fueran originales.

En el chat puedes preguntar «¿dónde está el documento?» (sale una tarjeta con la ruta y botones para abrirlo) o pedir «guárdalo en el Escritorio» (sale una tarjeta para confirmarlo; se copia la versión seudonimizada, nunca el original).

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
