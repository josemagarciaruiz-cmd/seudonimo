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

A la izquierda, tus **expedientes** (cada uno es un chat; las conversaciones anteriores están en «Expediente ▾»). En el centro, el **chat**: le pides las cosas con tus palabras, escribiendo o con el botón **«Dictar»** (⌘⇧D), y lo hace directamente (con «Cancelar» a la vista). A la derecha, la **lista de documentos** del expediente, cada uno con su estado. Arriba, «Expediente ▾» reúne los ajustes del expediente, la revisión de las copias, el uso con otra IA y la lista de nombres y etiquetas; abajo a la izquierda, «Ajustes» lleva a los modelos, el dictado, las listas del despacho y las actualizaciones.

## Trabajar

1. **Crea un expediente.** Basta con el nombre; o arrastra la carpeta del asunto a la ventana y se crea con su nombre. Dónde se guardan las copias, el tipo de asunto y la revisión a fondo están en «Más opciones» (y en «Expediente ▾ > Ajustes del expediente»).
2. **Añade los documentos**: arrastra archivos o carpetas a la ventana, o pulsa «+ Añadir» en la lista. Los originales nunca se modifican ni se mueven.
3. **Pulsa «Seudonimizar»** o pídeselo al chat: «seudonimiza todos los documentos», «seudonimiza solo la página 6 del informe». El avance se ve en la lista de documentos.
4. **Al terminar**, cada documento muestra **«Abrir copia»**, **«Revisar»**, **«Comprobar riesgo»** y **«⋯»** (Mostrar en el Finder o en su carpeta, Guardar en…, pedirle algo al asistente). En el chat queda una tarjeta «Listo» con lo mismo. Nada pide confirmación: los originales nunca se tocan y todo se puede cancelar o deshacer.
5. **Pídeselo al chat** cuando no sepas dónde está algo: «¿dónde está la copia de la carta de despido?», «guarda las copias en el Escritorio», «en la página 2 se ve "Rodríguez", tápalo», «¿qué documentos necesitan revisión?». Debajo de la lista, plegado, está el detalle técnico de cada seudonimización (D = lectura del documento, V = comprobación de la copia).

## Revisar una copia y tapar a mano

Pulsa **«Revisar»** junto a un documento. Verás **la página tal como ha quedado**, con los tachones (los PDF, fotos y escaneos siempre; Word, PowerPoint y Excel si tienes Office o Pages en el ordenador, que es quien la dibuja). Para tapar una zona, un sello o una foto de un PDF, **arrastra el ratón por encima**, como con un rotulador, y pulsa «Tapar»: se tapa en el acto, el texto que había debajo desaparece del archivo y, si te equivocas, «Deshacer» o la ✕ que aparece al pasar el ratón por la zona. Los documentos sin página (texto, correos) se ven como texto. En cualquier caso:

- ¿Algo que se ha quedado a la vista? Haz **doble clic** encima (o selecciónalo con el ratón) y pulsa **«Tapar»**. La copia se rehace en el acto y aparece «Deshacer» por si te has equivocado. Se tapará también en las demás copias del expediente cuando se actualicen.
- ¿Una etiqueta que no debería estar (un juzgado, una ley)? Haz clic en ella y elige **«Dejar a la vista»**. También en el acto, también con «Deshacer».
- ¿Una página con muchos datos sin tapar? Marca «Volver a leer esta página» y pulsa el botón de arriba: el modelo la lee de nuevo entera.
- **«Datos tapados»** (arriba a la derecha) despliega la lista completa del expediente, con un buscador y un campo para apuntar un dato a mano.

## Riesgo por contexto (opcional)

Una copia sin nombres ni DNI puede seguir identificando a alguien por la suma de datos indirectos: «jefa de almacén de 54 años en el centro de Arrecife, de baja desde el 12 de febrero por un trastorno adaptativo». Si quieres revisarlo, pulsa **«Comprobar riesgo»** junto al documento (en la lista, en la tarjeta «Listo» o en la revisión).

El modelo local lee la copia ya seudonimizada y muestra un semáforo, los datos indirectos que quedan («Se ve «54 años»») y una forma más general de decirlo («se cambiaría por «entre 50 y 59 años»»), con un interruptor por dato. Vienen marcados los que suelen identificar sin aportar nada al asunto (edad, municipio, familia, nacionalidad, rasgos y ser «la única» o «el más…» de su entorno, que se detecta también sin el modelo); las fechas, los importes, el puesto y la salud quedan a tu criterio, porque pueden ser necesarios (plazos, cantidades, incapacidad). Puedes cambiar la propuesta pulsándola. Al pulsar «Aplicar» se cambian en la copia y se vuelve a verificar. Las generalizaciones valen para todo el expediente y se pueden quitar desde el mismo cuadro. Si no pulsas el botón, la aplicación no hace nada de esto.

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
