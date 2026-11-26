# Matriz de formatos

Compatibilidad explícita, no universal. Lo que no está en esta tabla se rechaza en el inventario con su motivo.

| Formato | Lectura | Seudonimización | Formato de salida | Verificación estructural | Limitaciones conocidas |
|---|---|---|---|---|---|
| PDF nativo | Texto con pypdfium2 | Las páginas con datos se rasterizan y se reconstruyen desde el original inmutable, con capa de texto solo de lo visible | PDF | Revisiones incrementales, adjuntos, metadatos, anotaciones, texto recuperable | Las páginas afectadas pierden el texto vectorial, los enlaces y la accesibilidad. Un PDF firmado pierde la validez de la firma: la copia no equivale al documento firmado |
| PDF escaneado | OCR: Vision (Mac) o Tesseract (Windows), con relectura de las páginas ya tapadas a 360 y 420 ppp | Píxeles destruidos en la imagen reconstruida | PDF | Igual que el nativo, más OCR a otra resolución en cada verificación | Los nombres manuscritos y las firmas pueden exigir revisión humana |
| Word (.docx) | XML (OOXML) directo | Sustitución dentro de los *runs*, conservando el formato: cuerpo, encabezados, pies, notas, comentarios y texto borrado de cambios controlados | .docx | Partes internas con datos originales, control de cambios, objetos incrustados, imágenes internas (OCR) | Un documento con control de cambios va siempre a revisión. Los objetos incrustados no se revisan |
| Excel (.xlsx) | XML directo | Cadenas compartidas, celdas en línea, números largos, comentarios (también los encadenados) y autores | .xlsx | Hojas ocultas (aviso), cachés de tablas dinámicas, objetos incrustados | Los literales dentro de fórmulas no se alteran |
| PowerPoint (.pptx) | XML directo | Diapositivas y notas del orador | .pptx | Partes internas, objetos incrustados, imágenes internas (OCR) | Los patrones y diseños no se tocan |
| .doc, .xls, .ppt, .rtf, .odt, .ods, .odp | Conversión previa: Word, Excel o PowerPoint en Windows; textutil en Mac (.doc, .rtf, .odt); LibreOffice si está instalado | Como su equivalente OOXML | El formato moderno equivalente | Como OOXML | Sin conservación perfecta del formato |
| .docm, .xlsm, .pptm | — | Se rechazan | — | — | Contienen macros |
| CSV, TSV, TXT, MD | Detección de codificación (UTF-8, UTF-8 con BOM, cp1252) | Sustitución en el texto, con el mismo delimitador y la misma codificación | El mismo | — | Los marcadores empiezan por «[»: no crean fórmulas peligrosas en hojas de cálculo |
| Imágenes (PNG, JPG, TIFF, WEBP, BMP; HEIC en Mac) | OCR | Píxeles destruidos | PDF y la imagen re-renderizada, sin EXIF | EXIF de la imagen exportada | Avatares y caras no se detectan |
| Archivos cifrados o dañados | — | Error de procesamiento | — | — | — |
| EML, MSG, ZIP | — | Fase posterior | — | — | — |
