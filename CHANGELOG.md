# Cambios

## 0.8.3 · 28 de noviembre de 2026

- **¿Llega este ordenador?** Antes de instalar Ollama y de descargar el modelo, Seudónimo comprueba el ordenador y lo dice con un semáforo: verde (cumple), amarillo (funciona, con matices) o rojo (no llega), con el motivo en una frase. Mira la memoria (se recomiendan 16 GB; con 8 o menos no funciona), el espacio libre (unos 16 GB para Ollama y el modelo), el procesador (en Mac, chip Apple; en Windows, 64 bits), la tarjeta gráfica en Windows (sin una que acelere la IA, funciona pero más despacio) y si Windows está al día. «Ver detalles» enseña cada dato; también en «Ajustes › Comprobar este ordenador» y en «Modelos y dictado». Si sale rojo, los botones pasan a «… de todas formas», para que nadie se baje 8 GB sin saberlo. Nada de esto sale del ordenador.
- Descarga: la página del proyecto tiene arriba una sección «Descargar» con enlaces que dan siempre la última versión (`releases/latest/download/Seudonimo-Windows.exe` y `Seudonimo-Mac.dmg`).

## 0.8.2 · 27 de noviembre de 2026

- **Seleccionar varias palabras, una frase o un párrafo y tapar de una vez.** Al arrastrar sobre la página era fácil empezar o acabar a mitad de una palabra, y entonces no se tapaba nada (solo funcionaba palabra a palabra con el doble clic). Ahora la selección se ajusta siempre a palabras enteras y se ve resaltado exactamente lo que se va a tapar. Unas pocas palabras (un nombre, una frase corta) se tapan como dato, en esta copia y en las demás del expediente; un párrafo o más de dos líneas de un PDF se tapan línea a línea con un recuadro en esa copia, con un solo «Tapar» y un solo «Deshacer». En Word y PowerPoint, una frase larga se apunta línea a línea para que se encuentre en su párrafo.
- Los recuadros tapados a mano se ven en la revisión como el tachón que son, con su rótulo.

## 0.8.1 · 27 de noviembre de 2026

- **Una sola vista en la revisión.** Desaparecen los botones «Página | Texto»: la copia se ve como página, tal como ha quedado, y encima lleva una capa de texto invisible, así que el doble clic sobre una palabra y «Tapar» funcionan directamente sobre la página, igual que el rotulador. Las etiquetas («Persona 1»…) se ven sobre sus recuadros y se pueden pulsar. Los documentos que no tienen página (texto, correos) se siguen viendo como texto.
- **Word, PowerPoint y Excel también se ven como página** si en el ordenador está Microsoft Office (o Pages, en Mac): es el propio programa el que dibuja la copia, en este ordenador, para enseñarla. La primera vez tarda unos segundos y puede verse abrirse el programa. El rotulador sigue siendo solo para PDF; en Office se tapa con el doble clic.
- Arreglado: en la aplicación de escritorio las páginas salían en blanco (la ventana no permitía mostrar las imágenes cargadas con el token).
- «Ver en el Finder» y «Guardar en…» también arriba, en la revisión; en la lista de documentos, el botón «⋯» pasa a llamarse «Carpeta ▾».

## 0.8.0 · 27 de noviembre de 2026

- **Visor de páginas con rotulador.** La revisión de un PDF (también las fotos y los escaneos, que se convierten a PDF) enseña la página tal como ha quedado, con los tachones. Para tapar algo que falta, se arrastra el ratón por encima, como con un rotulador: la zona se tapa en el acto con un recuadro «Tapado», se puede quitar (✕ al pasar el ratón) y queda guardada en el expediente, de modo que se mantiene si la copia se vuelve a generar. El texto que había debajo desaparece del archivo. Un selector «Página | Texto» permite seguir viendo el texto con las etiquetas; los documentos de Office se ven en texto.
- La vista de texto de una copia ya no repite el contenido de las páginas tachadas (antes se leía dos veces: la capa de texto y la imagen).
- Robustez: la biblioteca de PDF ya no se usa desde dos hilos a la vez (podía cerrar la aplicación al abrir varias páginas mientras un trabajo tachaba otro documento). Y si la aplicación se cierra y se abre enseguida, vuelve a usar el mismo puerto.

## 0.7.0 · 27 de noviembre de 2026

Menos pasos y palabras más claras, para que se use sin explicaciones.

- **«Tapar» tapa de una vez.** En la revisión, al tapar una palabra (o dejar a la vista una etiqueta) la copia se rehace en el acto y aparece «Deshacer». Desaparecen los cambios pendientes y los botones «Rehacer esta copia» y «Rehacer todas»; si una copia se abrió antes que un cambio, un solo botón, «Actualizar esta copia».
- **Sin confirmaciones** para lo que no toca los originales: «Seudonimizar», volver a leer páginas y lo que se pide en el chat se ejecutan directamente (siempre con «Cancelar» a la vista). Se sigue confirmando lo que no tiene vuelta atrás (borrar un expediente, destruir la clave).
- **«Comprobar riesgo» a la vista** en cada documento terminado y en la tarjeta «Listo». El cuadro habla claro: un semáforo, «Se ve «54 años», se cambiaría por «entre 50 y 59 años»», un interruptor por dato y un botón «Aplicar». La propuesta se puede cambiar pulsándola.
- **Etiquetas en lugar de códigos** en la revisión: «Persona 1», «Empresa 1», «DNI / NIE 1» (el archivo sigue llevando [PERSONA_001]…). «Dejar a la vista» en vez de «Descartar», «clave para recuperar los nombres» en vez de «tabla de correspondencias».
- **La revisión se abre dentro de la ventana**, con la lista de documentos del expediente a la izquierda y los «Datos tapados» plegados hasta que se piden.
- **Un expediente es un chat.** La columna izquierda ya no acumula conversaciones; las anteriores están en «Expediente ▾ › Conversaciones anteriores».
- **Guía en tres globos** la primera vez (añadir, seudonimizar, abrir y revisar).

## 0.6.2 · 27 de noviembre de 2026

- **Tapar a mano dentro de una generalización.** Si en la revisión se tapa una palabra que puso el riesgo por contexto (por ejemplo «proceso», de «un proceso de salud mental»), ahora se tapa al rehacer la copia. Antes la copia quedaba «para revisar» porque esa palabra no está en el original.
- En la revisión de las copias, en cuanto hay un cambio pendiente, el botón se ilumina y dice lo que hace: «Aplicar el cambio a esta copia» (o «Aplicar a todas las copias»). El aviso tras «Tapar» indica que hay que pulsarlo.

## 0.6.1 · 27 de noviembre de 2026

- Riesgo por contexto: si el modelo señala un trozo de una frase de unicidad que ya ha encontrado la regla («única mujer… en la isla» dentro de «la única mujer… dentro del grupo empresarial»), se muestra una sola vez, con la propuesta de la regla. Y si el modelo propone una versión que sigue siendo única («única persona… en la zona»), se corrige a «una persona…».

## 0.6.0 · 27 de noviembre de 2026

Más sencilla: el chat en el centro y una sola lista de documentos.

- **Expedientes** en lugar de proyectos. Para crear uno basta con el nombre; lo demás está en «Más opciones». Si se arrastra la carpeta de un asunto a la ventana sin expediente abierto, se propone uno con el nombre de la carpeta.
- **Una sola lista de documentos** a la derecha, sin pestañas: cada documento con su estado, «Abrir copia» y «⋯» (Mostrar en el Finder, Guardar en…, Revisar y tapar a mano, Riesgo por contexto, Pedírselo al asistente). Los que conviene mirar llevan «Revisar». Debajo, dónde se guardan las copias, el certificado y, plegados, las carpetas del expediente y el detalle técnico.
- **El chat, protagonista**: ejemplos que se pulsan para rellenar la caja («Seudonimiza solo la página 6 del informe», «¿Dónde está la copia…?», «Guarda las copias en el Escritorio», «En la página 2 se ve "…", tápalo») y botón «Dictar» más visible.
- Fuera de la vista lo técnico: el selector de modelo, la casilla de revisión a fondo y los botones de añadir repetidos. «Expediente ▾» reúne los ajustes del expediente, la revisión de las copias, el uso con otra IA y la tabla; «Ajustes» (abajo a la izquierda), los modelos, el dictado, las listas del despacho y las actualizaciones.
- **Primera puesta en marcha guiada** en dos pasos: instalar Ollama y descargar el modelo recomendado con un botón.
- **Riesgo por contexto: «la única…» y «el más…»**. Se detectan por regla, sin depender del modelo, frases como «la única mujer con categoría de jefa de almacén en la isla» o «el más antiguo de la plantilla», y se propone «una mujer con categoría de jefa de almacén» o «una de las personas con más antigüedad». Un segundo análisis ya no se salta estas frases cuando llevan dentro algo generalizado antes.

## 0.5.1 · 27 de noviembre de 2026

- Riesgo por contexto: las versiones generales encajan en la frase (sin «por un un proceso…»; «nacionalidad colombiana» → «nacionalidad extranjera»), un segundo análisis ya no señala lo que se generalizó antes y no repite el mismo dato con más o menos palabras («12/02/2026» y «desde el 12/02/2026»).

## 0.5.0 · 27 de noviembre de 2026

- **Riesgo por contexto (opcional, con un botón).** En cada documento seudonimizado (pestaña Resultados, tarjeta «Listo» y mesa de revisión), «Riesgo por contexto» busca en la copia los datos indirectos que, juntos, podrían permitir reconocer a la persona aunque no aparezca su nombre: edad, fechas de hechos personales, salario exacto, municipio, puesto concreto, centro de trabajo, salud, situación familiar, nacionalidad, representación sindical y rasgos singulares (considerando 26 RGPD). Da un nivel de riesgo (bajo, medio o alto) con la explicación y propone una versión más general de cada dato («54 años» → «entre 50 y 59 años»; «Arrecife» → «un municipio de Lanzarote»). El profesional marca lo que quiere generalizar, puede cambiar el texto propuesto y la copia se rehace. Si no se pulsa, no cambia nada.
- Las generalizaciones valen para todo el proyecto (la misma persona en otros documentos) y se pueden quitar desde el mismo cuadro.

## 0.4.2 · 27 de noviembre de 2026

- **La comprobación final busca caras en la copia.** En cada ciclo, después de generar la copia, el detector vuelve a buscar caras desde cero en sus páginas (PDF) o imágenes (Word, PowerPoint y Excel). Si encuentra alguna que se escapó, el ciclo siguiente la tapa en ese sitio; si sigue viéndola donde ya se tapó, el documento queda «Para revisar» con el motivo, en vez de darse por bueno.

## 0.4.1 · 27 de noviembre de 2026

- **Caras en las fotos.** Se detectan en el propio ordenador (en Mac con el sistema; en Windows con OpenCV y el modelo YuNet) y se tapan con «[CARA]» en los PDF (también en las copias escaneadas de un DNI) y en las imágenes de Word, PowerPoint y Excel.
- **Logotipos, sellos y firmas en Word, PowerPoint y Excel**, con el mismo criterio que en los PDF: las imágenes que se muestran pequeñas se sustituyen enteras por un recuadro «[LOGO O SELLO]» del mismo tamaño. Los logotipos vectoriales (EMF/WMF), que no se pueden editar, se cambian por ese recuadro en PNG.
- La opción del proyecto pasa a llamarse «Tapar logotipos, sellos, firmas pequeñas y caras de las fotos» y vale para todos los formatos.

## 0.4.0 · 27 de noviembre de 2026

Más fácil de usar: se ve qué hacer y dónde queda cada documento.

- **Las copias se guardan junto a los originales**, en una carpeta «Seudonimizados» dentro de la carpeta de cada documento, sin subcarpetas por fecha. Cada copia lleva el nombre del original con «(seudonimizado)» o «(seudonimizado - revisar)»; la versión anterior pasa a «Anteriores» y los certificados a «Certificados». Al crear el proyecto se puede elegir otra carpeta.
- **Tarjeta «Listo»** en el chat al terminar: cada documento con «Abrir», «Mostrar en el Finder», «Guardar en…» y «Revisar», la carpeta donde están y el certificado.
- **Pestaña «Resultados»** (antes «Progreso»): todos los documentos seudonimizados del proyecto con sus botones, dónde se guardan, los certificados y, plegado, el detalle técnico.
- **Pedirlo en el chat:** «¿dónde está el documento?» muestra la ruta con botones para abrirlo; «guárdalo en el Escritorio» (o en Documentos, Descargas o cualquier carpeta) lo copia tras confirmarlo.
- **Primer uso guiado** en tres pasos (añadir, seudonimizar, revisar y guardar), un **botón grande «Seudonimizar»** para los documentos pendientes sin pasar por el chat, una zona para **arrastrar archivos** y las opciones técnicas del proyecto en «Opciones avanzadas». «Verificación intensiva» pasa a llamarse «Revisión a fondo».

## 0.3.8 · 27 de noviembre de 2026

- **Imágenes dentro de Word, PowerPoint y Excel.** Se leen con el OCR del propio ordenador y los datos que aparecen en ellas (una firma escaneada, una captura con un nombre) se tapan con un recuadro negro sobre la imagen, que se guarda en el mismo formato. Las imágenes vectoriales (EMF/WMF) no se pueden leer: si el documento las lleva, el resultado lo avisa.
- **Nombres de las hojas de Excel.** Si el nombre de una hoja lleva un dato («Nóminas Ana Ruiz»), se cambia por «Nóminas PERSONA_001» (sin corchetes, que Excel no admite en los nombres de hoja) y se actualizan las fórmulas, los nombres definidos, los gráficos, los hipervínculos internos y las tablas dinámicas que la nombran, para que el libro siga calculando igual.
- **Más texto de Office que antes no se miraba:** títulos y etiquetas de los gráficos (también los valores de texto que copian de las celdas), SmartArt, cuadros de texto de Excel y el texto fijo de los patrones de PowerPoint (un pie «Despacho X · confidencial»).

## 0.3.7 · 27 de noviembre de 2026

- **Pedir en el chat que tape algo.** «En la página 2 se ve "Rodríguez" en la firma, tápalo»: el asistente prepara una tarjeta con lo que va a tapar y, al confirmarla, lo añade a los datos del proyecto y rehace la copia con el mismo alcance (entera o solo esas páginas).
- **Texto dentro de las imágenes.** En los PDF con texto, las imágenes grandes (la firma de un correo, un pie legal, una foto con un nombre) se leen con OCR y lo que pone en ellas se tapa. Antes solo se tapaban enteras las imágenes pequeñas (logos y sellos).
- **Webs y números de colegiado.** Se tapan solos los dominios y direcciones web (josemaria.ai, www…) salvo los de organismos públicos, y los números de colegiado («Graduado Social nº 88», «Col. 1234»), sin tocar un «88» suelto que pueda ser un importe.
- **Páginas en Word, PowerPoint y Excel.** Se puede pedir una página de un Word, una diapositiva de un PowerPoint o una hoja de un Excel, tanto para repasarla como para sacar una copia solo con ella. En la copia recortada no queda nada de lo quitado: ni las diapositivas, hojas, imágenes, notas o comentarios, ni los textos compartidos de Excel. Las páginas de Word son las que Word apuntó al guardar el documento; si no las tiene, la aplicación lo dice.
- **El nombre del archivo también se seudonimiza** aunque la persona no salga en las páginas tratadas (antes, al pedir solo una página, la copia podía llevar el nombre del original).
- Los títulos de las diapositivas y los nombres de las hojas que Office guarda en las propiedades del archivo pasan también por la seudonimización.
- Corregido: borrar un proyecto mientras se seudonimizaba bloqueaba la base de datos y no dejaba crear nada más hasta reiniciar.

## 0.3.6 · 27 de noviembre de 2026

- El asistente encuentra el archivo aunque el modelo escriba su nombre con alguna letra de menos o sin tildes, y si el proyecto tiene un solo archivo entiende «el documento». En la batería de pruebas, un «seudonimiza solo la página 3» fallaba por eso.
- Avisos de adjuntos y fotos de WhatsApp en singular o plural según corresponda.

## 0.3.5 · 27 de noviembre de 2026

- **Seudonimizar solo unas páginas.** Si pides «seudonimiza solo la página 6», la copia es un PDF con únicamente esa página, seudonimizada y verificada. El plan del chat deja elegir entre «Solo esas páginas» y «Documento completo» (repasar esas páginas dentro del documento ya seudonimizado). En la lista de documentos, el archivo aparece como «Copia de algunas páginas».
- **El resultado dice lo que se ha hecho.** Si se repasan unas páginas dentro de un documento que nunca se había seudonimizado entero, la copia queda en «Requiere revisión» y explica que el resto de páginas no lo ha leído el modelo, en lugar de mostrar «Sin hallazgos».

## 0.3.4 · 26 de noviembre de 2026

- Primera actualización instalada con el botón «Actualizar» de la 0.3.3 (comprobación del actualizador). Sin otros cambios.

## 0.3.3 · 26 de noviembre de 2026

- **Actualizar con un clic.** Cuando hay una versión nueva aparece un aviso amarillo, arriba y en la barra lateral, con el botón «Actualizar». Seudónimo la descarga de GitHub, comprueba su huella SHA-256 con la publicada, se cierra, se instala y vuelve a abrirse solo. Los proyectos y los datos se conservan. No actualiza si hay una seudonimización en marcha.

## 0.3.2 · 26 de noviembre de 2026

- **Escaneados: datos conocidos que no se dejaban tapar.** Cuando la verificación encuentra en la copia un dato ya conocido que la edición no supo localizar (partido entre líneas o leído de otra forma por el OCR), ahora marca dónde está y el siguiente ciclo lo tapa en el original. Antes el documento se quedaba en «Requiere revisión».
- **Versión a la vista**, bajo el nombre de la aplicación: un clic dice si hay otra más reciente y abre su descarga o la lista de versiones en GitHub.
- Si se cierra la aplicación con un trabajo en marcha, al volver a abrirla ese trabajo queda como «Interrumpido» y los archivos recuperan su última copia (antes se quedaban «En cola» para siempre).
- **Repasar páginas concretas.** En la mesa de revisión, los PDF se ven por páginas, con su número; las que conservan datos conocidos sin tapar se marcan en rojo. Marca «Repasar esta página» en una o varias y pulsa «Repasar»: el modelo vuelve a buscar datos solo en esas páginas, y la copia se regenera y se verifica entera. También se puede pedir por el chat: «Repasa las páginas 6 y 7 del informe».

## 0.3.1 · 26 de noviembre de 2026

- **Cola de trabajos a la vista:** abajo a la izquierda se ve qué se está seudonimizando, en qué proyecto, con qué avance y cuántos trabajos esperan. Un clic lleva a su pestaña Progreso.
- La barra lateral se actualiza sola cuando aparece un proyecto nuevo.
- El razonamiento interno del modelo («thought … <channel|>») ya no se cuela en las respuestas del chat.
- Correcciones: el plan remite a la pestaña «Progreso»; al cambiar de proyecto ya no queda el título de la conversación anterior.

## 0.3.0 · 26 de noviembre de 2026

- **Mesa de revisión** a pantalla completa: cada copia seudonimizada entera, con los marcadores resaltados y en rojo los datos conocidos que siguen a la vista. Se selecciona con el ratón lo que se ha escapado y se pulsa «Tapar»; un clic en un marcador muestra qué tapa y permite dejarlo a la vista. «Rehacer esta copia» o «Rehacer todas» aplican los cambios.
- **Panel más ancho y redimensionable** (arrastrando su borde) y pestañas con nombres claros: Documentos, Progreso y Datos tapados.
- **Usar con otra IA:** «Copiar las copias seudonimizadas» deja el texto listo para pegarlo en Claude o ChatGPT, y «Poner los nombres» devuelve la respuesta con los datos reales, sin conexión.
- **Listas del despacho**, comunes a todos los proyectos: «Nunca tapar» (magistrados, organismos, tu despacho) y «Siempre tapar» (clientes habituales).
- **Tipo de asunto** al crear un proyecto (despido, cantidad, Seguridad Social, consulta sobre la empresa…), con los datos que se dejan a la vista.
- **Correos y chats:** correos de Outlook (.eml y .msg) y chats exportados de WhatsApp (.zip); se entregan como texto.
- **Carpeta vigilada:** lo que llega a las carpetas del proyecto se seudonimiza solo, mientras la aplicación está abierta.
- **Certificado de seudonimización** en PDF en cada carpeta de resultados: método, resultado y huellas SHA-256, sin datos personales.
- **Aviso de versiones nuevas**, consultando las versiones publicadas en GitHub.
- **Licencia PolyForm Shield 1.0.0:** uso libre, también profesional; prohibido usarla para ofrecer un producto que compita.

## 0.2.0 · 26 de noviembre de 2026 · ahora se llama Seudónimo

- **Nuevo nombre: Seudónimo.** Lo que hace la aplicación es seudonimizar, no anonimizar. Cambian la ventana, el icono (un detective con sombrero del que solo se ven los ojos), los instaladores (`Seudonimo-<versión>-…`), las carpetas (`~/Seudónimo` para los resultados) y el repositorio. La primera vez que se abre, traslada sola los datos, los resultados, las tablas cifradas y sus claves de «Áurea Asistente Local».
- **Gestión de proyectos y conversaciones** como en Claude: menú «⋯» en la barra lateral para renombrar, eliminar y mover una conversación a otro proyecto. Al moverla, los planes sin confirmar se anulan.
- **Dictado por voz** (botón «Dictar», ⌘⇧D): Whisper transcribe en el propio ordenador y el texto queda en la caja de mensaje para revisarlo. Modelos `small` (190 MB, por defecto) y `large-v3-turbo` (574 MB), que se descargan solo cuando se piden. `whisper-cli` (whisper.cpp b5454, MIT) va incluido en los instaladores.

## 0.1.1 · 26 de noviembre de 2026

- **Verificación intensiva más fiable.** El ruido del OCR sobre los propios tachones (marcadores mal leídos, tratamientos deformados como «Diña») ya no se reincorpora como dato. Lo que solo aparece en la copia se admite si se parece a la lectura del original o si viene de una regla con forma válida.
- **Validación estructural por tipo** al registrar datos (teléfono, DNI/NIE, NIF, IBAN, NAF, CCC, correo, nombres): la precisión pasa del 92,8 % al 96,8 % sin perder recall.
- La ventana de Mac, probada de punta a punta con Gemma: conversación, plan, ejecución, revisión, descarte y regeneración.
- Correcciones:
  - comprobación previa CORS de la ventana;
  - estilos de los botones de opción en WebKit;
  - «Regenerar copias» respeta la verificación intensiva;
  - el SBOM se genera antes de firmar.

## 0.1.0 · 26 de noviembre de 2026 · primera versión de desarrollo

Implementa los correos «Plan técnico detallado: asistente jurídico documental local» y «Anexo al plan técnico: seudonimización autónoma multipasada y verificación iterativa» (25/11/2026).

- **Fase 0.** Auditoría del motor de Áurea Anonimus 2.1.0 y del entorno (`docs/00-auditoria-motor.md`). Corpus sintético de 12 documentos etiquetados y evaluador de recall, conservación y precisión (`pruebas/`).
- **Fases 1 y 2.**
  - El motor como biblioteca del servicio local.
  - Registro de entidades por proyecto, con etiquetas estables `[TIPO_001]` y sin fusionar homónimos.
  - Tabla de correspondencias opcional y cifrada.
  - Controlador multipasada con verificación independiente y criterio de parada (`docs/multipasada.md`).
- **Fase 3.**
  - Ventana de escritorio con Tauri 2.
  - Servicio local en 127.0.0.1 con token efímero y validación de Host y Origin.
  - SQLite para proyectos, conversaciones e inventario.
- **Fase 4.**
  - Interfaz común de proveedores de modelos, con Ollama como primer adaptador.
  - Gestor de modelos: descargar, borrar, elegir uno por defecto y ver la licencia.
  - Asistente con herramientas registradas y un clasificador de intención para los modelos sin herramientas.
  - Planes que el usuario confirma.
- **Fase 5 (parcial).**
  - Formatos: PDF nativo y escaneado, Word, Excel, PowerPoint, CSV, texto e imágenes (`docs/matriz-formatos.md`).
  - Comentarios, autores, cambios controlados, propiedades y hojas ocultas.
- **Fase 6 (en curso).** Instalador de Mac (.dmg) y de Windows (NSIS), SBOM CycloneDX, `THIRD_PARTY_NOTICES.md` y manual (`docs/manual.md`).
