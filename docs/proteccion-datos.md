# Protección de datos y seguridad

## Encaje en el RGPD

- **La seudonimización sigue siendo tratamiento de datos personales** (art. 4.5 RGPD). La reducción de identificabilidad no equivale a la anonimización del considerando 26: aunque se destruya la tabla de correspondencias, la persona puede seguir siendo identificable por el contexto, por hechos singulares, por fechas o por combinaciones de atributos.
- El tratamiento local **minimiza la exposición, pero no garantiza por sí solo el cumplimiento**. Siguen aplicándose los arts. 5, 25 y 32 RGPD, el art. 9 cuando haya categorías especiales (por ejemplo, informes médicos), el art. 35 cuando proceda y el deber de confidencialidad del art. 5 LOPDGDD.
- Cada despacho debe documentar su uso de la herramienta: acceso, conservación y revisión humana antes de comunicar a terceros los expedientes de alto riesgo.
- La aplicación **no se comercializa como garantía automática** de cumplimiento ni de anonimización absoluta. Los estados que muestra son «sin hallazgos en las comprobaciones configuradas», «requiere revisión» y «error de procesamiento».

## Modos de la tabla de correspondencias

| Modo | Qué se guarda | Para qué |
|---|---|---|
| Guardar cifrada | `registro.seudonimo`, cifrado con Fernet. La clave va en el Llavero de Mac o en el Administrador de credenciales de Windows. Si no hay almacén, en un archivo con permisos solo del usuario, y se advierte | Seudonimización reversible y coherencia entre lotes del mismo proyecto |
| No guardar | Nada: el registro vive en memoria durante el lote | Reducir la identificabilidad sin tabla persistente. No hace irreversible la seudonimización |

Al borrar un proyecto se destruyen la tabla y su clave (borrado criptográfico). La exportación de la tabla en claro es una **acción explícita** del usuario, a una ruta que él elige, con aviso si esa carpeta está sincronizada con la nube.

## Medidas técnicas

- **Sin red para los documentos.** El servicio escucha solo en 127.0.0.1, en un puerto elegido al arrancar, con un token efímero en cada petición. Se valida el Host (contra DNS rebinding) y el Origin. El único destino de red es Ollama, también en 127.0.0.1.
- **Sin telemetría.** Internet solo se usa para descargar Ollama y los modelos que el usuario elija.
- **Permisos.** El modelo solo ve los archivos que el usuario añade al proyecto con el diálogo del sistema. No sigue enlaces simbólicos fuera de la carpeta autorizada. No tiene acceso a terminal ni ejecuta código.
- **Instrucciones dentro de documentos.** El texto de los documentos se entrega al modelo como datos no confiables. Las herramientas tienen esquema y validación. Seudonimizar es un plan que confirma el usuario.
- **Originales intactos.** Se trabaja sobre una copia de solo lectura. Nunca se sobrescribe el archivo del usuario.
- **Temporales.** Las copias de trabajo y los ciclos se borran al terminar cada lote. La base de datos (SQLite) no guarda el texto de los documentos. El registro técnico (`registro.log`) no contiene texto de documentos. Los proyectos temporales se borran al cerrar.
- **Carpetas sincronizadas.** Los resultados van por defecto a `~/Seudónimo`, fuera de Documentos y Escritorio, que suelen estar en iCloud u OneDrive. Si se elige una carpeta sincronizada, la aplicación lo advierte.
- **Dictado por voz.** El audio se graba en la ventana solo mientras el botón «Dictar» está activo, se escribe en un temporal de la carpeta de trabajo, lo transcribe whisper-cli en el propio equipo y se borra en el acto. No se guarda audio ni se envía a ningún servicio. El texto dictado queda en la caja de mensaje como si se hubiera tecleado.
