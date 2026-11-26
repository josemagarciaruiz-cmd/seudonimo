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
