# Seudonimización multipasada y verificación iterativa

Implementación del anexo técnico (correo del 25/11/2026) en `nucleo/multipasada.py`, `nucleo/verificacion.py` y `nucleo/registro.py`.

## Principio

El **controlador es código determinista**. El modelo identifica entidades. El motor documental modifica los archivos. El controlador decide cuándo repetir y cuándo parar. El ciclo termina por **convergencia**, por **límites** o por **error**, nunca porque el modelo declare que el documento está limpio.

## Pasadas

| Pasada | Qué hace | Por qué es distinta de la anterior |
|---|---|---|
| Detección 1 | Texto nativo y OCR, reglas (DNI/NIE, NIF, NAF, CCC, IBAN, teléfono, correo, matrícula, CSV/CEA, registro, domicilio con tipo de vía) y modelo con el prompt de detección, más una segunda lectura de las costuras entre fragmentos | — |
| Detección 2 | El texto con lo hallado ya sustituido por marcadores, a un **auditor** con otro prompt y otros cortes entre fragmentos | Otro enfoque y otro contexto. Lo que se le escapó al primero queda rodeado de marcadores y salta a la vista |
| Verificación A, B, C… | Se **reabre la copia desde el disco**. Se extraen de nuevo el texto y el OCR (300, 420 y 360 ppp). Se buscan los datos conocidos de todo el proyecto en todas sus variantes, se pasan otra vez las reglas y, en modo intensivo, un modelo auditor alterna el prompt A (datos escapados) y el B (restos parciales: nombres sueltos, iniciales, firmas, saludos, siglas). Se inspecciona la estructura del archivo | Cada ciclo cambia la resolución del OCR, el prompt y los cortes, para que las pasadas no repitan los mismos errores |

Los marcadores ya insertados se reconocen como marcadores, también deformados por el OCR («[CSV_001]» leído como «tcsv_001»).

## Transformación

Cada ciclo **reconstruye desde el original inmutable** (una copia de solo lectura) con el registro actualizado. No se edita la copia anterior, así que el PDF no se degrada ni se rasteriza encima de lo ya rasterizado.

Un hallazgo de la verificación que también está en la lectura del original se incorpora con normalidad. Uno que solo aparece en la copia (el OCR del original lo leyó mal) también se incorpora: la reconstrucción vuelve a leer las páginas escaneadas a 360 y 420 ppp y lo tapa por coordenadas. Si aun así sigue en la siguiente copia, pasa a «restos».

## Criterio de parada

| Parámetro | Estándar | Intensiva |
|---|---|---|
| Pasadas de detección | 2 | 2 |
| Ciclos máximos | 3 | 5 |
| Verificaciones limpias seguidas exigidas | 1 | 2 |
| Modelo auditor en la verificación | No (la verificación es determinista) | Sí |
| Tiempo máximo por documento | 1 h | 3 h |

Son **parámetros de ingeniería provisionales**, no umbrales validados. Se ajustan con el corpus (`pruebas/evaluar.py`).

Estados finales:

- **Sin hallazgos en las comprobaciones configuradas**: las verificaciones exigidas no encuentran datos nuevos, ni restos, ni incidencias graves.
- **Requiere revisión**: máximo de ciclos, tiempo agotado, datos conocidos que siguen en la copia sin poder localizarse (bucle sin progreso), o incidencias estructurales graves (control de cambios, objetos incrustados, adjuntos, revisiones incrementales, datos en metadatos o en partes ocultas, EXIF).
- **Error de procesamiento**: el documento no se puede leer o escribir.

Nunca se usa «anonimización garantizada». Dos verificaciones sin hallazgos no descartan falsos negativos correlacionados.

## Coherencia del lote

Un único registro por proyecto, con etiquetas estables (`[PERSONA_001]`). Cuando un documento posterior aporta una variante que aparece en uno anterior, el anterior se reconstruye y se verifica de nuevo, con un máximo de rondas globales. No se fusionan homónimos: una forma que encaja con varias personas recibe su propia etiqueta y se marca como ambigua para revisión.

Lo que el usuario descarta en la revisión («no es un dato personal») queda anotado y no vuelve a proponerse en las pasadas siguientes.

## Exportación

`Aprobados/` y `Para revisar/` se guardan separadas y nunca se mezclan. Los archivos con error no se exportan. El *Informe de verificación* (HTML y JSON) usa nombres de archivo ya seudonimizados y no contiene datos originales: solo estados, pasadas, recuentos por categoría, motivos y tiempos.
