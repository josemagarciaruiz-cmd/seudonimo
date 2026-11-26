# Cambios

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
