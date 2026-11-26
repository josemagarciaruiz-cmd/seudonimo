# Cambios

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
