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

**Primera puesta en marcha.** Una franja guía en dos pasos: «Instalar Ollama» (el programa que ejecuta el modelo en este ordenador, desde ollama.com) y «Descargar el modelo», que baja el recomendado, **gemma4:12b**, de unos 8 GB. En «Ajustes > Modelos y dictado» puedes elegir otro, ver su licencia y el espacio libre. No se descarga nada sin que lo pidas.

## La pantalla

A la izquierda, tus **expedientes** y sus conversaciones. En el centro, el **chat**: le pides las cosas con tus palabras, escribiendo o con el botón **«Dictar»** (⌘⇧D), y responde con tarjetas que confirmas. A la derecha, la **lista de documentos** del expediente, cada uno con su estado. Arriba, «Expediente ▾» reúne los ajustes del expediente, la revisión de las copias, el uso con otra IA y la tabla de correspondencias; abajo a la izquierda, «Ajustes» lleva a los modelos, el dictado, las listas del despacho y las actualizaciones.

## Trabajar

1. **Crea un expediente.** Basta con el nombre; o arrastra la carpeta del asunto a la ventana y se crea con su nombre. Dónde se guardan las copias, el tipo de asunto y la revisión a fondo están en «Más opciones» (y en «Expediente ▾ > Ajustes del expediente»).
2. **Añade los documentos**: arrastra archivos o carpetas a la ventana, o pulsa «+ Añadir» en la lista. Los originales nunca se modifican ni se mueven.
3. **Pulsa «Seudonimizar»** o pídeselo al chat: «seudonimiza todos los documentos», «seudonimiza solo la página 6 del informe». El avance se ve en la lista de documentos.
4. **Al terminar**, cada documento muestra **«Abrir copia»** y **«⋯»** (Mostrar en el Finder o en su carpeta, Guardar en…, Revisar y tapar a mano, Riesgo por contexto, Pedírselo al asistente). Los que conviene mirar antes de usar llevan además **«Revisar»**. En el chat queda una tarjeta «Listo» con lo mismo.
5. **Pídeselo al chat** cuando no sepas dónde está algo: «¿dónde está la copia de la carta de despido?», «guarda las copias en el Escritorio», «en la página 2 se ve "Rodríguez", tápalo», «¿qué documentos necesitan revisión?». Debajo de la lista, plegado, está el detalle técnico de cada seudonimización (D = lectura del documento, V = comprobación de la copia).

## Revisar las copias: la mesa de revisión

Pulsa **«Revisar»** junto a un documento, «⋯ > Revisar y tapar a mano» o «Expediente ▾ > Revisar las copias y los datos tapados». Verás la copia seudonimizada entera y, a la derecha, todos los datos tapados del expediente con su marcador:

- Los **marcadores** ([PERSONA_001]…) aparecen como tachones. Haz clic en uno para ver qué dato tapa. Si no es un dato personal, pulsa «No es un dato personal: dejarlo a la vista».
- Lo que aparece **en rojo** es un dato que ya está en la lista pero sigue a la vista en esa copia: rehazla.
- Si ves un dato que **se ha escapado**, selecciónalo con el ratón, elige su tipo y pulsa **«Tapar»**. Se tapará en todas las copias del expediente.
- Los cambios se aplican al pulsar **«Rehacer esta copia»** o **«Rehacer todas»**. La copia se vuelve a generar desde el original y se verifica de nuevo, en una carpeta de resultados nueva.

**Seudonimizar solo unas páginas.** Pide en el chat «Seudonimiza solo la página 6 del informe»: el plan te deja elegir «Solo esas páginas» (la copia solo tiene esas páginas) o «Documento completo». Vale para PDF, Word (las páginas que Word apuntó al guardar el documento), PowerPoint (diapositivas) y Excel (hojas): «sácame solo la hoja 2 del Excel de nóminas».

**Imágenes, caras, logotipos y hojas de Excel.** El texto que va dentro de las imágenes se lee y se tapa en los PDF, Word, PowerPoint y Excel. Las caras de las fotos se tapan con «[CARA]» y las imágenes pequeñas (logotipos, sellos, firmas) se sustituyen enteras por «[LOGO O SELLO]»; se puede desactivar en los ajustes del expediente. Si el nombre de una hoja de Excel lleva un dato, la hoja se renombra («Nóminas PERSONA_001») y sus fórmulas se ajustan solas.

**Pedir que tape algo que se ha quedado a la vista.** Si al revisar ves un dato sin tapar, sobre todo dentro de una imagen (la firma de un correo, un sello con un nombre), díselo al asistente: «en la página 2 se ve "Rodríguez" en la firma, tápalo». Te enseña una tarjeta con lo que va a tapar; al confirmarla lo añade a los datos del expediente y rehace la copia, también dentro de las imágenes.

**Repasar solo unas páginas.** En los PDF, la mesa muestra el documento por páginas; las que tienen datos conocidos sin tapar llevan el número en rojo. Si en una o dos páginas se han quedado datos, marca «Repasar esta página» en ellas y pulsa «Repasar»: el modelo vuelve a buscar solo en esas páginas (mucho más rápido que el documento entero) y la copia se regenera y se verifica. También puedes pedirlo en el chat: «Repasa las páginas 6 y 7 del informe del INSS».

El panel de la derecha se ensancha arrastrando su borde izquierdo (doble clic para alternar entre estrecho y ancho).

## Riesgo por contexto (opcional)

Una copia sin nombres ni DNI puede seguir identificando a alguien por la suma de datos indirectos: «jefa de almacén de 54 años en el centro de Arrecife, de baja desde el 12 de febrero por un trastorno adaptativo». Si quieres revisarlo, pulsa **«Riesgo por contexto»** junto a la copia (en su «⋯» de la lista de documentos, o en la revisión de las copias).

El modelo local lee la copia ya seudonimizada y muestra el nivel de riesgo, los datos indirectos que quedan y una versión más general de cada uno. Vienen marcados los que suelen identificar sin aportar nada al asunto (edad, municipio, familia, nacionalidad, rasgos y ser «la única» o «el más…» de su entorno, que se detecta también sin el modelo); las fechas, los importes, el puesto y la salud quedan a tu criterio, porque pueden ser necesarios (plazos, cantidades, incapacidad). Puedes cambiar el texto propuesto. Al pulsar «Generalizar y rehacer la copia» se cambian en la copia y se vuelve a verificar. Las generalizaciones valen para todo el expediente y se pueden quitar desde el mismo cuadro. Si no pulsas el botón, la aplicación no hace nada de esto.

## Usar las copias con otra IA

En **«Expediente ▾»** (arriba):
1. **Copiar las copias para otra IA** copia al portapapeles el texto de todas las copias del expediente, listo para pegarlo en Claude o ChatGPT.
2. Cuando la IA responda, **Poner los nombres en una respuesta de otra IA…**: pega su respuesta y Seudónimo cambia los marcadores por los datos reales, en este ordenador. Necesita que el expediente guarde la tabla de correspondencias.

El resultado con los nombres ya contiene datos personales: no lo vuelvas a pegar en ninguna IA.

## Listas del despacho y tipo de asunto

- **Listas del despacho** («Ajustes», abajo a la izquierda): «Nunca tapar» para lo que debe quedar a la vista en todos los expedientes (magistrados, organismos, tu despacho) y «Siempre tapar» para lo que debe taparse siempre que aparezca (clientes habituales).
- **Tipo de asunto** (al crear el expediente o en sus ajustes): elige despido, reclamación de cantidad, Seguridad Social, consulta sobre la empresa o general. Cada uno propone qué datos dejar a la vista, y puedes cambiarlo en «Qué datos se dejan a la vista».

## Correos, chats y carpeta vigilada

- Puedes añadir **correos de Outlook** (.eml, .msg) y **chats exportados de WhatsApp** (el .zip de «Exportar chat»). Se entregan como texto; los adjuntos, fotos y audios no se tratan y se avisa.
- **Carpeta vigilada** (en los ajustes del expediente): lo que llegue a partir de ese momento a las carpetas del expediente se seudonimiza solo, mientras Seudónimo esté abierto.

## Certificado de seudonimización

Cada carpeta de resultados lleva un **«Certificado de seudonimización.pdf»** para el expediente: método, resultado por documento y huellas SHA-256 del original y de la copia, sin datos personales. También se abre con «Certificado», debajo de la lista de documentos.

## Organizar expedientes y conversaciones

Al pasar el ratón por un expediente o una conversación de la barra lateral aparece el botón «⋯»:

- **Expediente**: renombrar, abrir sus ajustes o eliminarlo. Eliminar un expediente borra sus conversaciones, su tabla de correspondencias y la clave; los documentos originales y los resultados ya generados no se tocan.
- **Conversación**: renombrar, moverla a otro expediente o eliminarla. Al moverla se lleva todos sus mensajes; los planes que no se hubieran confirmado quedan anulados, porque se referían a los archivos del expediente de origen.

## Dictar en lugar de escribir

1. Pulsa **«Dictar»** junto a la caja de mensaje (o ⌘⇧D en Mac, Ctrl+Mayús+D en Windows).
2. La primera vez, la aplicación pide descargar el **modelo de voz** (unos 190 MB, una sola vez) y el sistema pide **permiso para usar el micrófono**. Concédelo.
3. Habla. El botón pasa a rojo y muestra el tiempo. Vuelve a pulsarlo para terminar (Esc cancela). Máximo, 3 minutos seguidos.
4. El texto aparece en la caja de mensaje. **Revísalo y pulsa Enviar**: nunca se envía solo.

La voz se transcribe en este ordenador con Whisper y el audio no se guarda. En «Ajustes > Modelos y dictado» puedes cambiar al modelo `large-v3-turbo` (574 MB), más preciso con ruido o acentos marcados.

Si en Mac el dictado dice que no hay permiso: Ajustes del Sistema > Privacidad y seguridad > Micrófono, y activa Seudónimo.

## Dónde quedan los documentos

Por defecto, **junto a los originales**, en una carpeta **«Seudonimizados»** dentro de la carpeta de cada documento:

- `Carta de despido (seudonimizado).docx`: copia sin hallazgos en las comprobaciones configuradas.
- `Nóminas (seudonimizado - revisar).xlsx`: copia con algún motivo de revisión. Revísala antes de usarla.
- `Certificados/`: el certificado de cada seudonimización, con la fecha.
- `Anteriores/`: las versiones anteriores de cada copia, con la fecha en el nombre. En la carpeta solo queda la última.

Si eliges otra carpeta en los ajustes del expediente, la estructura es la misma dentro de esa carpeta. Si la carpeta de un original no admite escritura (una unidad de red de solo lectura), esas copias van a `~/Seudónimo/<expediente>` y la tarjeta «Listo» lo avisa. La carpeta «Seudonimizados» nunca se vuelve a leer como si fueran originales.

En el chat puedes preguntar «¿dónde está el documento?» (sale una tarjeta con la ruta y botones para abrirlo) o pedir «guárdalo en el Escritorio» (sale una tarjeta para confirmarlo; se copia la versión seudonimizada, nunca el original).

«Sin hallazgos en las comprobaciones configuradas» **no es una garantía**. La seudonimización sigue siendo tratamiento de datos personales, y una persona puede ser identificable por el contexto. Revisa los expedientes de alto riesgo antes de comunicarlos a terceros.

## Tabla de correspondencias

Si el expediente la guarda, va cifrada en este ordenador, con la clave en el Llavero (Mac) o en el Administrador de credenciales (Windows). «Expediente ▾ > Exportar la tabla de correspondencias…» la saca en claro para guardarla en el expediente: **no la subas nunca a ninguna IA**. Al borrar el expediente se destruyen la tabla y su clave.

## Actualizar

Cuando hay una versión nueva, aparece un **aviso amarillo** con el botón **«Actualizar»**. Al pulsarlo, Seudónimo descarga la versión nueva, comprueba que el archivo es exactamente el publicado, se cierra y se vuelve a abrir actualizado en un minuto. Tus expedientes y datos se conservan. La versión instalada se ve bajo el nombre «Seudónimo», arriba a la izquierda; un clic ahí comprueba si hay otra más reciente.

## Si algo falla

- **«Falta Ollama»** o **«Ollama detenido»**: abre Ollama, o pulsa «Instalar Ollama».
- **El modelo va muy lento**: cierra programas pesados. Con 16 GB se carga un solo modelo cada vez.
- **Un documento con error**: el informe explica el motivo, por ejemplo que esté cifrado o dañado, o tenga macros.
- **Registro técnico**, sin texto de documentos: en Mac, `~/Library/Application Support/Seudonimo/registro.log`; en Windows, `%LOCALAPPDATA%\Seudonimo\registro.log`.
