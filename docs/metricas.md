# Métricas sobre el corpus sintético

Corpus: `pruebas/corpus/generar_corpus.py` (12 documentos, 345 datos sensibles etiquetados). Equipo: Mac mini M4, 16 GB, gemma4:12b (nvfp4, 100 % GPU, contexto 8.192). Evaluador: `pruebas/evaluar.py`, que relee cada copia exportada: texto, OCR y todas las partes internas de los archivos de Office.

## 26/11/2026 · versión 0.1.0 · perfil estándar

| Métrica | Resultado |
|---|---|
| **Recall crítico** | **100 %** (345/345; 0 fugas) |
| Conservación de datos necesarios (antigüedad, periodo de liquidación, importes, categoría) | 100 % |
| Estado final correcto | 12 de 12 (el contrato con control de cambios va a «Para revisar», como se espera) |
| Precisión de las detecciones | 92,8 % de 195 formas |
| Duración total | 578 s (9 min 38 s) |

Recall por categoría, todas al 100 %:

| Categoría | Etiquetados |
|---|---|
| PERSONA | 58 |
| TELEFONO | 40 |
| DNI | 38 |
| EMAIL | 38 |
| DOMICILIO | 37 |
| IBAN | 32 |
| NAF | 32 |
| F_NACIMIENTO | 29 |
| DEPARTAMENTO | 20 |
| EMPRESA | 7 |
| NIF | 6 |
| CCC | 5 |
| CSV | 1 |
| REGISTRO | 1 |
| EXPEDIENTE | 1 |

Detecciones sin etiqueta: son sobre-tachados inocuos, no datos perdidos.

- Códigos postales sueltos, marcados como domicilio. Son cuasi-identificadores: taparlos es prudente.
- Trozos de NAF y CCC cubiertos dos veces, por la regla de teléfono o la de domicilio («C.C.C. 35…»).
- «Recursos Humanos», como departamento.
- La nota al pie que nombra a la aplicación, como empresa.

Tiempo de inferencia por documento:

| Documento | Segundos |
|---|---|
| Evaluación del desempeño (15 personas, 23 columnas) | 241 |
| Listado CSV | 159 |
| Carta de sanción y certificado (PDF de 2 páginas) | 36 |
| Contrato (Word) | 27 |
| Cada uno de los demás | 8–16 |

OCR, transformación y verificación determinista: menos de 2 s por documento. La segunda pasada de detección (auditor sobre el texto enmascarado) no encontró datos nuevos en ningún documento de este corpus.

### Lectura

- La combinación de reglas y modelo cubre el corpus completo en modo estándar. El cuello de botella son las tablas densas: muchos datos por fragmento.
- El corpus es sintético y conocido. **Estos resultados no prometen cero errores con documentos reales.** Cada fallo que aparezca en un uso real debe añadirse al corpus como prueba de regresión permanente.
- Pendiente: medir el perfil intensivo y comparar 1, 2, 3 y 5 pasadas con documentos más difíciles (manuscritos, fotos torcidas, nombres poco frecuentes o partidos).

## 26/11/2026 · prueba de la aplicación de escritorio (Mac, ventana Tauri)

Flujo completo en la aplicación instalada, con gemma4:12b:

1. Crear el proyecto y añadir la carpeta. El inventario rechaza `etiquetas.json` y explica el motivo.
2. Pedir en lenguaje natural «Seudonimiza la nómina, el contrato y las notas de la reunión con verificación intensiva». El modelo llama a la herramienta, identifica los tres archivos y el perfil, y la aplicación muestra el plan para confirmarlo.
3. Ejecutar con la pista de pasadas en directo. Resultado:
   - Las notas, sin hallazgos.
   - El contrato, a revisión por el control de cambios (correcto).
   - La nómina, a revisión por un resto `[CCC_002]`.
4. Diagnóstico del caso de la nómina. El OCR de verificación leyó el marcador `[CCC_001]` como «ICCC.0011» y el auditor lo tomó por una cuenta de cotización. Era una falsa alarma conservadora, no una fuga. **Corregido**: el patrón de marcadores deformados admite «.» y «,» como separador. El caso queda como prueba de regresión en `pruebas/test_nucleo.py`.
5. Revisión humana:
   - Descartar `[CCC_002]` y el falso positivo `[EMPRESA_003]`.
   - Regenerar las copias, sin repetir la detección. La nómina queda sin hallazgos.
   - Comprobación visual: datos sustituidos; antigüedad, periodo de liquidación, categoría e importes intactos.

Aparente incidencia cosmética, ya explicada: en la nómina sintética, «N.º afili-» aparece tapado. No es un fallo del motor. El tachón del número de afiliación empieza después de la etiqueta (x = 382,6 frente a 380,0). Lo que tapa ese trozo es el tachón del domicilio de la empresa: en el documento generado, esa dirección es tan larga que invade la columna derecha en la misma línea. Es un defecto del generador del corpus, no de la seudonimización.
