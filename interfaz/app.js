/* Seudónimo · interfaz
   Sin frameworks. Habla con el servicio local (127.0.0.1) con un token efímero.
   En la ventana de escritorio (Tauri) usa los diálogos nativos; en modo navegador, el servicio. */
"use strict";

const T = window.__TAURI__ || null;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const E = {
  conexion: null,
  salud: null,
  modelos: [],
  proyectos: [],
  proyecto: null,        // ficha completa del proyecto activo
  conversacion: null,    // id
  conversaciones: {},    // pid -> lista
  trabajos: {},          // id -> estado
  sondeo: null,
  enviando: false,
};

const fondo = () => E.proyecto?.perfil === "intensivo";       // «Revisión a fondo» se elige en los ajustes del expediente
const modeloActual = () => E.proyecto?.modelo || E.modeloDefecto;

const ESTADOS = {
  nuevo: "Sin tratar", no_admitido: "No admitido", en_cola: "En cola", procesando: "Procesando",
  sin_hallazgos: "Lista", revision: "Revísala", error: "Error", cancelado: "Cancelado", pendiente: "Pendiente",
  interrumpido: "Interrumpido (se cerró la aplicación)", parcial: "Copia de algunas páginas",
};

// ------------------------------------------------------------------ conexión

async function conectar() {
  if (window.SEUDONIMO_CONEXION) return { base: "", token: window.SEUDONIMO_CONEXION.token };
  if (T) {
    const c = await T.core.invoke("conexion");   // puerto y token que ha elegido la ventana
    const base = `http://127.0.0.1:${c.puerto}`;
    for (let i = 0; i < 180; i++) {               // el servicio tarda unos segundos en arrancar
      try {
        const r = await fetch(base + "/api/salud", { headers: { "X-Seudonimo-Token": c.token } });
        if (r.ok) return { base, token: c.token };
      } catch (e) { /* aún arranca */ }
      await new Promise((r) => setTimeout(r, 500));
    }
  }
  throw new Error("El servicio local no responde. Cierra la aplicación y vuelve a abrirla.");
}

async function api(metodo, ruta, cuerpo) {
  const r = await fetch(E.conexion.base + ruta, {
    method: metodo,
    headers: { "Content-Type": "application/json", "X-Seudonimo-Token": E.conexion.token },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  let datos = null;
  try { datos = await r.json(); } catch (e) { /* vacío */ }
  if (!r.ok) throw new Error((datos && datos.error) || `Error ${r.status}`);
  return datos;
}

async function elegir(tipo) {
  if (T && T.dialog) {
    if (tipo === "carpeta") return [].concat((await T.dialog.open({ directory: true, multiple: true, title: "Elige las carpetas" })) || []);
    if (tipo === "archivos") return [].concat((await T.dialog.open({ multiple: true, title: "Elige los archivos" })) || []);
    if (tipo === "carpeta_salida") return [].concat((await T.dialog.open({ directory: true, title: "Carpeta de resultados" })) || []);
    if (tipo === "guardar") return [].concat((await T.dialog.save({ title: "Guardar la tabla de correspondencias", defaultPath: "Tabla de correspondencias.csv" })) || []);
  }
  const r = await api("POST", "/api/sistema/elegir", { tipo: tipo === "carpeta_salida" ? "carpeta" : tipo });
  return r.rutas || [];
}

// ------------------------------------------------------------------ arranque

async function iniciar() {
  try {
    E.conexion = await conectar();
  } catch (e) {
    document.body.innerHTML = `<div class="vacio"><h2>No se ha podido arrancar Seudónimo</h2><p>${esc(e.message || e)}</p></div>`;
    return;
  }
  enlazar();
  await refrescarSalud();
  await refrescarModelos();
  await refrescarProyectos();
  if (E.proyectos.length) await abrirProyecto(E.proyectos[0].id);
  else pintarBienvenida();
  setInterval(refrescarSalud, 15000);
  refrescarCola();
  setTimeout(buscarActualizacion, 4000);
  if (T && T.webview) {
    // arrastrar archivos o carpetas sobre la ventana los añade al proyecto
    try {
      T.webview.getCurrentWebview().onDragDropEvent((ev) => {
        document.body.classList.toggle("soltando", ["enter", "over"].includes(ev.payload.type));
        if (ev.payload.type === "drop" && ev.payload.paths?.length) {
          if (E.proyecto) anadirRutas(ev.payload.paths);
          else expedienteDesde(ev.payload.paths).catch((e) => alerta(e.message));
        }
      });
    } catch (e) { /* versión sin soporte */ }
  }
}

async function refrescarSalud() {
  try {
    E.salud = await api("GET", "/api/salud");
    $("#version").textContent = `Versión ${E.salud.version}`;
    const el = $("#estado-motor");
    el.className = "estado-motor " + (E.salud.ollama ? "ok" : "mal");
    el.textContent = E.salud.ollama ? "Motor local activo" : (E.salud.instalado ? "Ollama detenido" : "Falta Ollama");
    pintarAviso();
  } catch (e) { /* sigue */ }
}

async function refrescarModelos() {
  try {
    const r = await api("GET", "/api/modelos");
    E.modelos = r.instalados || [];
    E.modeloDefecto = r.defecto;
    E.catalogo = r;
  } catch (e) { E.modelos = []; }
  pintarAviso();
}

function pintarAviso() {
  const b = $("#aviso-banda");
  let html = "";
  const rec = (E.catalogo?.catalogo || []).find((m) => m.recomendado) || (E.catalogo?.catalogo || [])[0];
  const bajando = Object.values(E.catalogo?.descargas || {}).find((d) => d.fase === "trabajando");
  if (E.salud && !E.salud.instalado && !E.salud.ollama) {
    html = `<span><b>Preparar este ordenador · paso 1 de 2.</b> Instala Ollama, el programa gratuito que ejecuta el modelo de IA dentro de este ordenador. Es una sola vez.</span><button class="boton boton-principal" data-accion="instalar-ollama">Instalar Ollama</button>`;
  } else if (E.salud && !E.salud.ollama) {
    html = `<span>Ollama está instalado pero detenido. Ábrelo (está en Aplicaciones) y Seudónimo lo detectará solo.</span>`;
  } else if (E.salud && E.salud.ollama && !E.modelos.length) {
    html = bajando ? `<span><b>Preparar este ordenador · paso 2 de 2.</b> Descargando el modelo… ${Math.round((bajando.progreso || 0) * 100)} %. Puedes ir creando el expediente mientras tanto.</span>`
      : `<span><b>Preparar este ordenador · paso 2 de 2.</b> Descarga el modelo de IA${rec ? ` recomendado (${esc(rec.nombre)}, unos ${rec.memoria} GB de memoria)` : ""}. Después funciona sin conexión.</span>
        ${rec ? `<button class="boton boton-principal" data-descargar="${esc(rec.nombre)}">Descargar el modelo</button>` : ""}<button class="boton-texto" data-accion="abrir-modelos">Elegir otro</button>`;
    if (bajando) setTimeout(async () => { await refrescarModelos(); }, 2000);
  } else if (E.proyecto && E.modelos.length && !E.modelos.some((m) => m.nombre === modeloActual())) {
    html = `<span>El modelo de este expediente (${esc(E.proyecto.modelo)}) no está descargado.</span><button class="boton" data-accion="abrir-modelos">Gestionar modelos</button>`;
  }
  b.innerHTML = html;
  b.hidden = !html;
}

// ------------------------------------------------------------------ proyectos y conversaciones

async function refrescarProyectos() {
  E.proyectos = await api("GET", "/api/proyectos");
  await Promise.all(E.proyectos.map(async (p) => { E.conversaciones[p.id] = await api("GET", `/api/proyectos/${p.id}/conversaciones`); }));
  pintarLateral();
}

function pintarLateral() {
  const el = $("#lista-proyectos");
  if (!E.proyectos.length) { el.innerHTML = `<p class="nota" style="padding:8px">Todavía no hay expedientes.</p>`; return; }
  el.innerHTML = E.proyectos.map((p) => {
    const activo = E.proyecto && E.proyecto.id === p.id;
    // un expediente es un chat: las conversaciones anteriores están en «Expediente ▾ > Conversaciones»
    return `<div class="proyecto${activo ? " activo" : ""}">
      <div class="fila">
        <button class="proyecto-cab" data-proyecto="${p.id}">${esc(p.nombre)}${p.temporal ? ' <span class="temporal">temporal</span>' : ""}</button>
        <button class="mas" data-menu-proyecto="${p.id}" aria-label="Opciones del expediente ${esc(p.nombre)}" title="Opciones">⋯</button>
      </div>
    </div>`;
  }).join("");
}

// ------------------------------------------------------------------ menús de proyectos y conversaciones

function abrirMenu(boton, opciones) {
  cerrarMenu();
  const m = document.createElement("div");
  m.className = "menu";
  m.id = "menu";
  m.setAttribute("role", "menu");
  m.innerHTML = opciones.map((o, i) => `<button role="menuitem" class="${o.peligro ? "peligro" : ""}" data-i="${i}">${esc(o.texto)}</button>`).join("");
  document.body.append(m);
  const r = boton.getBoundingClientRect();
  m.style.top = Math.min(r.bottom + 4, window.innerHeight - m.offsetHeight - 8) + "px";
  m.style.left = Math.min(r.left, window.innerWidth - m.offsetWidth - 8) + "px";
  m.addEventListener("click", async (ev) => {
    const b = ev.target.closest("button[data-i]");
    if (!b) return;
    ev.stopPropagation();
    cerrarMenu();
    try { await opciones[+b.dataset.i].accion(); } catch (e) { alerta(e.message); }
  });
  m.querySelector("button")?.focus();
}

function cerrarMenu() { $("#menu")?.remove(); }

function pedirTexto(titulo, valor, aceptar = "Guardar") {
  const d = $("#dlg-texto");
  $("#texto-titulo").textContent = titulo;
  $("#texto-aceptar").textContent = aceptar;
  const i = $("#texto-valor");
  i.value = valor || "";
  d.showModal();
  i.select();
  return new Promise((res) => d.addEventListener("close", () => res(d.returnValue === "si" ? i.value.trim() : null), { once: true }));
}

function menuProyecto(boton, pid) {
  const p = E.proyectos.find((x) => x.id === pid);
  abrirMenu(boton, [
    { texto: "Renombrar", accion: async () => {
      const n = await pedirTexto("Renombrar el expediente", p.nombre);
      if (!n) return;
      await api("PATCH", `/api/proyectos/${pid}`, { nombre: n });
      await refrescarProyectos();
      if (E.proyecto?.id === pid) { E.proyecto.nombre = n; $("#titulo-proyecto").textContent = n; }
    } },
    { texto: "Ajustes del expediente", accion: async () => { if (E.proyecto?.id !== pid) await abrirProyecto(pid); abrirDialogoProyecto(true); } },
    { texto: "Eliminar expediente", peligro: true, accion: () => eliminarProyecto(pid) },
  ]);
}

function menuConversacion(boton, cid) {
  const c = (E.conversaciones[E.proyecto.id] || []).find((x) => x.id === cid);
  const otros = E.proyectos.filter((p) => p.id !== E.proyecto.id);
  abrirMenu(boton, [
    { texto: "Renombrar", accion: async () => {
      const n = await pedirTexto("Renombrar la conversación", c.titulo);
      if (!n) return;
      await api("PATCH", `/api/conversaciones/${cid}`, { titulo: n });
      await refrescarConversaciones();
    } },
    ...(otros.length ? [{ texto: "Mover a otro expediente…", accion: () => moverConversacion(cid, otros) }] : []),
    { texto: "Eliminar conversación", peligro: true, accion: async () => {
      if (!await confirmar("Eliminar la conversación", `Se eliminará «${c.titulo}» con todos sus mensajes. Los documentos del expediente y las copias seudonimizadas no se tocan.`, "Eliminar")) return;
      await api("DELETE", `/api/conversaciones/${cid}`);
      await refrescarConversaciones();
      if (E.conversacion === cid) {
        const resto = E.conversaciones[E.proyecto.id];
        if (resto.length) await abrirConversacion(resto[0].id);
        else { E.conversacion = null; $("#titulo-conversacion").textContent = ""; pintarVacioProyecto(); pintarLateral(); }
      }
    } },
  ]);
}

async function moverConversacion(cid, otros) {
  const d = $("#dlg-mover");
  $("#mover-destino").innerHTML = otros.map((p) => `<option value="${p.id}">${esc(p.nombre)}</option>`).join("");
  d.showModal();
  const ok = await new Promise((res) => d.addEventListener("close", () => res(d.returnValue === "si"), { once: true }));
  if (!ok) return;
  const destino = +$("#mover-destino").value;
  await api("PATCH", `/api/conversaciones/${cid}`, { proyecto: destino });
  await refrescarProyectos();
  await abrirProyecto(destino, cid);
}

async function refrescarConversaciones() {
  E.conversaciones[E.proyecto.id] = await api("GET", `/api/proyectos/${E.proyecto.id}/conversaciones`);
  const c = E.conversaciones[E.proyecto.id].find((x) => x.id === E.conversacion);
  $("#titulo-conversacion").textContent = c ? c.titulo : "";
  pintarLateral();
}

async function eliminarProyecto(pid) {
  const p = E.proyectos.find((x) => x.id === pid);
  const ok = await confirmar("Eliminar el expediente", `Se eliminarán «${p.nombre}», sus conversaciones, su lista de datos tapados y la clave que permite recuperar los nombres. Tus documentos originales y las copias ya guardadas no se tocan.`, "Eliminar expediente");
  if (!ok) return;
  if ($("#dlg-proyecto").open) $("#dlg-proyecto").close("cancelar");
  await api("DELETE", `/api/proyectos/${pid}`);
  if (E.proyecto?.id === pid) { E.proyecto = null; E.conversacion = null; }
  await refrescarProyectos();
  if (E.proyecto) pintarLateral();
  else if (E.proyectos.length) await abrirProyecto(E.proyectos[0].id);
  else pintarBienvenida();
}

async function abrirProyecto(pid, conv) {
  E.proyecto = await api("GET", `/api/proyectos/${pid}`);
  $("#titulo-conversacion").textContent = "";
  E.conversaciones[pid] = await api("GET", `/api/proyectos/${pid}/conversaciones`);
  $("#titulo-proyecto").textContent = E.proyecto.nombre;
  $("#menu-expediente").hidden = false;
  $("#redactor").hidden = false;
  await refrescarModelos();
  const convs = E.conversaciones[pid];
  E.conversacion = conv || (convs[0] && convs[0].id) || null;
  pintarLateral();
  pintarArchivos();
  await refrescarOperaciones();
  if (E.conversacion) await abrirConversacion(E.conversacion);
  else pintarVacioProyecto();
}

async function abrirConversacion(cid) {
  E.conversacion = cid;
  const c = await api("GET", `/api/conversaciones/${cid}`);
  $("#titulo-conversacion").textContent = (E.conversaciones[E.proyecto.id] || []).length > 1 ? (c.titulo || "") : "";
  const hilo = $("#hilo");
  hilo.innerHTML = "";
  if (!c.mensajes.length) pintarVacioProyecto();
  for (const m of c.mensajes) {
    if (m.rol === "usuario") hilo.append(nodoUsuario(m.contenido));
    else hilo.append(nodoAsistente(m));
  }
  pintarLateral();
  hilo.scrollTop = hilo.scrollHeight;
}

async function nuevaConversacion() {
  const c = await api("POST", `/api/proyectos/${E.proyecto.id}/conversaciones`);
  E.conversaciones[E.proyecto.id] = await api("GET", `/api/proyectos/${E.proyecto.id}/conversaciones`);
  E.conversacion = c.id;
  pintarLateral();
  $("#titulo-conversacion").textContent = "";
  $("#hilo").innerHTML = "";
  pintarVacioProyecto();
  $("#entrada").focus();
}

function pintarBienvenida() {
  $("#titulo-proyecto").textContent = "Seudónimo";
  $("#titulo-conversacion").textContent = "";
  $("#redactor").hidden = true;
  $("#menu-expediente").hidden = true;
  $("#hilo").innerHTML = `<div class="vacio bienvenida">
    <h2>Tus expedientes, sin salir de este ordenador</h2>
    <p>Seudónimo cambia los nombres, DNI, direcciones y demás datos de tus documentos por marcadores ([PERSONA_001]…) para que puedas usarlos con otra IA sin que salgan datos de tus clientes. Todo ocurre en este ordenador.</p>
    <div class="zona-soltar grande"><b>Arrastra aquí la carpeta de un expediente</b><span>Se crea el expediente con el nombre de la carpeta. Los originales no se tocan.</span></div>
    <div class="plan-acciones centrado"><button class="boton boton-principal" data-accion="nuevo-proyecto">Nuevo expediente</button><button class="boton" data-accion="expediente-desde-carpeta">Elegir la carpeta…</button></div>
    ${ejemplosChat("Y después se lo pides al asistente con tus palabras, escribiendo o dictando:", false)}
  </div>`;
  $("#panel-archivos").innerHTML = `<p class="nota">Crea un expediente para añadir sus documentos.</p>`;
}

const EJEMPLOS = [
  "Seudonimiza todos los documentos",
  "Seudonimiza solo la página 6 del informe",
  "En la página 2 se ve \"Rodríguez\", tápalo",
  "¿Dónde está la copia de la carta de despido?",
  "Guarda las copias en el Escritorio",
  "¿Qué documentos necesitan revisión?",
];

function ejemplosChat(titulo, activos = true) {
  return `<div class="ejemplos"><p>${esc(titulo)}</p><div class="sugerencias">${EJEMPLOS.map((x) => activos
    ? `<button class="sugerencia" data-rellenar="${esc(x)}">${esc(x)}</button>` : `<span class="sugerencia muda">${esc(x)}</span>`).join("")}</div></div>`;
}

function pendientes() {
  return (E.proyecto?.archivos || []).filter((a) => a.admitido && ["nuevo", "error", "cancelado", "interrumpido"].includes(a.estado));
}

function pintarVacioProyecto() {
  const adm = (E.proyecto.archivos || []).filter((a) => a.admitido);
  const pend = pendientes();
  const hechos = adm.filter((a) => ["sin_hallazgos", "revision", "parcial"].includes(a.estado)).length;
  const enCurso = adm.filter((a) => ["en_cola", "procesando"].includes(a.estado)).length;
  const situacion = enCurso
    ? `<p>Seudonimizando ${enCurso === 1 ? "un documento" : enCurso + " documentos"}. El avance se ve en la lista de la derecha; al terminar te dejo aquí el resumen con las copias.</p>`
    : !adm.length
    ? `<p>Añade los documentos del asunto: arrástralos a esta ventana o pulsa «Añadir» en la lista de la derecha. Los originales nunca se modifican.</p>
       <div class="plan-acciones centrado"><button class="boton boton-principal" data-accion="adjuntar-carpeta">Añadir una carpeta</button><button class="boton" data-accion="adjuntar-archivos">Añadir archivos</button></div>`
    : pend.length
    ? `<p>${pend.length === 1 ? "Hay un documento pendiente" : `Hay ${pend.length} documentos pendientes`}. Pulsa el botón o pídemelo abajo.</p>
       <div class="plan-acciones centrado"><button class="boton boton-principal boton-grande" data-accion="seudonimizar-pendientes">Seudonimizar ${pend.length === 1 ? "el documento" : "los " + pend.length + " documentos"}</button></div>`
    : hechos ? `<p>${hechos === 1 ? "El documento está seudonimizado" : `Los ${hechos} documentos están seudonimizados`}. Las copias están en la lista de la derecha: «Abrir copia» las abre.</p>` : "";
  $("#hilo").innerHTML = `<div class="vacio guia">
    <h2>${esc(E.proyecto.nombre)}</h2>
    ${situacion}
    ${ejemplosChat("Pídeme lo que necesites con tus palabras, escribiendo o con el micrófono. Por ejemplo:")}
  </div>`;
}

// ------------------------------------------------------------------ mensajes

function nodoUsuario(texto) {
  const d = document.createElement("div");
  d.className = "msg msg-usuario";
  d.innerHTML = `<div class="burbuja">${esc(texto)}</div>`;
  return d;
}

function nodoAsistente(m) {
  const d = document.createElement("div");
  d.className = "msg msg-asistente";
  const datos = m.datos || {};
  const herr = (datos.herramientas || []).map((h) => `<div class="herramienta${h.ok ? "" : " error"}">${esc(nombreHerramienta(h.nombre))}${h.resumen ? ": " + esc(h.resumen) : ""}</div>`).join("");
  d.innerHTML = `${herr}<div class="prosa">${markdown(m.contenido || "")}</div>`;
  for (const plan of datos.planes || []) d.append(nodoPlan(plan, m.id, datos));
  if (datos.resultado) d.append(nodoResultado(datos.resultado));
  return d;
}

function nombreHerramienta(n) {
  return { inspeccionar_carpeta: "Inventario del expediente", inspeccionar_documento: "Ficha del documento", extraer_texto: "Lectura del documento",
    seudonimizar: "Plan de seudonimización", estado_trabajos: "Estado de los trabajos", verificar_documento: "Auditoría del documento",
    tapar: "Datos para tapar", donde_esta: "Dónde están", guardar_copia: "Guardar en otra carpeta" }[n] || n;
}

// ------------------------------------------------------------------ resultados: componentes

const EN_MAC = /Mac/i.test(navigator.platform || navigator.userAgent);
const EXPLORADOR = EN_MAC ? "Finder" : "su carpeta";

function filaResultado(c) {
  // c: {id, original, nombre, ruta, estado}
  const nombre = c.nombre || (c.ruta || "").split(/[\\/]/).pop();
  const estado = c.estado === "sin_hallazgos" ? "Lista" : c.estado === "revision" ? "Revísala antes de usarla" : c.estado === "parcial" ? "Solo unas páginas" : ESTADOS[c.estado] || c.estado;
  return `<div class="resultado-doc">
    <span class="punto ${esc(c.estado)}" aria-hidden="true"></span>
    <div class="resultado-info"><b title="${esc(c.ruta || "")}">${esc(nombre)}</b><span class="nota">${esc(estado)} · original: ${esc(c.original || "")}</span></div>
    <div class="botones-fila">
      <button class="boton boton-chico" data-abrir="${esc(c.ruta)}">Abrir copia</button>
      ${c.id ? `<button class="boton boton-chico${c.estado === "revision" ? " aviso" : ""}" data-revisar="${c.id}" title="Ver la copia y tapar a mano lo que falte">Revisar</button>
      <button class="boton boton-chico" data-contexto="${c.id}" title="¿Se podría reconocer a la persona por la suma de datos indirectos?">Comprobar riesgo</button>` : ""}
      <button class="boton-texto mas-doc" data-menu-copia="${esc(c.ruta)}" data-doc="${c.id || ""}" data-nombre="${esc(c.original || nombre)}" aria-label="Más opciones" title="Más opciones">⋯</button>
    </div></div>`;
}

function bloqueCarpetas(carpetas, certificado) {
  if (!carpetas.length && !certificado) return "";
  return `<div class="resultado-donde">
    ${carpetas.map((c) => `<div class="donde-fila"><span class="nota">Guardados en</span> <code title="${esc(c)}">${esc(c)}</code> <button class="boton-texto" data-abrir="${esc(c)}">Abrir la carpeta</button></div>`).join("")}
    ${certificado ? `<div class="donde-fila"><span class="nota">Certificado de la seudonimización</span> <button class="boton-texto" data-abrir="${esc(certificado)}">Abrir</button> <button class="boton-texto" data-guardar-en="${esc(certificado)}">Guardar en…</button></div>` : ""}
  </div>`;
}

function nodoResultado(res) {
  // tarjeta «Listo» al terminar una seudonimización pedida desde el chat
  const d = document.createElement("div");
  d.className = "plan tarjeta-listo";
  const hechos = (res.documentos || []).filter((x) => x.copia);
  const fallos = (res.documentos || []).filter((x) => !x.copia);
  const rev = hechos.filter((x) => x.estado === "revision").length;
  d.innerHTML = `<h4>${hechos.length ? (rev ? `Listo · ${rev === 1 ? "una copia necesita" : rev + " copias necesitan"} revisión` : `Listo · ${hechos.length === 1 ? "documento seudonimizado" : hechos.length + " documentos seudonimizados"}`) : "No se ha podido generar ninguna copia"}</h4>
    ${hechos.map((x) => filaResultado({ id: x.id, original: x.original, ruta: x.copia, estado: x.estado })).join("")}
    ${fallos.length ? `<ul class="doc-motivos">${fallos.map((x) => `<li>${esc(x.original)}: ${esc(ESTADOS[x.estado] || x.estado)}${x.motivos && x.motivos.length ? " — " + esc(x.motivos[0]) : ""}</li>`).join("")}</ul>` : ""}
    ${bloqueCarpetas(res.carpeta ? [res.carpeta] : [], res.certificado)}
    ${res.aviso ? `<p class="aviso-campo">${esc(res.aviso)}</p>` : ""}
    ${hechos.length > 1 ? `<div class="plan-acciones"><button class="boton" data-guardar-en="${esc(hechos.map((x) => x.copia).join("\n"))}">Guardar todas en…</button></div>` : ""}`;
  return d;
}

function nodoUbicacion(plan) {
  const d = document.createElement("div");
  d.className = "plan tarjeta-listo";
  d.innerHTML = `<h4>Dónde ${plan.documentos.length === 1 ? "está" : "están"}</h4>
    ${plan.documentos.map((x) => filaResultado({ id: x.id, original: x.original, nombre: x.nombre, ruta: x.copia, estado: x.estado })).join("")}
    ${bloqueCarpetas(plan.carpetas || [], plan.certificado)}`;
  return d;
}

function nodoGuardar(plan, mid, datos) {
  const d = document.createElement("div");
  d.className = "plan";
  const n = plan.documentos.length;
  const titulo = `Guardar ${n === 1 ? "una copia" : n + " copias"} en ${plan.destino}`;
  if (plan.estado) {
    d.classList.add("cerrado");
    d.innerHTML = `<h4>${esc(titulo)}</h4><p class="resultado">${plan.estado === "confirmado" ? "Hecho: guardadas en esa carpeta. Las copias del expediente siguen también donde estaban." : "Descartado."}</p>
      ${plan.estado === "confirmado" ? `<div class="plan-acciones"><button class="boton-texto" data-abrir="${esc(plan.destino)}">Abrir la carpeta</button></div>` : ""}`;
    return d;
  }
  d.innerHTML = `<h4>${esc(titulo)}</h4>
    <ul class="plan-archivos">${plan.documentos.map((x) => `<li>${esc(x.nombre)}</li>`).join("")}</ul>
    <p class="nota">Se guarda la copia seudonimizada; si ya hay un archivo con ese nombre, no se sobrescribe.</p>
    <div class="plan-acciones"><button class="boton boton-principal" data-confirmar>Guardar</button><button class="boton" data-descartar>Descartar</button></div>`;
  $("[data-confirmar]", d).onclick = async () => {
    try {
      await api("POST", "/api/guardar_en", { rutas: plan.documentos.map((x) => x.copia), destino: plan.destino });
      plan.estado = "confirmado";
      await guardarPlanes(mid, datos);
      d.replaceWith(nodoGuardar(plan, mid, datos));
    } catch (e) { alerta(e.message); }
  };
  $("[data-descartar]", d).onclick = async () => { plan.estado = "descartado"; await guardarPlanes(mid, datos); d.replaceWith(nodoGuardar(plan, mid, datos)); };
  return d;
}

async function guardarEn(rutas) {
  const r = await elegir("carpeta_salida");
  if (!r[0]) return;
  const res = await api("POST", "/api/guardar_en", { rutas, destino: r[0] });
  avisoFlotante(`${res.copiados.length === 1 ? "Guardado" : res.copiados.length + " archivos guardados"} en ${res.carpeta}`);
}

// ------------------------------------------------------------------ riesgo por contexto (opcional)

const NIVELES = { bajo: "Riesgo bajo", medio: "Riesgo medio", alto: "Riesgo alto" };
const NIVEL_FRASE = {
  bajo: "Con lo que queda a la vista, difícilmente alguien reconocería a la persona.",
  medio: "Con lo que queda a la vista, alguien de su entorno podría llegar a reconocerla.",
  alto: "Con lo que queda a la vista, alguien de su entorno (compañeros, la empresa, vecinos) reconocería a la persona aunque no aparezca su nombre.",
};

async function riesgoContexto(aid) {
  const d = $("#dlg-contexto");
  const cuerpo = $("#contexto-cuerpo");
  const boton = $("#contexto-aplicar");
  boton.disabled = true;
  boton.textContent = "Aplicar";
  $("#contexto-nota").textContent = "";
  cuerpo.innerHTML = `<p class="cargando">Leyendo la copia con el modelo local… En un documento largo puede tardar un par de minutos.</p>`;
  if (!d.open) d.showModal();
  let r;
  try { r = await api("POST", `/api/proyectos/${E.proyecto.id}/contexto/${aid}/analizar`); }
  catch (e) { cuerpo.innerHTML = `<p class="aviso-campo">${esc(e.message)}</p>`; return; }
  const fila = (h, i) => `<div class="riesgo-fila${h.aplicada ? " aplicada" : ""}">
      <label class="interruptor-grande"><input type="checkbox" data-i="${i}"${h.aplicada || h.recomendado ? " checked" : ""}><span class="pista-int"></span></label>
      <div class="riesgo-texto">
        <div>${h.aplicada ? "Ya cambiado" : "Se ve"} <b class="riesgo-de">«${esc(h.texto)}»</b>${h.veces > 1 ? ` <span class="nota">(${h.veces} veces)</span>` : ""} <span class="nota">· ${esc(h.nombre_categoria.toLowerCase())}</span></div>
        <div class="riesgo-a">${h.aplicada ? "ahora pone" : "se cambiaría por"} <button type="button" class="riesgo-prop" data-e="${i}" title="Pulsa para escribir otra cosa">«<span data-txt="${i}">${esc(h.generalizado)}</span>»</button><input class="contexto-a" data-r="${i}" value="${esc(h.generalizado)}" hidden aria-label="Cómo queda"></div>
      </div></div>`;
  const huerfanas = (r.aplicadas || []).filter((g) => !r.hallazgos.some((h) => h.aplicada && (h.original || h.texto).toLowerCase() === g.texto.toLowerCase()));
  cuerpo.innerHTML = `<div class="contexto-nivel ${esc(r.nivel)}"><span class="semaforo" aria-hidden="true"></span><div><b>${NIVELES[r.nivel]}</b><p>${esc(NIVEL_FRASE[r.nivel] || r.explicacion)}</p></div></div>
    ${r.hallazgos.length ? `<p class="nota">Deja activado lo que quieras cambiar. Vienen activados los datos que delatan a la persona sin aportar nada al asunto; las fechas, los importes, el puesto y la salud los decides tú, porque pueden ser necesarios para el caso.</p>
      <div class="riesgo-lista">${r.hallazgos.map(fila).join("")}</div>` : `<p class="nota">No queda ningún dato indirecto que cambiar.</p>`}
    ${huerfanas.length ? `<h3>Cambiados antes en este expediente</h3><div class="riesgo-lista">${huerfanas.map((g) => `<div class="riesgo-fila aplicada"><label class="interruptor-grande"><input type="checkbox" data-ya="${esc(g.texto)}" checked><span class="pista-int"></span></label><div class="riesgo-texto"><div>«${esc(g.texto)}» → «${esc(g.reemplazo)}»</div></div></div>`).join("")}</div><p class="nota">Desactiva uno para volver a dejarlo como estaba.</p>` : ""}`;
  $$(".riesgo-prop", cuerpo).forEach((b) => (b.onclick = () => {
    const inp = $(`input[data-r="${b.dataset.e}"]`, cuerpo);
    b.hidden = true; inp.hidden = false; inp.focus(); inp.select();
    inp.onblur = () => { $(`[data-txt="${b.dataset.e}"]`, cuerpo).textContent = inp.value; inp.hidden = true; b.hidden = false; contar(); };
    inp.onkeydown = (ev) => { if (ev.key === "Enter") { ev.preventDefault(); inp.blur(); } };
  }));
  const contar = () => {
    const poner = r.hallazgos.filter((h, i) => !h.aplicada && $(`input[data-i="${i}"]`, cuerpo).checked).length;
    const quitar = r.hallazgos.filter((h, i) => h.aplicada && !$(`input[data-i="${i}"]`, cuerpo).checked).length + $$("input[data-ya]", cuerpo).filter((x) => !x.checked).length;
    const cambios = r.hallazgos.filter((h, i) => h.aplicada && $(`input[data-i="${i}"]`, cuerpo).checked && $(`input[data-r="${i}"]`, cuerpo).value !== h.generalizado).length;
    const total = poner + quitar + cambios;
    boton.disabled = !total;
    boton.textContent = total ? `Aplicar ${total === 1 ? "el cambio" : total + " cambios"}` : "Aplicar";
    $("#contexto-nota").textContent = total ? "La copia se actualiza al momento." : "";
  };
  cuerpo.oninput = contar;
  contar();
  boton.onclick = async () => {
    const poner = r.hallazgos.map((h, i) => ({ h, i })).filter(({ i }) => $(`input[data-i="${i}"]`, cuerpo).checked)
      .map(({ h, i }) => ({ texto: h.original || h.texto, reemplazo: $(`input[data-r="${i}"]`, cuerpo).value.trim(), categoria: h.categoria }))
      .filter((x) => x.reemplazo);
    const quitar = r.hallazgos.filter((h, i) => h.aplicada && !$(`input[data-i="${i}"]`, cuerpo).checked).map((h) => h.original || h.texto)
      .concat($$("input[data-ya]", cuerpo).filter((x) => !x.checked).map((x) => x.dataset.ya));
    try {
      const res = await api("POST", `/api/proyectos/${E.proyecto.id}/contexto/aplicar`, { archivo: aid, poner, quitar, conversacion: E.conversacion });
      d.close();
      if (!$("#mesa").hidden && MESA.actual?.id === aid) seguirTrabajoMesa(res.id, "Actualizando la copia…", { texto: "Copia actualizada con los cambios." });
      else { avisoFlotante("Actualizando la copia con los cambios…"); await refrescarOperaciones(); }
    } catch (e) { alerta(e.message); }
  };
}

function nodoTapar(plan, mid, datos) {
  // Plan «tapar»: datos que el usuario ha visto a la vista en una copia y quiere tapados
  const d = document.createElement("div");
  d.className = "plan";
  const n = plan.datos.length;
  const titulo = `Tapar ${n === 1 ? "un dato" : n + " datos"} en ${plan.nombres[0]}`;
  if (plan.estado) {
    d.classList.add("cerrado");
    d.innerHTML = `<h4>${esc(titulo)}</h4><p class="resultado">${plan.estado === "confirmado"
      ? "En marcha: la copia se está rehaciendo con esos datos tapados. El avance se ve en la lista de documentos." : "Descartado."}</p>`;
    return d;
  }
  d.innerHTML = `<h4>${esc(titulo)}</h4>
    <ul class="plan-archivos">${plan.datos.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <p class="nota">Se tapan en todo el documento${plan.pagina ? ` (también fuera de la página ${plan.pagina})` : ""}, dentro de las imágenes incluidas. El original no se toca.</p>
    <div class="plan-acciones">
      <button class="boton boton-principal" data-confirmar>Tapar</button>
      <button class="boton" data-descartar>Descartar</button>
    </div>`;
  $("[data-confirmar]", d).onclick = async () => {
    try {
      const r = await api("POST", `/api/proyectos/${E.proyecto.id}/tapar`, { archivo: plan.archivos[0], datos: plan.datos, tipo: plan.tipo, perfil: plan.perfil, conversacion: E.conversacion });
      plan.estado = "confirmado"; plan.trabajo = r.id;
      await guardarPlanes(mid, datos);
      d.replaceWith(nodoTapar(plan, mid, datos));
      E.trabajos[r.id] = r.estado;
      mostrarPestana("operaciones");
      await refrescarOperaciones();
    } catch (e) { alerta(e.message); }
  };
  $("[data-descartar]", d).onclick = async () => {
    plan.estado = "descartado";
    await guardarPlanes(mid, datos);
    d.replaceWith(nodoTapar(plan, mid, datos));
  };
  return d;
}

function nodoPlan(plan, mid, datos) {
  if (plan.accion === "tapar") return nodoTapar(plan, mid, datos);
  if (plan.accion === "ubicacion") return nodoUbicacion(plan);
  if (plan.accion === "guardar") return nodoGuardar(plan, mid, datos);
  const d = document.createElement("div");
  d.className = "plan";
  const n = plan.archivos.length;
  const estado = plan.estado;   // confirmado | descartado | undefined
  const pags = plan.paginas && plan.paginas.length ? plan.paginas : null;
  const uni = plan.unidad || "página", unis = plan.unidades || "páginas";
  const textoPags = pags ? (pags.length === 1 ? `la ${uni} ${pags[0]}` : `las ${unis} ${pags.join(", ")}`) : "";
  const titulo = pags ? `${plan.solo_paginas ? "Seudonimizar solo" : "Repasar"} ${textoPags} de ${plan.nombres[0]}`
    : `Seudonimizar ${n} archivo${n === 1 ? "" : "s"}`;
  if (estado) {
    d.classList.add("cerrado");
    d.innerHTML = `<h4>${esc(pags ? titulo : `Seudonimización de ${n} archivo${n === 1 ? "" : "s"}`)}</h4>
      <p class="resultado">${estado === "confirmado" ? `En marcha${plan.perfil === "intensivo" ? " (revisión a fondo)" : ""}. El avance se ve en la lista de documentos; allí puedes cancelarlo. Los originales no se tocan.` : estado === "otro_proyecto" ? "Esto era del expediente de origen de la conversación. Si lo necesitas aquí, vuelve a pedirlo." : "Descartada."}</p>`;
    return d;
  }
  const intensivo = plan.perfil === "intensivo";
  d.innerHTML = `<h4>${esc(titulo)}</h4>
    ${pags ? `<fieldset class="plan-perfil plan-alcance">
        <label class="opcion"><input type="radio" name="alcance-${mid}" value="solo"${plan.solo_paginas ? " checked" : ""}> <span><b>Solo ${esc(textoPags)}.</b> La copia tendrá únicamente ${pags.length === 1 ? "esa " + uni : "esas " + unis}, seudonimizada${pags.length === 1 ? "" : "s"} y verificada${pags.length === 1 ? "" : "s"}.</span></label>
        <label class="opcion"><input type="radio" name="alcance-${mid}" value="completo"${plan.solo_paginas ? "" : " checked"}> <span><b>Documento completo.</b> Repasa ${esc(textoPags)} dentro del documento ya seudonimizado; la copia sale con todas las ${unis}.</span></label>
      </fieldset>`
      : `<ul class="plan-archivos">${plan.nombres.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`}
    <div class="plan-opciones">
      <label class="opcion"><input type="radio" name="perfil-${mid}" value="estandar"${intensivo ? "" : " checked"}> <span>Revisión normal</span></label>
      <label class="opcion"><input type="radio" name="perfil-${mid}" value="intensivo"${intensivo ? " checked" : ""}> <span>Revisión a fondo (más lenta)</span></label>
    </div>
    <p class="nota">Las copias se guardan ${E.proyecto?.guardar_efectivo === "carpeta" ? "en la carpeta elegida para este expediente" : "junto a los originales, en una carpeta «Seudonimizados»"}. Los originales no se tocan.</p>
    <div class="plan-acciones">
      <button class="boton boton-principal" data-confirmar>${pags ? "Confirmar" : `Seudonimizar ${n} archivo${n === 1 ? "" : "s"}`}</button>
      <button class="boton" data-descartar>Descartar</button>
    </div>`;
  $("[data-confirmar]", d).onclick = async () => {
    const perfil = $(`input[name="perfil-${mid}"]:checked`, d).value;
    try {
      const solo = pags ? ($(`input[name="alcance-${mid}"]:checked`, d) || {}).value === "solo" : false;
      const r = await api("POST", `/api/proyectos/${E.proyecto.id}/trabajos`, { archivos: plan.archivos, perfil, conversacion: E.conversacion, ...(pags ? { paginas: pags, solo_paginas: solo } : {}) });
      plan.estado = "confirmado"; plan.perfil = perfil; plan.trabajo = r.id; if (pags) plan.solo_paginas = solo;
      await guardarPlanes(mid, datos);
      d.replaceWith(nodoPlan(plan, mid, datos));
      E.trabajos[r.id] = r.estado;
      mostrarPestana("operaciones");
      await refrescarOperaciones();
    } catch (e) { alerta(e.message); }
  };
  $("[data-descartar]", d).onclick = async () => {
    plan.estado = "descartado";
    await guardarPlanes(mid, datos);
    d.replaceWith(nodoPlan(plan, mid, datos));
  };
  return d;
}

async function guardarPlanes(mid, datos) {
  if (mid) { try { await api("PATCH", `/api/mensajes/${mid}`, { datos }); } catch (e) { /* no crítico */ } }
}

async function enviar(texto) {
  texto = (texto || "").trim();
  if (!texto || E.enviando) return;
  if (!E.conversacion) {
    const c = await api("POST", `/api/proyectos/${E.proyecto.id}/conversaciones`);
    E.conversacion = c.id;
  }
  if (fondo() && /seudonim|anonim/i.test(texto) && !/intensiv|a fondo/i.test(texto)) texto += " (con verificación intensiva)";
  E.enviando = true;
  $("#enviar").disabled = true;
  const hilo = $("#hilo");
  if (hilo.querySelector(".vacio")) hilo.innerHTML = "";
  hilo.append(nodoUsuario(texto));
  const nodo = document.createElement("div");
  nodo.className = "msg msg-asistente";
  nodo.innerHTML = `<div class="herramientas"></div><div class="prosa cursor"></div>`;
  hilo.append(nodo);
  hilo.scrollTop = hilo.scrollHeight;
  let acumulado = "";
  const planes = [];
  try {
    const r = await fetch(E.conexion.base + `/api/conversaciones/${E.conversacion}/mensajes`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-Seudonimo-Token": E.conexion.token },
      body: JSON.stringify({ texto, modelo: modeloActual() }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `Error ${r.status}`);
    const lector = r.body.getReader();
    const dec = new TextDecoder();
    let resto = "";
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      resto += dec.decode(value, { stream: true });
      let i;
      while ((i = resto.indexOf("\n")) >= 0) {
        const linea = resto.slice(0, i); resto = resto.slice(i + 1);
        if (!linea.trim()) continue;
        const ev = JSON.parse(linea);
        if (ev.t === "texto") { acumulado += ev.v; $(".prosa", nodo).innerHTML = markdown(acumulado); }
        else if (ev.t === "herramienta") pintarHerramienta(nodo, ev);
        else if (ev.t === "plan") planes.push(ev);
        else if (ev.t === "fin") {
          $(".prosa", nodo).classList.remove("cursor");
          const datos = { herramientas: [], planes };
          for (const p of planes) {
            const tarjeta = nodoPlan(p, ev.mensaje, datos);
            nodo.append(tarjeta);
            // lo que pide el usuario se hace sin pedir confirmación: nada toca los originales y todo se puede cancelar o deshacer
            const b = $("[data-confirmar]", tarjeta);
            if (b) b.click();
          }
        }
        hilo.scrollTop = hilo.scrollHeight;
      }
    }
  } catch (e) {
    $(".prosa", nodo).innerHTML = markdown(acumulado + `\n\n*${e.message}*`);
  } finally {
    $(".prosa", nodo).classList.remove("cursor");
    E.enviando = false;
    $("#enviar").disabled = false;
    E.conversaciones[E.proyecto.id] = await api("GET", `/api/proyectos/${E.proyecto.id}/conversaciones`);
    const c = (E.conversaciones[E.proyecto.id] || []).find((x) => x.id === E.conversacion);
    if (c) $("#titulo-conversacion").textContent = c.titulo;
    pintarLateral();
  }
}

function pintarHerramienta(nodo, ev) {
  const cont = $(".herramientas", nodo);
  let el = $$(".herramienta", cont).find((x) => x.dataset.nombre === ev.nombre && x.classList.contains("trabajando"));
  if (!el) { el = document.createElement("div"); el.className = "herramienta"; el.dataset.nombre = ev.nombre; cont.append(el); }
  el.className = "herramienta" + (ev.estado === "inicio" ? " trabajando" : ev.estado === "error" ? " error" : "");
  el.textContent = nombreHerramienta(ev.nombre) + (ev.estado === "inicio" ? "…" : ev.resumen ? ": " + ev.resumen : "");
}

// Markdown mínimo y seguro (todo se escapa antes de dar formato)
function markdown(md) {
  const lineas = esc(md).split("\n");
  let html = "", lista = null, parrafo = [];
  const cerrarP = () => { if (parrafo.length) { html += `<p>${inline(parrafo.join("<br>"))}</p>`; parrafo = []; } };
  const cerrarL = () => { if (lista) { html += `</${lista}>`; lista = null; } };
  for (const l of lineas) {
    let m;
    if ((m = l.match(/^\s*[-*•]\s+(.*)/))) { cerrarP(); if (lista !== "ul") { cerrarL(); html += "<ul>"; lista = "ul"; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { cerrarP(); if (lista !== "ol") { cerrarL(); html += "<ol>"; lista = "ol"; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = l.match(/^#{1,4}\s+(.*)/))) { cerrarP(); cerrarL(); html += `<h4>${inline(m[1])}</h4>`; }
    else if ((m = l.match(/^&gt;\s?(.*)/))) { cerrarP(); cerrarL(); html += `<blockquote>${inline(m[1])}</blockquote>`; }
    else if (!l.trim()) { cerrarP(); cerrarL(); }
    else { cerrarL(); parrafo.push(l); }
  }
  cerrarP(); cerrarL();
  return html;
}
function inline(s) {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
    .replace(/\[([A-Z_]+_\d{1,4}|LOGO O SELLO)\]/g, '<span class="tachon">[$1]</span>');
}

// ------------------------------------------------------------------ panel: archivos

function pintarArchivos() {
  // Una sola lista: cada documento con su estado y, si ya está hecho, «Abrir copia» y «⋯»
  const p = E.proyecto;
  if (!p) return;
  const el = $("#panel-archivos");
  const adm = p.archivos.filter((a) => a.admitido);
  const fuera = p.archivos.filter((a) => !a.admitido);
  const R = E.resultados || { copias: [], carpetas: [], certificados: [] };
  const copia = Object.fromEntries((R.copias || []).map((c) => [c.id, c]));
  const vivos = Object.values(E.trabajos).filter(Boolean).filter((t) => (E.historial || []).some((h) => h.id === t.id));
  const activos = vivos.filter((t) => ["pendiente", "procesando"].includes(t.estado));
  const pend = pendientes();
  let html = "";
  html += activos.sort((a, b) => b.id.localeCompare(a.id)).map((t) => `<div class="trabajo en-curso">
      <div class="trabajo-cab"><b><i class="punto-vivo"></i> Seudonimizando ${t.docs.length === 1 ? "un documento" : t.docs.length + " documentos"} · ${Math.round(t.progreso * 100)} %</b><button class="boton-texto peligro" data-cancelar="${t.id}">Cancelar</button></div>
      <div class="progreso"><i style="width:${Math.round(t.progreso * 100)}%"></i></div><div class="trabajo-msg">${esc(t.mensaje)}</div></div>`).join("");
  if (pend.length && !activos.length) html += `<button class="boton boton-principal boton-grande ancho" data-accion="seudonimizar-pendientes">Seudonimizar ${pend.length === 1 ? "el documento pendiente" : "los " + pend.length + " documentos pendientes"}</button>`;
  html += `<div class="docs-cab"><h3>Documentos${adm.length ? ` · ${adm.length}` : ""}</h3><button class="boton boton-chico" data-accion="menu-anadir" aria-haspopup="menu">+ Añadir</button></div>`;
  if (!adm.length) {
    html += `<div class="zona-soltar grande"><b>Arrastra aquí documentos o una carpeta</b><span>PDF, Word, Excel, PowerPoint, correos, imágenes… Los originales no se tocan.</span>
      <div class="plan-acciones centrado"><button class="boton boton-principal" data-accion="adjuntar-carpeta">Añadir una carpeta</button><button class="boton" data-accion="adjuntar-archivos">Añadir archivos</button></div></div>`;
  }
  const orden = { revision: 0, procesando: 1, en_cola: 2, error: 3, interrumpido: 3, nuevo: 4, cancelado: 4, parcial: 5, sin_hallazgos: 6 };
  html += adm.slice().sort((a, b) => (orden[a.estado] ?? 9) - (orden[b.estado] ?? 9) || a.rel.localeCompare(b.rel)).map((a) => {
    const c = copia[a.id];
    const estado = a.estado === "nuevo" ? "Pendiente" : a.estado === "revision" ? "Revísala antes de usarla" : a.estado === "parcial" ? "Copia de algunas páginas" : ESTADOS[a.estado] || a.estado;
    return `<div class="resultado-doc">
      <span class="punto ${esc(a.estado)}" aria-hidden="true"></span>
      <div class="resultado-info"><b title="${esc(a.rel)}">${esc(a.rel.split(/[\\/]/).pop())}</b><span class="nota">${esc(estado)}${a.motivo && !c ? " · " + esc(a.motivo) : ""}</span></div>
      ${c ? `<div class="botones-fila">
        <button class="boton boton-chico" data-abrir="${esc(c.ruta)}">Abrir copia</button>
        <button class="boton boton-chico${a.estado === "revision" ? " aviso" : ""}" data-revisar="${a.id}" title="Ver la copia y tapar a mano lo que falte">Revisar</button>
        <button class="boton boton-chico" data-contexto="${a.id}" title="¿Se podría reconocer a la persona por la suma de datos indirectos?">Comprobar riesgo</button>
        <button class="boton-texto mas-doc" data-menu-copia="${esc(c.ruta)}" data-doc="${a.id}" data-nombre="${esc(a.rel.split(/[\\/]/).pop())}" aria-label="Más opciones" title="Más opciones">⋯</button></div>` : ""}
    </div>`;
  }).join("");
  if (fuera.length) html += `<details class="plegable"><summary>${fuera.length === 1 ? "Un archivo no se puede tratar" : fuera.length + " archivos no se pueden tratar"}</summary>
    ${fuera.map((a) => `<div class="archivo"><span class="nombre">${esc(a.rel)}</span><span class="chip no_admitido">No admitido</span>${a.motivo ? `<span class="motivo">${esc(a.motivo)}</span>` : ""}</div>`).join("")}</details>`;
  // dónde están las copias
  if ((R.copias || []).length) {
    const donde = p.guardar_efectivo === "carpeta" ? "en la carpeta que elegiste" : "junto a los originales, en «Seudonimizados»";
    html += `<div class="pie-docs"><p class="nota">Las copias se guardan ${donde}.</p>
      <div class="plan-acciones">${(R.carpetas || []).slice(0, 3).map((c) => `<button class="boton-texto" data-abrir="${esc(c)}" title="${esc(c)}">Abrir ${R.carpetas.length > 1 ? "«" + esc(c.split(/[\\/]/).slice(-2, -1)[0] || c) + "»" : "la carpeta"}</button>`).join("")}
        ${R.copias.length > 1 ? `<button class="boton-texto" data-guardar-en="${esc(R.copias.map((c) => c.ruta).join("\n"))}">Guardar todas en…</button>` : ""}
        ${(R.certificados || []).length ? `<button class="boton-texto" data-abrir="${esc(R.certificados[0].ruta)}" title="Certificado de la última seudonimización">Certificado</button>` : ""}</div></div>`;
  }
  if (p.vigilar) html += `<p class="nota vigilada">Carpeta vigilada: lo que llegue a las carpetas del expediente se seudonimiza solo.</p>`;
  if (p.carpetas.length) html += `<details class="plegable"><summary>Carpetas y archivos del expediente</summary>
    ${p.carpetas.map((c) => `<div class="carpeta"><span>${esc(c.ruta)}</span><button class="boton-texto" data-quitar-carpeta="${c.id}" title="Quitar del expediente (no borra nada del disco)">Quitar</button></div>`).join("")}
    <button class="boton-texto" data-accion="actualizar-carpetas" title="Volver a leer las carpetas">Volver a leer las carpetas</button></details>`;
  html += detalleTecnico(activos);
  el.innerHTML = html;
  pintarGuia(el, { adm: adm.length, pend: pend.length, activos: activos.length, hechos: (R.copias || []).length });
}

// Tres globos la primera vez: qué hacer ahora. Desaparecen al pulsar «Entendido» en el último.
function guiaVista() { try { return !!localStorage.getItem("seudonimo.guia"); } catch (e) { return true; } }
function pintarGuia(el, n) {
  if (guiaVista() || !E.proyecto) return;
  const paso = !n.adm ? 1 : (n.pend || n.activos) && !n.hechos ? 2 : n.hechos ? 3 : 0;
  if (!paso) return;
  const textos = {
    1: ["Paso 1 de 3", "Arrastra aquí los documentos del asunto, o pulsa «+ Añadir». Los originales nunca se tocan."],
    2: ["Paso 2 de 3", n.activos ? "Ya está trabajando. Al terminar, cada documento tendrá su copia sin datos." : "Pulsa «Seudonimizar». Tarda un rato y puedes seguir usando el ordenador."],
    3: ["Paso 3 de 3", "«Abrir copia» abre el documento sin datos. Si ves algo sin tapar, pulsa «Revisar», haz doble clic encima y «Tapar». Y en el chat puedes pedir lo que quieras con tus palabras."],
  }[paso];
  el.insertAdjacentHTML("afterbegin", `<div class="globo"><b>${textos[0]}</b><p>${textos[1]}</p>${paso === 3 ? `<button class="boton boton-chico" data-accion="guia-vista">Entendido</button>` : `<button class="boton-texto boton-chico" data-accion="guia-vista">No mostrar más</button>`}</div>`);
}

async function expedienteDesde(rutas) {
  // Sin expediente abierto: se propone uno con el nombre de la carpeta (o del primer archivo)
  if (!rutas.length) return;
  const nombre = rutas[0].replace(/[\\/]+$/, "").split(/[\\/]/).pop().replace(/\.[^.]+$/, "");
  E.rutasPendientes = rutas;
  abrirDialogoProyecto(false);
  $("#form-proyecto").nombre.value = nombre;
  $("#form-proyecto").nombre.select();
}

async function anadirRutas(rutas) {
  if (!rutas.length) return;
  try {
    await api("POST", `/api/proyectos/${E.proyecto.id}/carpetas`, { rutas });
    E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`);
    pintarArchivos();
    if ($("#hilo .vacio")) pintarVacioProyecto();
  } catch (e) { alerta(e.message); }
}

// ------------------------------------------------------------------ panel: operaciones

async function refrescarOperaciones() {
  if (!E.proyecto) return;
  const r = await api("GET", `/api/proyectos/${E.proyecto.id}/trabajos`);
  try { E.resultados = await api("GET", `/api/proyectos/${E.proyecto.id}/resultados`); } catch (e) { E.resultados = null; }
  E.historial = r.historial;
  for (const t of r.activos) E.trabajos[t.id] = t;
  // los trabajos vivos de este proyecto, con su detalle
  const vivos = r.historial.filter((h) => ["en_cola", "procesando", "pendiente"].includes(h.estado) || E.trabajos[h.id]);
  for (const h of vivos) {
    try { E.trabajos[h.id] = await api("GET", `/api/trabajos/${h.id}`); } catch (e) { /* de una sesión anterior */ }
  }
  const hayActivos = Object.values(E.trabajos).some((t) => t && ["pendiente", "procesando"].includes(t.estado));
  if (hayActivos) { try { E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`); } catch (e) { /* sigue */ } }
  pintarArchivos();
  clearTimeout(E.sondeo);
  if (hayActivos) E.sondeo = setTimeout(async () => {
    const antes = Object.values(E.trabajos).filter((t) => t && ["pendiente", "procesando"].includes(t.estado)).length;
    await refrescarOperaciones();
    const despues = Object.values(E.trabajos).filter((t) => t && ["pendiente", "procesando"].includes(t.estado)).length;
    if (despues < antes) {            // algún trabajo ha terminado
      E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`);
      pintarArchivos();
      // la tarjeta «Listo» llega como mensaje a la conversación desde la que se pidió
      if (E.conversacion && !E.enviando) await abrirConversacion(E.conversacion);
      avisoFlotante("Seudonimización terminada: «Abrir copia» en la lista de documentos.");
    }
  }, 2000);
}

function certificadoDe(tid) {
  return ((E.historial || []).find((h) => h.id === tid) || {}).certificado || null;
}

function pistaDoc(d) {
  return (d.pasadas || []).map((p) => {
    if (p.tipo === "deteccion") return `<span class="paso${p.nuevos ? " nuevos" : ""}" title="Detección ${p.n}: ${p.nuevos} dato(s) nuevo(s)">D${p.n}</span>`;
    const cls = p.restos || p.incidencias_graves ? "restos" : p.nuevos || p.caras ? "nuevos" : "limpio";
    return `<span class="paso ${cls}" title="Verificación ${p.ciclo} (método ${p.metodo}): ${p.nuevos} nuevo(s), ${p.restos} resto(s), ${p.incidencias_graves} incidencia(s) grave(s)${p.caras ? `, ${p.caras} cara(s) aún visible(s), se tapan en el ciclo siguiente` : ""}">V${p.ciclo}</span>`;
  }).join("");
}

function detalleTecnico(activos) {
  const terminados = (E.historial || []).filter((h) => !activos.some((v) => v.id === h.id));
  if (!terminados.length) return "";
  return `<details class="tecnico plegable"><summary>Detalle técnico de cada seudonimización</summary>` + terminados.map((h) => {
    const t = E.trabajos[h.id];
    return `<div class="trabajo">
      <div class="trabajo-cab"><b>${esc(new Date((h.terminado || h.creado) * 1000).toLocaleString("es-ES"))} · revisión ${h.perfil === "intensivo" ? "a fondo" : "normal"}</b>${h.certificado ? `<button class="boton-texto" data-abrir="${esc(h.certificado)}">Certificado</button>` : ""}</div>
      ${h.resumen ? `<p class="nota">${h.resumen.recuento.sin_hallazgos} listos · ${h.resumen.recuento.revision} para revisar · ${h.resumen.recuento.error} con error</p>` : `<p class="nota">${esc(ESTADOS[h.estado] || h.estado)}</p>`}
      ${t && t.docs ? t.docs.map((d) => `<div class="doc"><div class="doc-cab"><span>${esc(d.rel)}${d.paginas && d.paginas.length ? ` <span class="nota">· ${d.solo_paginas ? "solo" : "repaso de"} ${d.paginas.join(", ")}</span>` : ""}</span><span class="chip ${esc(d.estado)}">${esc(ESTADOS[d.estado] || d.estado)}</span></div>
        <div class="pista">${pistaDoc(d)}</div>${d.motivos && d.motivos.length ? `<ul class="doc-motivos">${d.motivos.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}</div>`).join("") : ""}
    </div>`;
  }).join("") + `<p class="leyenda">D = lectura del documento · V = comprobación de la copia. Dorado: encontró datos nuevos; verde: limpia; ámbar: quedan restos.</p></details>`;
}

function menuCopia(boton) {
  const d = boton.dataset;
  const aid = +d.doc || null;
  abrirMenu(boton, [
    { texto: `Mostrar en ${EXPLORADOR}`, accion: () => api("POST", "/api/mostrar", { ruta: d.menuCopia }) },
    { texto: "Guardar en…", accion: () => guardarEn([d.menuCopia]) },
    ...(aid ? [
      { texto: "Pedirle algo al asistente sobre este documento…", accion: () => rellenar(`En «${d.nombre}», `) },
    ] : []),
  ]);
}

function menuExpediente(boton) {
  const p = E.proyecto;
  const hayCopias = (E.resultados?.copias || []).length > 0;
  abrirMenu(boton, [
    { texto: "Ajustes del expediente", accion: () => abrirDialogoProyecto(true) },
    ...(hayCopias ? [{ texto: "Revisar las copias", accion: () => abrirMesa() }] : []),
    ...(hayCopias ? [{ texto: "Copiar las copias para otra IA", accion: copiarParaIA }] : []),
    { texto: "Volver a poner los nombres en una respuesta de otra IA…", accion: abrirNombres },
    ...(p.tabla === "cifrada" ? [{ texto: "Exportar la lista de nombres y etiquetas…", accion: () => accion("exportar-tabla") }] : []),
    { texto: "Empezar una conversación nueva", accion: nuevaConversacion },
    ...((E.conversaciones[p.id] || []).length > 1 ? [{ texto: "Conversaciones anteriores…", accion: () => menuConversaciones(boton) }] : []),
  ]);
}

function menuConversaciones(boton) {
  const convs = (E.conversaciones[E.proyecto.id] || []).slice(0, 12);
  abrirMenu(boton, convs.map((c) => ({
    texto: `${c.id === E.conversacion ? "● " : ""}${c.titulo}`,
    accion: () => abrirConversacion(c.id),
  })).concat([{ texto: "Gestionar la conversación actual…", accion: () => menuConversacion(boton, E.conversacion) }]));
}

function menuAjustes(boton) {
  abrirMenu(boton, [
    { texto: "Modelos y dictado", accion: abrirModelos },
    { texto: "Listas del despacho (nunca / siempre tapar)", accion: abrirListas },
    ...(E.proyecto ? [{ texto: "Ajustes de este expediente", accion: () => abrirDialogoProyecto(true) }] : []),
    { texto: "Buscar actualizaciones", accion: acercaDe },
  ]);
}

function rellenar(texto) {
  const e = $("#entrada");
  if ($("#redactor").hidden) return;
  e.value = texto;
  e.dispatchEvent(new Event("input"));
  e.focus();
  e.setSelectionRange(e.value.length, e.value.length);
}

// ------------------------------------------------------------------ lista de datos tapados (dentro de la revisión)

function pintarRevision(el = $("#mesa-datos")) {
  const r = MESA.registro;
  if (!E.proyecto || !r) return;
  const grupos = {};
  for (const e of r.entidades) (grupos[e.tipo] = grupos[e.tipo] || []).push(e);
  const tipos = Object.keys(r.etiquetas);
  el.innerHTML = `<div class="mesa-datos-cab"><h3>Datos tapados</h3><button type="button" class="boton-texto" id="mesa-datos-cerrar" aria-label="Ocultar">✕</button></div>
    <p class="nota">Todo lo que se tapa en este expediente. Lo que apuntes aquí se tapa en esta copia ahora y en las demás cuando se actualicen.</p>
    <form class="form-anadir">
      <input name="texto" placeholder="Dato que se ha escapado" required>
      <button class="boton">Tapar</button>
      <select name="tipo" aria-label="Qué es">${tipos.map((t) => `<option value="${t}"${t === "PERSONA" ? " selected" : ""}>${esc(r.etiquetas[t])}</option>`).join("")}</select>
    </form>
    <input class="filtro-datos" type="search" placeholder="Buscar un dato o una etiqueta">
    ${r.entidades.length ? "" : `<p class="nota">Todavía no hay datos detectados en este expediente.</p>`}
    <div class="grupos-datos">${Object.entries(grupos).map(([tipo, ents]) => `<div class="grupo-tipo"><h3>${esc(r.etiquetas[tipo] || tipo)} · ${ents.filter((e) => e.activo).length}</h3>
      ${ents.map((e) => {
        const visible = !e.activo || e.conservado || e.en_lista;
        return `<div class="entidad${visible ? " inactiva" : ""}" data-buscar="${esc((e.marcador + " " + etiquetaMarca(e.marcador) + " " + e.formas.join(" ")).toLowerCase())}">
        <span class="tachon${visible ? " descartado" : ""}" title="En el archivo: ${esc(e.marcador)}">${esc(etiquetaMarca(e.marcador))}</span>
        <span class="formas">${e.formas.map(esc).join(" · ")}</span>
        ${!e.activo ? `<button class="boton-texto" data-reactivar-ent="${e.id}">Volver a tapar</button>` : (e.conservado || e.en_lista) ? `<span></span>` : `<button class="boton-texto" data-descartar-ent="${e.id}" title="No es un dato personal">Dejar a la vista</button>`}
        <span class="meta">${e.conservado ? "a la vista por el tipo de asunto · " : ""}${e.en_lista ? "en la lista «Nunca tapar» · " : ""}${e.docs.length} documento${e.docs.length === 1 ? "" : "s"} · ${esc(e.origenes.join(", "))}${e.ambigua ? " · ambigua: revisa si es la misma persona" : ""}</span>
      </div>`; }).join("")}</div>`).join("")}</div>`;
  $("#mesa-datos-cerrar", el).onclick = () => alternarDatosMesa(false);
  $(".form-anadir", el).onsubmit = async (ev) => {
    ev.preventDefault();
    if (MESA.trabajo) return;
    const f = new FormData(ev.target);
    try {
      const r2 = await api("POST", `/api/proyectos/${E.proyecto.id}/registro`, { texto: f.get("texto"), tipo: f.get("tipo"), rehacer: MESA.actual?.id, conversacion: E.conversacion });
      await cargarRegistroMesa();
      const marca = r2.nuevas?.[0]?.marcador;
      if (r2.trabajo) seguirTrabajoMesa(r2.trabajo, "Tapando…", marca ? { texto: `Tapado como «${etiquetaMarca(marca)}».`, etiqueta: "Deshacer", accion: () => deshacerTapado(marca) } : { texto: "Ese dato ya estaba en la lista." });
    } catch (e) { alerta(e.message); }
  };
  const filtro = $(".filtro-datos", el);
  if (filtro) filtro.oninput = () => {
    const q = filtro.value.trim().toLowerCase();
    $$(".entidad", el).forEach((n) => (n.hidden = q && !n.dataset.buscar.includes(q)));
  };
}

function alternarDatosMesa(abrir) {
  MESA.datosAbiertos = abrir === undefined ? !MESA.datosAbiertos : abrir;
  $("#mesa").classList.toggle("con-datos", MESA.datosAbiertos);
  try { localStorage.setItem("seudonimo.datosMesa", MESA.datosAbiertos ? "1" : ""); } catch (e) { /* sin almacenamiento */ }
}

// ------------------------------------------------------------------ diálogos

function alerta(texto, titulo = "No se ha podido hacer") {
  return confirmar(titulo, texto, "Entendido", true);
}

function confirmar(titulo, texto, si = "Aceptar", soloAceptar = false) {
  const d = $("#dlg-confirmar");
  $("#confirmar-titulo").textContent = titulo;
  $("#confirmar-texto").textContent = texto;
  $("#confirmar-si").textContent = si;
  $("button[value=no]", d).hidden = soloAceptar;
  d.showModal();
  return new Promise((res) => d.addEventListener("close", () => res(d.returnValue === "si"), { once: true }));
}

let PLANTILLAS = null;

async function prepararPlantillas(f, p) {
  if (!PLANTILLAS) PLANTILLAS = await api("GET", "/api/plantillas");
  const sel = f.plantilla;
  sel.innerHTML = PLANTILLAS.plantillas.map((x) => `<option value="${x.id}">${esc(x.nombre)}</option>`).join("");
  sel.value = p.plantilla || "general";
  const marcar = (lista) => {
    $("#conservar-tipos").innerHTML = Object.entries(PLANTILLAS.etiquetas).map(([k, v]) =>
      `<label class="opcion"><input type="checkbox" value="${k}"${lista.includes(k) ? " checked" : ""}> <span>${esc(v)}</span></label>`).join("");
    resumir();
  };
  const resumir = () => {
    const n = $$("#conservar-tipos input:checked").map((x) => PLANTILLAS.etiquetas[x.value]);
    $("#conservar-resumen").textContent = n.length ? `· a la vista: ${n.join(", ")}` : "· se tapa todo";
  };
  const desc = () => { $("#plantilla-desc").textContent = (PLANTILLAS.plantillas.find((x) => x.id === sel.value) || {}).descripcion || ""; };
  sel.onchange = () => { marcar((PLANTILLAS.plantillas.find((x) => x.id === sel.value) || {}).conservar || []); desc(); };
  $("#conservar-tipos").onchange = resumir;
  marcar(Array.isArray(p.conservar) ? p.conservar : (() => { try { return JSON.parse(p.conservar || "[]"); } catch (e) { return []; } })());
  desc();
}

function abrirDialogoProyecto(editar) {
  const d = $("#dlg-proyecto");
  const f = $("#form-proyecto");
  d.className = "dialogo " + (editar ? "edicion" : "alta");
  $("#dlg-proyecto-titulo").textContent = editar ? "Ajustes del expediente" : "Nuevo expediente";
  $("#guardar-proyecto").textContent = editar ? "Guardar" : "Crear expediente";
  $("#mas-opciones").open = !!editar;
  const sel = $("#proyecto-modelo");
  const nombres = E.modelos.map((m) => m.nombre);
  const actual = editar ? E.proyecto.modelo : E.modeloDefecto;
  if (actual && !nombres.includes(actual)) nombres.unshift(actual);
  sel.innerHTML = nombres.map((n) => `<option${n === actual ? " selected" : ""}>${esc(n)}</option>`).join("");
  const p = editar ? E.proyecto : { nombre: "", perfil: "estandar", tabla: "cifrada", salida: "", instrucciones: "", logos: 1, plantilla: "general", conservar: [] };
  prepararPlantillas(f, p);
  f.nombre.value = p.nombre;
  f.perfil.value = p.perfil;
  f.tabla.value = p.tabla;
  f.salida.value = editar ? (p.salida || "") : "";
  f.guardar.value = editar ? (p.guardar_efectivo || "junto") : "junto";
  f.instrucciones.value = p.instrucciones || "";
  f.logos.checked = !!p.logos;
  f.vigilar.checked = !!p.vigilar;
  f.temporal.checked = false;
  $("#aviso-salida").hidden = !(editar && p.salida_sincronizada);
  d.showModal();
  d.onclose = async () => {
    if (d.returnValue !== "aceptar") { E.rutasPendientes = null; return; }
    const datos = { nombre: f.nombre.value.trim(), modelo: sel.value, perfil: f.perfil.value, tabla: f.tabla.value,
      plantilla: f.plantilla.value, conservar: $$("#conservar-tipos input:checked").map((x) => x.value),
      guardar: f.guardar.value, salida: f.guardar.value === "carpeta" ? (f.salida.value || null) : null };
    if (datos.guardar === "carpeta" && !datos.salida) { alerta("Elige la carpeta donde quieres guardar las copias, o marca «Junto a los originales».", "Falta la carpeta"); return; }
    if (!editar && E.rutasPendientes) datos.rutas = E.rutasPendientes;
    try {
      if (editar) {
        if (E.proyecto.tabla === "cifrada" && datos.tabla === "sin_tabla") {
          const ok = await confirmar("Dejar de guardar la clave", "Se destruirá la clave de este expediente: ya no se podrán volver a poner los nombres en las copias generadas ni en las respuestas de otra IA.", "Destruir la clave");
          if (!ok) return;
        }
        Object.assign(datos, { instrucciones: f.instrucciones.value, logos: f.logos.checked ? 1 : 0, vigilar: f.vigilar.checked });
        await api("PATCH", `/api/proyectos/${E.proyecto.id}`, datos);
        await refrescarProyectos();
        await abrirProyecto(E.proyecto.id, E.conversacion);
      } else {
        datos.temporal = f.temporal.checked;
        const rutas = datos.rutas; delete datos.rutas;
        E.rutasPendientes = null;
        const nuevo = await api("POST", "/api/proyectos", datos);
        await refrescarProyectos();
        await abrirProyecto(nuevo.id);
        if (rutas && rutas.length) await anadirRutas(rutas);
      }
    } catch (e) { alerta(e.message); }
  };
}

async function abrirModelos() {
  await refrescarModelos();
  pintarModelos();
  api("GET", "/api/voz").then(pintarVoz).catch(() => {});
  $("#dlg-modelos").showModal();
  const vigilar = async () => {
    if (!$("#dlg-modelos").open) return;
    const activas = Object.values(E.catalogo?.descargas || {}).some((d) => d.fase === "trabajando");
    if (activas) { await refrescarModelos(); pintarModelos(); }
    setTimeout(vigilar, 1500);
  };
  vigilar();
}

function capacidades(caps) {
  const n = { completion: "texto", tools: "herramientas", vision: "imágenes", thinking: "razonamiento", audio: "audio", embedding: "vectores" };
  return `<div class="capacidades">${(caps || []).map((c) => `<span class="chip">${esc(n[c] || c)}</span>`).join("")}</div>`;
}

function pintarModelos() {
  const c = E.catalogo || {};
  const gb = (b) => (b / 1e9).toLocaleString("es-ES", { maximumFractionDigits: 1 }) + " GB";
  $("#ollama-estado").innerHTML = c.error ? `<p class="aviso-campo" style="margin:0 0 10px">${esc(c.error)}</p>` : `<p class="nota">Espacio libre: ${String(c.espacio_libre_gb ?? "?").replace(".", ",")} GB.</p>`;
  $("#modelos-instalados").innerHTML = E.modelos.length ? E.modelos.map((m) => `<div class="modelo">
      <span><b>${esc(m.nombre)}</b>${m.nombre === E.modeloDefecto ? ' <span class="chip sin_hallazgos">por defecto</span>' : ""} <span class="nota">${gb(m.tamano)} · ${esc(m.parametros || "")} · ${esc(m.cuantizacion || "")}</span></span>
      <span class="botones">
        ${m.nombre === E.modeloDefecto ? "" : `<button type="button" class="boton-texto" data-defecto="${esc(m.nombre)}">Usar por defecto</button>`}
        <button type="button" class="boton-texto" data-licencia="${esc(m.nombre)}">Licencia</button>
        <button type="button" class="boton-texto peligro" data-borrar-modelo="${esc(m.nombre)}">Borrar</button>
      </span>
      ${capacidades(m.capacidades)}
    </div>`).join("") : `<p class="nota">Ninguno todavía.</p>`;
  const desc = c.descargas || {};
  $("#modelos-catalogo").innerHTML = (c.catalogo || []).filter((m) => !m.instalado || desc[m.nombre]?.fase === "trabajando").map((m) => {
    const d = desc[m.nombre];
    return `<div class="modelo">
      <span><b>${esc(m.nombre)}</b>${m.recomendado ? ' <span class="chip en_cola">recomendado</span>' : ""}</span>
      <span class="botones">${d && d.fase === "trabajando" ? `<span class="nota">${Math.round(d.progreso * 100)} %</span>` : `<button type="button" class="boton" data-descargar="${esc(m.nombre)}">Descargar</button>`}</span>
      <span class="desc">${esc(m.descripcion)} Memoria recomendada: ${m.memoria} GB.${d && d.fase !== "trabajando" && d.error ? ` <b style="color:var(--rojo)">${esc(d.error)}</b>` : ""}${d && d.fase === "trabajando" ? ` ${esc(d.mensaje)}` : ""}</span>
    </div>`;
  }).join("") || `<p class="nota">Tienes todos los del catálogo.</p>`;
}

async function verLicencia(nombre) {
  try {
    const f = await api("GET", `/api/modelos/ficha?nombre=${encodeURIComponent(nombre)}`);
    $("#licencia-titulo").textContent = `Licencia de ${nombre}`;
    $("#licencia-texto").textContent = f.licencia || "El modelo no declara licencia en su ficha. Consúltala en ollama.com antes de usarlo profesionalmente.";
    $("#dlg-licencia").showModal();
  } catch (e) { alerta(e.message); }
}

function mostrarPestana() {
  // ya no hay pestañas: la lista de documentos lo enseña todo (en pantallas estrechas, se abre)
  $("#app").classList.remove("sin-panel");
  return refrescarOperaciones();
}

// ------------------------------------------------------------------ dictado por voz
// Se graba en la ventana, se convierte a WAV mono de 16 kHz y lo transcribe Whisper en este
// ordenador. El texto se escribe en la caja de mensaje para revisarlo antes de enviarlo.

const DICTADO = { estado: "parado", flujo: null, ctx: null, nodo: null, trozos: [], tasa: 48000, t0: 0, reloj: null };
const MAX_DICTADO = 180;

async function alternarDictado() {
  if (DICTADO.estado === "grabando") return pararDictado();
  if (DICTADO.estado !== "parado") return;
  const v = await api("GET", "/api/voz");
  if (!v.binario) return alerta("Esta instalación no incluye el programa de dictado.", "Dictado no disponible");
  if (!v.listo) {
    const m = v.modelos.find((x) => x.nombre === v.activo) || v.modelos[0];
    if (v.descarga.fase === "trabajando") return alerta(`Se está descargando el modelo de voz (${Math.round(v.descarga.progreso * 100)} %). Prueba en un momento.`, "Un momento");
    const ok = await confirmar("Activar el dictado",
      `Para dictar hace falta el modelo de voz «${m.nombre}» (${m.mb} MB). Se descarga una sola vez y después todo funciona sin internet: tu voz nunca sale de este ordenador.`, "Descargar");
    if (!ok) return;
    await api("POST", "/api/voz/descargar", { nombre: m.nombre });
    seguirDescargaVoz();
    return;
  }
  try {
    DICTADO.flujo = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  } catch (e) {
    return alerta("No tengo permiso para usar el micrófono, o no hay ninguno conectado. En Mac: Ajustes del Sistema > Privacidad y seguridad > Micrófono, y activa Seudónimo.", "Micrófono no disponible");
  }
  const Ctx = window.AudioContext || window.webkitAudioContext;
  DICTADO.ctx = new Ctx();
  DICTADO.tasa = DICTADO.ctx.sampleRate;
  const fuente = DICTADO.ctx.createMediaStreamSource(DICTADO.flujo);
  DICTADO.nodo = DICTADO.ctx.createScriptProcessor(4096, 1, 1);
  DICTADO.trozos = [];
  DICTADO.nodo.onaudioprocess = (ev) => {
    const datos = ev.inputBuffer.getChannelData(0);
    DICTADO.trozos.push(new Float32Array(datos));
    let pico = 0;
    for (let i = 0; i < datos.length; i += 64) pico = Math.max(pico, Math.abs(datos[i]));
    $("#dictar").style.setProperty("--nivel", Math.min(1, pico * 4).toFixed(2));
  };
  fuente.connect(DICTADO.nodo);
  DICTADO.nodo.connect(DICTADO.ctx.destination);
  DICTADO.estado = "grabando";
  DICTADO.t0 = Date.now();
  pintarDictado();
  DICTADO.reloj = setInterval(() => {
    const s = Math.round((Date.now() - DICTADO.t0) / 1000);
    if (s >= MAX_DICTADO) pararDictado();
    else pintarDictado();
  }, 500);
}

function cancelarDictado() {
  if (DICTADO.estado !== "grabando") return;
  limpiarGrabacion();
  DICTADO.estado = "parado";
  pintarDictado();
}

function limpiarGrabacion() {
  clearInterval(DICTADO.reloj);
  try { DICTADO.nodo && DICTADO.nodo.disconnect(); } catch (e) { /* ya */ }
  try { DICTADO.flujo && DICTADO.flujo.getTracks().forEach((t) => t.stop()); } catch (e) { /* ya */ }
  try { DICTADO.ctx && DICTADO.ctx.close(); } catch (e) { /* ya */ }
  $("#dictar").style.removeProperty("--nivel");
}

async function pararDictado() {
  limpiarGrabacion();
  DICTADO.estado = "transcribiendo";
  pintarDictado();
  try {
    const wav = aWav(DICTADO.trozos, DICTADO.tasa);
    DICTADO.trozos = [];
    const r = await fetch(E.conexion.base + "/api/voz/transcribir", {
      method: "POST", headers: { "Content-Type": "audio/wav", "X-Seudonimo-Token": E.conexion.token }, body: wav,
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "No se ha podido transcribir.");
    if (d.texto) {
      const e = $("#entrada");
      e.value = (e.value.trim() ? e.value.trim() + " " : "") + d.texto;
      e.dispatchEvent(new Event("input"));
      e.focus();
    } else {
      alerta("No he entendido nada en la grabación. Comprueba el micrófono y vuelve a probar.", "Sin texto");
    }
  } catch (e) {
    alerta(e.message);
  } finally {
    DICTADO.estado = "parado";
    pintarDictado();
  }
}

function pintarDictado() {
  const b = $("#dictar");
  const s = Math.round((Date.now() - DICTADO.t0) / 1000);
  b.classList.toggle("grabando", DICTADO.estado === "grabando");
  b.disabled = DICTADO.estado === "transcribiendo";
  $("#dictar-texto").textContent = DICTADO.estado === "grabando" ? `Parar · ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`
    : DICTADO.estado === "transcribiendo" ? "Transcribiendo…" : "Dictar";
  b.setAttribute("aria-pressed", String(DICTADO.estado === "grabando"));
}

// Mezcla los trozos, baja a 16 kHz (media por bloques) y escribe un WAV PCM de 16 bits
function aWav(trozos, tasa) {
  const total = trozos.reduce((n, t) => n + t.length, 0);
  const todo = new Float32Array(total);
  let o = 0;
  for (const t of trozos) { todo.set(t, o); o += t.length; }
  const paso = tasa / 16000;
  const n = Math.floor(total / paso);
  const pcm = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * paso), b = Math.min(total, Math.floor((i + 1) * paso));
    let s = 0;
    for (let k = a; k < b; k++) s += todo[k];
    const v = Math.max(-1, Math.min(1, s / Math.max(1, b - a)));
    pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const dv = new DataView(buf);
  const txt = (p, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(p + i, s.charCodeAt(i)); };
  txt(0, "RIFF"); dv.setUint32(4, 36 + pcm.length * 2, true); txt(8, "WAVE"); txt(12, "fmt ");
  dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, 16000, true);
  dv.setUint32(28, 32000, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); txt(36, "data");
  dv.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);
  return new Blob([buf], { type: "audio/wav" });
}

function seguirDescargaVoz() {
  const b = $("#aviso-banda");
  const paso = async () => {
    const v = await api("GET", "/api/voz");
    const d = v.descarga;
    if (d.fase === "trabajando") {
      b.hidden = false;
      b.innerHTML = `<span>${esc(d.mensaje || "Descargando el modelo de voz…")}</span><span>${Math.round(d.progreso * 100)} %</span>`;
      setTimeout(paso, 1000);
    } else if (d.fase === "error") {
      b.hidden = false;
      b.innerHTML = `<span>${esc(d.error)}</span>`;
    } else {
      pintarAviso();
      if (d.fase === "listo") alerta("Ya puedes dictar: pulsa «Dictar», habla y vuelve a pulsar para terminar.", "Dictado listo");
    }
    if ($("#dlg-modelos").open) pintarVoz(v);
  };
  paso();
}

function pintarVoz(v) {
  const el = $("#voz-modelos");
  if (!el) return;
  if (!v.binario) { el.innerHTML = `<p class="nota">Esta instalación no incluye el programa de dictado.</p>`; return; }
  el.innerHTML = v.modelos.map((m) => {
    const bajando = v.descarga.fase === "trabajando" && v.descarga.nombre === m.nombre;
    return `<div class="modelo">
      <span><b>Whisper ${esc(m.nombre)}</b>${m.nombre === v.activo ? ' <span class="chip sin_hallazgos">en uso</span>' : ""} <span class="nota">${m.mb} MB</span></span>
      <span class="botones">${bajando ? `<span class="nota">${Math.round(v.descarga.progreso * 100)} %</span>`
        : !m.descargado ? `<button type="button" class="boton" data-voz-descargar="${m.nombre}">Descargar</button>`
        : m.nombre !== v.activo ? `<button type="button" class="boton-texto" data-voz-usar="${m.nombre}">Usar</button>` : ""}</span>
      <span class="desc">${esc(m.descripcion)}</span>
    </div>`;
  }).join("");
}

// ------------------------------------------------------------------ revisión de la copia
// La copia seudonimizada entera. Doble clic (o selección) sobre lo que se ha escapado y «Tapar»:
// la copia se rehace en el acto, con «Deshacer». Clic en una etiqueta para ver qué tapa y dejarla a
// la vista si no es un dato personal (también en el acto). Nada queda «pendiente».

const MESA = { copias: [], actual: null, datos: null, registro: null, trabajo: null, sondeo: null, paginas: new Set(), datosAbiertos: false };
const RE_MARCA = /\[(?:[A-Z_]+_\d{1,4}|LOGO O SELLO|CARA)\]/g;

function etiquetaMarca(m) {
  // [PERSONA_001] → «Persona 1»: lo que ve quien revisa; el archivo conserva el marcador
  if (m === "[LOGO O SELLO]") return "Logo o sello";
  if (m === "[CARA]") return "Cara";
  const x = /^\[([A-Z_]+)_(\d{1,4})\]$/.exec(m);
  if (!x) return m;
  const etq = (MESA.registro?.etiquetas || E.etiquetas || {})[x[1]] || x[1].charAt(0) + x[1].slice(1).toLowerCase().replace(/_/g, " ");
  return `${etq} ${parseInt(x[2], 10)}`;
}

async function abrirMesa(aid) {
  if (!E.proyecto) return;
  MESA.copias = await api("GET", `/api/proyectos/${E.proyecto.id}/copias`);
  if (!MESA.copias.length) return alerta("Todavía no hay copias seudonimizadas en este expediente. Pide primero que seudonimice los documentos.", "Nada que revisar");
  $("#mesa").hidden = false;
  document.body.classList.add("con-mesa");
  $("#mesa").classList.toggle("con-datos", MESA.datosAbiertos);
  await cargarRegistroMesa();
  const elegido = MESA.copias.find((c) => c.id === aid) || MESA.copias.find((c) => c.estado === "revision") || MESA.copias[0];
  await verCopia(elegido.id);
  pintarEstadoMesa();
}

function cerrarMesa() {
  $("#mesa").hidden = true;
  $("#mesa-pop").hidden = true;
  document.body.classList.remove("con-mesa");
  refrescarOperaciones();
}

async function cargarRegistroMesa() {
  MESA.registro = await api("GET", `/api/proyectos/${E.proyecto.id}/registro`);
  pintarRevision($("#mesa-datos"), true);
  const n = (MESA.registro.entidades || []).filter((e) => e.activo).length;
  $("#mesa-datos-toggle").textContent = `Datos tapados${n ? " · " + n : ""}`;
}

function pintarDocsMesa() {
  const el = $("#mesa-docs");
  el.hidden = MESA.copias.length < 2;
  el.innerHTML = `<h3>Documentos</h3>` + MESA.copias.map((c) => `<button class="mesa-doc${MESA.actual && c.id === MESA.actual.id ? " activo" : ""}" data-mesa-doc="${c.id}">
      <span class="nombre">${esc(c.original)}</span><span class="chip ${esc(c.estado)}">${esc(c.estado === "revision" ? "Revísala" : ESTADOS[c.estado] || c.estado)}</span></button>`).join("");
  $("#mesa-nombre").textContent = MESA.actual ? MESA.actual.original : "";
}

async function verCopia(aid) {
  $("#mesa-pop").hidden = true;
  MESA.paginas.clear();
  pintarRepaso();
  MESA.actual = MESA.copias.find((c) => c.id === aid);
  pintarDocsMesa();
  const hoja = $("#mesa-texto");
  hoja.innerHTML = `<p class="nota">Leyendo la copia${/\.pdf$/i.test(MESA.actual.copia) ? " (las páginas escaneadas pasan por el OCR: puede tardar unos segundos)" : ""}…</p>`;
  try {
    MESA.datos = await api("GET", `/api/proyectos/${E.proyecto.id}/copias/${aid}`);
  } catch (e) { hoja.innerHTML = `<p class="nota">${esc(e.message)}</p>`; return; }
  pintarHoja();
}

function pintarHoja() {
  const d = MESA.datos;
  const t = d.texto || "";
  // tramos: los datos conocidos que siguen a la vista (rojo) y las etiquetas (tachón)
  const tramos = d.escapados.map((x) => ({ ini: x.ini, fin: x.fin, tipo: "escapado", marca: x.marcador }));
  for (const m of t.matchAll(RE_MARCA)) tramos.push({ ini: m.index, fin: m.index + m[0].length, tipo: "marca", marca: m[0] });
  tramos.sort((a, b) => a.ini - b.ini || b.fin - a.fin);
  const cortes = d.paginas && d.paginas.length ? d.paginas : [0];
  const pintarTramo = (a, b) => {
    let html = "", pos = a;
    for (const s of tramos) {
      if (s.ini < pos || s.ini >= b) continue;
      html += esc(t.slice(pos, s.ini));
      const trozo = esc(t.slice(s.ini, Math.min(s.fin, b)));
      html += s.tipo === "marca"
        ? `<button type="button" class="tachon marca" data-marca="${esc(s.marca)}" title="En el archivo: ${esc(s.marca)}. Clic para ver qué tapa.">${esc(etiquetaMarca(s.marca))}</button>`
        : `<mark class="escapado" data-marca="${esc(s.marca)}" title="Este dato ya está en la lista (${esc(etiquetaMarca(s.marca))}) pero esta copia es anterior: pulsa «Actualizar esta copia».">${trozo}</mark>`;
      pos = Math.min(s.fin, b);
    }
    return html + esc(t.slice(pos, b));
  };
  const enRojo = (a, b) => d.escapados.some((x) => x.ini >= a && x.ini < b);
  let html = "";
  cortes.forEach((ini, i) => {
    const fin = i + 1 < cortes.length ? cortes[i + 1] : t.length;
    const cuerpo = pintarTramo(ini, fin).replace(/\n+$/, "");
    if (cortes.length === 1) { html += `<div class="texto-copia">${cuerpo}</div>`; return; }
    const n = i + 1;
    const u = d.unidad || "página", U = u.charAt(0).toUpperCase() + u.slice(1);
    html += `<section class="pagina${enRojo(ini, fin) ? " con-restos" : ""}" id="pagina-${n}">
      <header class="pagina-cab"><span>${U} ${n} de ${cortes.length}</span>
        <label class="opcion repaso" title="El modelo vuelve a leer solo esta ${u} buscando datos que se le escaparan"><input type="checkbox" data-repasar-pagina="${n}"${MESA.paginas.has(n) ? " checked" : ""}> <span>Volver a leer esta ${u}</span></label></header>
      <div class="texto-copia">${cuerpo || `<span class="nota">${U} sin texto legible.</span>`}</div></section>`;
  });
  const n = d.escapados.length;
  $("#mesa-texto").innerHTML = (n && !MESA.trabajo ? `<div class="aviso-hoja"><span>Esta copia es anterior a ${n === 1 ? "un cambio" : n + " cambios"} de la lista de datos (en rojo).</span><button class="boton boton-principal" data-actualizar-copia>Actualizar esta copia</button></div>` : "")
    + (cortes.length > 1 ? "" : "")
    + (html || '<span class="nota">La copia no tiene texto legible.</span>')
    + `<p class="nota ayuda-mesa">¿Algo sin tapar? Haz doble clic encima (o selecciónalo) y pulsa «Tapar». ¿Una etiqueta que no debería estar? Haz clic en ella y elige «Dejar a la vista». Los cambios se aplican en el acto y se pueden deshacer.${cortes.length > 1 ? ` Si en una ${d.unidad || "página"} falta mucho, marca «Volver a leer esta ${d.unidad || "página"}».` : ""}</p>`;
  $$("[data-repasar-pagina]").forEach((c) => (c.onchange = () => {
    const p = +c.dataset.repasarPagina;
    if (c.checked) MESA.paginas.add(p); else MESA.paginas.delete(p);
    pintarRepaso();
  }));
  $("#mesa-hoja").scrollTop = 0;
}

function tipoProbable(s) {
  const x = s.replace(/[\s.-]/g, "");
  if (/^[XYZ]?\d{7,8}[A-Z]$/i.test(x)) return "DNI";
  if (/^[A-HJ-NP-SUVW]\d{7}[0-9A-J]$/i.test(x)) return "NIF";
  if (/^ES\d{22}$/i.test(x)) return "IBAN";
  if (/@/.test(s)) return "EMAIL";
  if (/^\+?\d{9,12}$/.test(x)) return "TELEFONO";
  if (/^\d{12}$/.test(x) || /^\d{2}\/?\d{8}\/?\d{2}$/.test(x)) return "NAF";
  if (/\b(calle|c\/|avda|avenida|plaza|camino|carretera|urb)/i.test(s)) return "DOMICILIO";
  if (/\b(s\.?l\.?u?|s\.?a\.?|s\.?c\.?p|s\.?coop|sociedad)\b/i.test(s)) return "EMPRESA";
  if (/^[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü'-]+(\s+(de|del|la|y)?\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü'-]+){0,4}$/.test(s.trim())) return "PERSONA";
  return "OTRO";
}

function situarPop(rect) {
  const pop = $("#mesa-pop");
  pop.hidden = false;
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let x = rect.left + rect.width / 2 - w / 2, y = rect.bottom + 8;
  if (y + h > innerHeight - 8) y = rect.top - h - 8;
  pop.style.left = Math.max(8, Math.min(x, innerWidth - w - 8)) + "px";
  pop.style.top = Math.max(8, y) + "px";
}

function popTapar() {
  if (MESA.trabajo) return;
  const sel = getSelection();
  const s = sel.toString().replace(/\s+/g, " ").trim();
  if (!s || s.length < 2 || s.length > 150 || !sel.rangeCount) return;
  if (!$("#mesa-texto").contains(sel.anchorNode)) return;
  if (RE_MARCA.test(s)) { RE_MARCA.lastIndex = 0; return; }
  const etiquetas = MESA.registro?.etiquetas || {};
  const tipo = tipoProbable(s);
  $("#mesa-pop").innerHTML = `<div class="pop-titulo">Tapar «${esc(s.length > 60 ? s.slice(0, 57) + "…" : s)}»</div>
    <div class="fila-campo"><select id="pop-tipo" aria-label="Qué es">${Object.entries(etiquetas).map(([k, v]) => `<option value="${k}"${k === tipo ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
    <button type="button" class="boton boton-principal" id="pop-tapar">Tapar</button></div>
    <p class="nota">Se tapa ahora en esta copia y, cuando se actualicen, en las demás del expediente.</p>`;
  situarPop(sel.getRangeAt(0).getBoundingClientRect());
  $("#pop-tapar").onclick = async () => {
    try {
      const r = await api("POST", `/api/proyectos/${E.proyecto.id}/registro`, { texto: s, tipo: $("#pop-tipo").value, doc: MESA.actual.id, rehacer: MESA.actual.id, conversacion: E.conversacion });
      $("#mesa-pop").hidden = true;
      getSelection().removeAllRanges();
      await cargarRegistroMesa();
      const marca = r.nuevas?.[0]?.marcador;
      if (r.trabajo) seguirTrabajoMesa(r.trabajo, "Tapando…", marca
        ? { texto: `Tapado como «${etiquetaMarca(marca)}».`, etiqueta: "Deshacer", accion: () => deshacerTapado(marca) }
        : { texto: "Ese dato ya estaba en la lista; la copia se actualiza." });
    } catch (e) { alerta(e.message); }
  };
}

async function deshacerTapado(marca) {
  const e = (MESA.registro?.entidades || []).find((x) => x.marcador === marca);
  if (!e) return;
  const r = await api("POST", `/api/proyectos/${E.proyecto.id}/registro/${e.id}/descartar`, { rehacer: MESA.actual.id, conversacion: E.conversacion });
  await cargarRegistroMesa();
  if (r.trabajo) seguirTrabajoMesa(r.trabajo, "Deshaciendo…", { texto: "Vuelve a verse." });
}

function popMarca(boton) {
  const marca = boton.dataset.marca;
  const e = (MESA.registro?.entidades || []).find((x) => x.marcador === marca);
  const etq = MESA.registro?.etiquetas || {};
  $("#mesa-pop").innerHTML = e ? `<div class="pop-titulo"><span class="tachon">${esc(etiquetaMarca(marca))}</span> <span class="nota">${esc(etq[e.tipo] || e.tipo)} · en el archivo ${esc(marca)}</span></div>
      <p class="pop-formas">${e.formas.map(esc).join(" · ")}</p>
      <p class="nota">Aparece en ${e.docs.length} documento${e.docs.length === 1 ? "" : "s"} · ${esc(e.origenes.join(", "))}</p>
      ${e.activo ? `<button type="button" class="boton" data-descartar-ent="${e.id}"${MESA.trabajo ? " disabled" : ""}>Dejar a la vista (no es un dato personal)</button>`
        : `<p class="nota">Se deja a la vista.</p><button type="button" class="boton-texto" data-reactivar-ent="${e.id}">Volver a taparlo</button>`}`
    : `<div class="pop-titulo"><span class="tachon">${esc(etiquetaMarca(marca))}</span></div><p class="nota">Etiqueta de una revisión anterior.</p>`;
  situarPop(boton.getBoundingClientRect());
}

async function cambiarEntidadMesa(eid, accion) {
  $("#mesa-pop").hidden = true;
  const e = (MESA.registro?.entidades || []).find((x) => x.id === eid);
  const r = await api("POST", `/api/proyectos/${E.proyecto.id}/registro/${eid}/${accion}`, { rehacer: MESA.actual?.id, conversacion: E.conversacion });
  await cargarRegistroMesa();
  const nombre = e ? etiquetaMarca(e.marcador) : "";
  if (r.trabajo) seguirTrabajoMesa(r.trabajo, accion === "descartar" ? "Dejando a la vista…" : "Tapando…",
    accion === "descartar" ? { texto: `«${nombre}» vuelve a verse.`, etiqueta: "Deshacer", accion: () => cambiarEntidadMesa(eid, "reactivar") }
      : { texto: `«${nombre}» vuelve a estar tapado.`, etiqueta: "Deshacer", accion: () => cambiarEntidadMesa(eid, "descartar") });
}

function pintarEstadoMesa() {
  const el = $("#mesa-estado-trabajo");
  el.hidden = !MESA.trabajo;
  el.textContent = MESA.trabajo || "";
  document.body.classList.toggle("mesa-ocupada", !!MESA.trabajo);
  pintarRepaso();
}

function pintarRepaso() {
  const b = $("#mesa-repasar");
  const n = MESA.paginas.size;
  b.hidden = !n;
  b.disabled = !!MESA.trabajo;
  const u = MESA.datos?.unidad || "página", us = MESA.datos?.unidades || "páginas";
  b.textContent = n === 1 ? `Volver a leer la ${u} ${[...MESA.paginas][0]}` : `Volver a leer ${n} ${us}`;
}

async function repasarPaginas() {
  const pags = [...MESA.paginas].sort((a, b) => a - b);
  if (!pags.length || !MESA.actual) return;
  await rehacer([MESA.actual.id], pags);
  MESA.paginas.clear();
  pintarRepaso();
}

async function rehacer(ids, paginas) {
  const perfil = fondo() ? "intensivo" : "estandar";
  const cuerpo = paginas ? { archivos: ids, paginas, perfil, conversacion: E.conversacion }
    : { archivos: ids, solo_ciclos: true, perfil, conversacion: E.conversacion };
  const r = await api("POST", `/api/proyectos/${E.proyecto.id}/trabajos`, cuerpo);
  seguirTrabajoMesa(r.id, paginas ? "Volviendo a leer…" : "Actualizando la copia…", { texto: paginas ? "Páginas leídas de nuevo y copia actualizada." : "Copia actualizada." });
}

function seguirTrabajoMesa(tid, texto, aviso) {
  MESA.trabajo = texto;
  pintarEstadoMesa();
  clearTimeout(MESA.sondeo);
  const seguir = async () => {
    let t;
    try { t = await api("GET", `/api/trabajos/${tid}`); } catch (e) { t = null; }
    if (t && ["pendiente", "procesando"].includes(t.estado)) {
      MESA.trabajo = `${texto} ${Math.round(t.progreso * 100)} %`;
      pintarEstadoMesa();
      MESA.sondeo = setTimeout(seguir, 1200);
      return;
    }
    MESA.trabajo = null;
    pintarEstadoMesa();
    E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`);
    await refrescarOperaciones();
    if ($("#mesa").hidden) return;
    const actual = MESA.actual?.id;
    MESA.copias = await api("GET", `/api/proyectos/${E.proyecto.id}/copias`);
    await cargarRegistroMesa();
    const y = $("#mesa-hoja").scrollTop;
    await verCopia(MESA.copias.some((c) => c.id === actual) ? actual : MESA.copias[0].id);
    $("#mesa-hoja").scrollTop = y;
    if (aviso) avisoAccion(aviso.texto, aviso.etiqueta, aviso.accion);
  };
  seguir();
}

function avisoFlotante(texto) { avisoAccion(texto); }

function avisoAccion(texto, etiqueta, accion, ms) {
  const el = $("#aviso-flotante");
  el.innerHTML = `<span>${esc(texto)}</span>${etiqueta ? `<button type="button" class="aviso-accion">${esc(etiqueta)}</button>` : ""}`;
  if (etiqueta) $(".aviso-accion", el).onclick = () => { el.hidden = true; clearTimeout(el._t); Promise.resolve(accion()).catch((e) => alerta(e.message)); };
  el.hidden = false;
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.hidden = true), ms || (etiqueta ? 8000 : 3500));
}

// ------------------------------------------------------------------ copiar para la IA y poner nombres

function copiarAlPortapapeles(texto) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(texto).catch(() => copiarConArea(texto));
  }
  return Promise.resolve(copiarConArea(texto));
}

function copiarConArea(texto) {
  const a = document.createElement("textarea");
  a.value = texto;
  a.style.position = "fixed"; a.style.opacity = "0";
  document.body.appendChild(a);
  a.select();
  const ok = document.execCommand("copy");
  a.remove();
  if (!ok) throw new Error("No he podido copiar al portapapeles.");
}

async function copiarParaIA() {
  const r = await api("POST", `/api/proyectos/${E.proyecto.id}/copias/texto`, {});
  await copiarAlPortapapeles(r.texto);
  const miles = Math.round(r.caracteres / 1000);
  avisoFlotante(`Copiado: ${r.documentos} documento${r.documentos === 1 ? "" : "s"} seudonimizado${r.documentos === 1 ? "" : "s"} (${miles || 1} mil caracteres). Pégalo en el chat de la IA.`);
}

function abrirNombres() {
  const d = $("#dlg-nombres");
  if (E.proyecto.tabla !== "cifrada") return alerta("Este expediente no guarda la clave para recuperar los nombres, así que no se pueden poner. Actívala en «Ajustes del expediente» (Más opciones) para los próximos trabajos.", "Sin clave");
  $("#nombres-entrada").value = "";
  $("#nombres-salida").value = "";
  $("#nombres-resumen").textContent = "";
  $("#nombres-copiar").disabled = true;
  let t = null;
  $("#nombres-entrada").oninput = () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const texto = $("#nombres-entrada").value;
      if (!texto.trim()) { $("#nombres-salida").value = ""; $("#nombres-resumen").textContent = ""; $("#nombres-copiar").disabled = true; return; }
      try {
        const r = await api("POST", `/api/proyectos/${E.proyecto.id}/reidentificar`, { texto });
        $("#nombres-salida").value = r.texto;
        $("#nombres-copiar").disabled = false;
        $("#nombres-resumen").textContent = `${r.sustituidos} etiqueta${r.sustituidos === 1 ? "" : "s"} sustituida${r.sustituidos === 1 ? "" : "s"} (${r.distintos} dato${r.distintos === 1 ? "" : "s"} distinto${r.distintos === 1 ? "" : "s"}).`
          + (r.desconocidos.length ? ` Estas etiquetas no son de este expediente: ${r.desconocidos.join(", ")}.` : "");
      } catch (e) { $("#nombres-resumen").textContent = e.message; }
    }, 250);
  };
  $("#nombres-copiar").onclick = async () => { await copiarAlPortapapeles($("#nombres-salida").value); avisoFlotante("Copiado con los datos reales."); };
  d.showModal();
}

// ------------------------------------------------------------------ listas del despacho

const LISTAS = { nunca: [], siempre: [], etiquetas: {} };

async function abrirListas() {
  const [l, pl] = await Promise.all([api("GET", "/api/listas"), api("GET", "/api/plantillas")]);
  LISTAS.nunca = l.nunca || []; LISTAS.siempre = l.siempre || []; LISTAS.etiquetas = pl.etiquetas;
  $("#siempre-tipo").innerHTML = Object.entries(pl.etiquetas).map(([k, v]) => `<option value="${k}"${k === "PERSONA" ? " selected" : ""}>${esc(v)}</option>`).join("");
  pintarListas();
  const anadir = (cual) => {
    const inp = $(`#${cual}-texto`);
    const texto = inp.value.trim();
    if (texto.length < 2) return;
    if (LISTAS[cual].some((x) => x.texto.toLowerCase() === texto.toLowerCase())) { inp.value = ""; return; }
    LISTAS[cual].unshift(cual === "siempre" ? { texto, tipo: $("#siempre-tipo").value } : { texto });
    inp.value = "";
    inp.focus();
    pintarListas();
  };
  $("#nunca-anadir").onclick = () => anadir("nunca");
  $("#siempre-anadir").onclick = () => anadir("siempre");
  $("#nunca-texto").onkeydown = (ev) => { if (ev.key === "Enter") { ev.preventDefault(); anadir("nunca"); } };
  $("#siempre-texto").onkeydown = (ev) => { if (ev.key === "Enter") { ev.preventDefault(); anadir("siempre"); } };
  const d = $("#dlg-listas");
  d.showModal();
  d.onclose = async () => {
    if (d.returnValue !== "guardar") return;
    try { await api("PUT", "/api/listas", { nunca: LISTAS.nunca, siempre: LISTAS.siempre }); avisoFlotante("Listas guardadas."); }
    catch (e) { alerta(e.message); }
  };
}

function pintarListas() {
  const fila = (cual, x, i) => `<li><span>${esc(x.texto)}</span>${x.tipo ? `<span class="chip">${esc(LISTAS.etiquetas[x.tipo] || x.tipo)}</span>` : ""}
    <button type="button" class="boton-texto" data-quitar-lista="${cual}:${i}" title="Quitar de la lista">Quitar</button></li>`;
  $("#nunca-lista").innerHTML = LISTAS.nunca.map((x, i) => fila("nunca", x, i)).join("") || `<li class="nota">Vacía.</li>`;
  $("#siempre-lista").innerHTML = LISTAS.siempre.map((x, i) => fila("siempre", x, i)).join("") || `<li class="nota">Vacía.</li>`;
}

// ------------------------------------------------------------------ panel redimensionable

function enlazarTirador() {
  const t = $("#tirador");
  const fijar = (w) => {
    w = Math.max(300, Math.min(w, Math.round(innerWidth * 0.55), 760));
    document.documentElement.style.setProperty("--ancho-panel", w + "px");
    try { localStorage.setItem("seudonimo.anchoPanel", String(w)); } catch (e) { /* sin almacenamiento */ }
  };
  try { const w = +localStorage.getItem("seudonimo.anchoPanel"); if (w) fijar(w); } catch (e) { /* sin almacenamiento */ }
  t.addEventListener("pointerdown", (ev) => {
    ev.preventDefault();
    t.setPointerCapture(ev.pointerId);
    document.body.classList.add("arrastrando");
    const mover = (e) => fijar(innerWidth - e.clientX);
    const soltar = () => { t.removeEventListener("pointermove", mover); document.body.classList.remove("arrastrando"); };
    t.addEventListener("pointermove", mover);
    t.addEventListener("pointerup", soltar, { once: true });
  });
  t.addEventListener("keydown", (ev) => {
    const w = $("#panel").offsetWidth;
    if (ev.key === "ArrowLeft") fijar(w + 24);
    if (ev.key === "ArrowRight") fijar(w - 24);
  });
  t.addEventListener("dblclick", () => fijar($("#panel").offsetWidth < 500 ? 560 : 400));
}

// ------------------------------------------------------------------ cola de trabajos (todos los proyectos)

async function refrescarCola() {
  clearTimeout(E.colaReloj);
  let activos = [];
  try {
    activos = await api("GET", "/api/trabajos/activos");
    // la lista de proyectos puede cambiar desde fuera (carpeta vigilada, otro proceso): se refresca
    const lista = await api("GET", "/api/proyectos");
    const firma = (l) => l.map((p) => p.id + ":" + p.nombre).sort().join("|");
    if (firma(lista) !== firma(E.proyectos)) { E.proyectos = lista; pintarLateral(); }
  } catch (e) { /* servicio ocupado: se reintenta */ }
  const el = $("#cola");
  if (!activos.length) { el.hidden = true; }
  else {
    const curso = activos.find((t) => t.estado === "procesando") || activos[0];
    const enCola = activos.length - 1;
    el.hidden = false;
    el.dataset.colaProyecto = curso.proyecto;
    el.innerHTML = `<span class="cola-titulo"><i class="punto-vivo"></i>Seudonimizando · ${Math.round(curso.progreso * 100)} %</span>
      <span class="cola-detalle">${esc(curso.nombre_proyecto)}${enCola ? ` · ${enCola} más en cola` : ""}</span>
      <span class="progreso"><i style="width:${Math.round(curso.progreso * 100)}%"></i></span>`;
    el.title = activos.map((t, i) => `${i ? "En cola" : "En curso"}: ${t.nombre_proyecto} (${t.documentos} documento${t.documentos === 1 ? "" : "s"})`).join("\n");
  }
  E.colaReloj = setTimeout(refrescarCola, activos.length ? 4000 : 12000);
}

// ------------------------------------------------------------------ actualizaciones

const PAGINA_VERSIONES = "https://github.com/josemagarciaruiz-cmd/seudonimo/releases";

async function acercaDe() {
  const actual = E.salud?.version || "";
  let r = null;
  try { r = await api("GET", "/api/actualizacion"); } catch (e) { /* sin conexión */ }
  const texto = r && r.nueva ? `Tienes instalada la versión ${actual}. Hay una más reciente: la ${r.version}.`
    : r && r.version ? `Tienes instalada la versión ${actual}, que es la última publicada.`
    : `Tienes instalada la versión ${actual}. No he podido consultar si hay otra más reciente (¿sin conexión?).`;
  if (r && r.nueva) { ACTUALIZACION = r; pintarActualizacion(); }
  const ok = await confirmar(`Seudónimo ${actual}`, texto + "\n\nLas versiones publicadas, con sus novedades, están en GitHub.",
    r && r.nueva ? "Actualizar ahora" : "Ver las versiones en GitHub");
  if (!ok) return;
  if (r && r.nueva) return actualizarAhora();
  await api("POST", "/api/actualizacion/descargar", { url: PAGINA_VERSIONES });
}

let ACTUALIZACION = null;

async function buscarActualizacion() {
  try {
    const r = await api("GET", "/api/actualizacion");
    ACTUALIZACION = r.nueva ? r : null;
  } catch (e) { return; }   // sin conexión: nada que avisar
  pintarActualizacion();
  clearTimeout(E.relojAct);
  E.relojAct = setTimeout(buscarActualizacion, 6 * 3600 * 1000);   // y cada seis horas
}

function pintarActualizacion() {
  const r = ACTUALIZACION;
  const banda = $("#banda-actualizacion"), lateral = $("#actualizacion");
  banda.hidden = lateral.hidden = !r || E.actualizacionOculta === r?.version;
  if (!r) return;
  lateral.innerHTML = `<b>Actualización disponible</b><span>Versión ${esc(r.version)} · pulsa para actualizar</span>`;
  lateral.onclick = actualizarAhora;
  banda.innerHTML = `<span class="act-icono" aria-hidden="true">⬆</span>
    <span class="act-texto"><b>Actualización disponible:</b> Seudónimo ${esc(r.version)} (tienes la ${esc(r.actual)}).</span>
    <button class="boton boton-actualizar" data-act="instalar">Actualizar</button>
    <button class="boton-texto" data-act="novedades">Novedades</button>
    <button class="boton-texto cerrar-banda" data-act="ocultar" title="Ocultar hasta la próxima vez" aria-label="Ocultar">✕</button>`;
  banda.onclick = (ev) => {
    const a = ev.target.closest("[data-act]")?.dataset.act;
    if (a === "instalar") actualizarAhora();
    else if (a === "novedades") alerta((r.notas || "Sin notas.").replace(/[*#`]/g, "").trim(), `Novedades de la ${r.version}`);
    else if (a === "ocultar") { E.actualizacionOculta = r.version; pintarActualizacion(); }
  };
}

async function actualizarAhora() {
  const r = ACTUALIZACION;
  if (!r) return;
  if (!r.instalable) {
    const ok = await confirmar(`Actualizar a la ${r.version}`, "Se abrirá la descarga en el navegador. Después, instálala igual que la primera vez: tus expedientes y datos se conservan.", "Descargar");
    if (ok) await api("POST", "/api/actualizacion/descargar", { url: r.descarga || PAGINA_VERSIONES });
    return;
  }
  const ok = await confirmar(`Actualizar a la ${r.version}`,
    "Seudónimo descargará la versión nueva desde GitHub, comprobará que el archivo es el publicado, se cerrará y volverá a abrirse ya actualizado. Tarda un minuto. Tus expedientes, conversaciones y datos se conservan.", "Actualizar ahora");
  if (!ok) return;
  try { await api("POST", "/api/actualizacion/instalar"); } catch (e) { return alerta(e.message); }
  const banda = $("#banda-actualizacion");
  const seguir = async () => {
    let s;
    try { s = await api("GET", "/api/actualizacion/estado"); } catch (e) { return; }   // la aplicación ya se está cerrando
    if (s.fase === "error") { banda.innerHTML = `<span class="act-texto">${esc(s.error)}</span>`; return; }
    banda.innerHTML = `<span class="act-icono" aria-hidden="true">⬆</span><span class="act-texto">${esc(s.mensaje || "Actualizando…")}</span>
      <span class="progreso act-progreso"><i style="width:${Math.round((s.progreso || 0) * 100)}%"></i></span>`;
    setTimeout(seguir, 800);
  };
  seguir();
}

// ------------------------------------------------------------------ eventos

function enlazar() {
  $("#nuevo-proyecto").onclick = () => abrirDialogoProyecto(false);
  $("#ajustes").onclick = (ev) => { ev.stopPropagation(); menuAjustes($("#ajustes")); };
  $("#menu-expediente").onclick = (ev) => { ev.stopPropagation(); menuExpediente($("#menu-expediente")); };
  $("#version").onclick = () => acercaDe().catch((e) => alerta(e.message));
  $("#cola").onclick = async () => {
    const pid = +$("#cola").dataset.colaProyecto;
    if (pid && (!E.proyecto || E.proyecto.id !== pid)) await abrirProyecto(pid);
    mostrarPestana("operaciones");
  };

  $("#mesa-cerrar").onclick = cerrarMesa;
  $("#mesa-repasar").onclick = () => repasarPaginas().catch((e) => alerta(e.message));
  $("#mesa-datos-toggle").onclick = () => alternarDatosMesa();
  try { MESA.datosAbiertos = !!localStorage.getItem("seudonimo.datosMesa"); } catch (e) { /* sin almacenamiento */ }
  $("#mesa-contexto").onclick = () => MESA.actual && riesgoContexto(MESA.actual.id).catch((e) => alerta(e.message));
  $("#mesa-abrir").onclick = () => MESA.actual && api("POST", "/api/abrir", { ruta: MESA.actual.ruta }).catch((e) => alerta(e.message));
  $("#mesa-texto").addEventListener("mouseup", () => setTimeout(popTapar, 0));
  $("#mesa-hoja").addEventListener("scroll", () => { $("#mesa-pop").hidden = true; });
  enlazarTirador();
  $("#alternar-panel").onclick = () => {
    const app = $("#app");
    app.classList.toggle("sin-panel");
    $("#alternar-panel").setAttribute("aria-expanded", String(!app.classList.contains("sin-panel")));
  };

  const entrada = $("#entrada");
  entrada.addEventListener("input", () => { entrada.style.height = "auto"; entrada.style.height = Math.min(entrada.scrollHeight, 240) + "px"; });
  entrada.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); $("#redactor").requestSubmit(); }
  });
  $("#redactor").onsubmit = (ev) => { ev.preventDefault(); const t = entrada.value; entrada.value = ""; entrada.style.height = "auto"; enviar(t); };
  $("#dictar").onclick = () => alternarDictado().catch((e) => alerta(e.message));
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && DICTADO.estado === "grabando") cancelarDictado();
    // ⌘/Ctrl + Mayúsculas + D: empezar o terminar de dictar
    if ((ev.metaKey || ev.ctrlKey) && ev.shiftKey && ev.key.toLowerCase() === "d" && !$("#redactor").hidden) { ev.preventDefault(); alternarDictado().catch((e) => alerta(e.message)); }
  });

  $("#elegir-salida").onclick = async () => {
    const r = await elegir("carpeta_salida");
    if (r[0]) { $("#form-proyecto").salida.value = r[0]; $("#form-proyecto").guardar.value = "carpeta"; }
  };
  $("#borrar-proyecto").onclick = () => eliminarProyecto(E.proyecto.id);
  $("#descargar-libre").onclick = async () => {
    const n = $("#modelo-libre").value.trim();
    if (!n) return;
    try { await api("POST", "/api/modelos/descargar", { nombre: n }); $("#modelo-libre").value = ""; await refrescarModelos(); pintarModelos(); } catch (e) { alerta(e.message); }
  };

  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    cerrarMenu();
    if (!$("#mesa").hidden && !document.querySelector("dialog[open]")) {
      ev.preventDefault();
      if (!$("#mesa-pop").hidden) $("#mesa-pop").hidden = true; else setTimeout(cerrarMesa, 0);
    }
  });
  document.addEventListener("click", async (ev) => {
    if (!ev.target.closest("#menu")) cerrarMenu();
    if (!ev.target.closest("#mesa-pop") && !ev.target.closest(".marca") && !getSelection().toString()) $("#mesa-pop").hidden = true;
    const b = ev.target.closest("button, [data-proyecto]");
    if (!b) return;
    const d = b.dataset;
    try {
      if (d.menuProyecto) { ev.stopPropagation(); menuProyecto(b, +d.menuProyecto); }
      else if (d.menuConv) { ev.stopPropagation(); menuConversacion(b, +d.menuConv); }
      else if (d.proyecto) await abrirProyecto(+d.proyecto);
      else if (d.conv) await abrirConversacion(+d.conv);
      else if (d.nuevaConv) await nuevaConversacion();
      else if (d.sugerencia) enviar(d.sugerencia);
      else if (d.rellenar) rellenar(d.rellenar);
      else if (d.menuCopia) { ev.stopPropagation(); menuCopia(b); }
      else if (d.quitarCarpeta) { await api("DELETE", `/api/proyectos/${E.proyecto.id}/carpetas/${d.quitarCarpeta}`); E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`); pintarArchivos(); }
      else if (d.cancelar) { await api("POST", `/api/trabajos/${d.cancelar}/cancelar`); avisoFlotante("Cancelado. Lo ya terminado se conserva."); refrescarOperaciones(); }
      else if (d.abrir) await api("POST", "/api/abrir", { ruta: d.abrir });
      else if (d.mostrar) await api("POST", "/api/mostrar", { ruta: d.mostrar });
      else if (d.contexto) await riesgoContexto(+d.contexto);
      else if (d.guardarEn) await guardarEn(d.guardarEn.split("\n"));
      else if (d.descartarEnt || d.reactivarEnt) {
        if (MESA.trabajo) return;
        await cambiarEntidadMesa(+(d.descartarEnt || d.reactivarEnt), d.descartarEnt ? "descartar" : "reactivar");
      }
      else if ("actualizarCopia" in d) { if (MESA.actual && !MESA.trabajo) await rehacer([MESA.actual.id]); }
      else if (d.marca) popMarca(b);
      else if (d.mesaDoc) await verCopia(+d.mesaDoc);
      else if (d.revisar) await abrirMesa(+d.revisar);
      else if (d.quitarLista) { const [cual, i] = d.quitarLista.split(":"); LISTAS[cual].splice(+i, 1); pintarListas(); }
      else if (d.descargar) { await api("POST", "/api/modelos/descargar", { nombre: d.descargar }); await refrescarModelos(); pintarModelos(); }
      else if (d.defecto) { await api("POST", "/api/modelos/defecto", { nombre: d.defecto }); await refrescarModelos(); pintarModelos(); }
      else if (d.vozDescargar) { await api("POST", "/api/voz/descargar", { nombre: d.vozDescargar }); seguirDescargaVoz(); }
      else if (d.vozUsar) pintarVoz(await api("POST", "/api/voz/modelo", { nombre: d.vozUsar }));
      else if (d.licencia) await verLicencia(d.licencia);
      else if (d.borrarModelo) {
        if (await confirmar("Borrar el modelo", `Se borrará ${d.borrarModelo} de este ordenador y se liberará su espacio. Podrás volver a descargarlo.`, "Borrar")) {
          await api("DELETE", "/api/modelos", { nombre: d.borrarModelo }); await refrescarModelos(); pintarModelos();
        }
      }
      else if (d.accion) await accion(d.accion);
    } catch (e) { alerta(e.message); }
  });
}

async function accion(a) {
  if (a === "nuevo-proyecto") abrirDialogoProyecto(false);
  else if (a === "abrir-modelos") abrirModelos();
  else if (a === "adjuntar-carpeta") anadirRutas(await elegir("carpeta"));
  else if (a === "adjuntar-archivos") anadirRutas(await elegir("archivos"));
  else if (a === "actualizar-carpetas") { await api("POST", `/api/proyectos/${E.proyecto.id}/carpetas/actualizar`); E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`); pintarArchivos(); }
  else if (a === "instalar-ollama") {
    await api("POST", "/api/instalacion/ollama");
    const b = $("#aviso-banda");
    const seguir = async () => {
      const s = await api("GET", "/api/instalacion");
      b.innerHTML = `<span>${esc(s.error || s.mensaje || "Instalando Ollama…")}</span>`;
      if (s.fase === "trabajando") setTimeout(seguir, 1500); else { await refrescarSalud(); await refrescarModelos(); }
    };
    seguir();
  }
  else if (a === "abrir-mesa") await abrirMesa();
  else if (a === "ver-resultados") await mostrarPestana();
  else if (a === "menu-anadir") abrirMenu($('[data-accion="menu-anadir"]'), [
    { texto: "Una carpeta…", accion: async () => anadirRutas(await elegir("carpeta")) },
    { texto: "Archivos sueltos…", accion: async () => anadirRutas(await elegir("archivos")) },
  ]);
  else if (a === "expediente-desde-carpeta") await expedienteDesde(await elegir("carpeta"));
  else if (a === "guia-vista") { try { localStorage.setItem("seudonimo.guia", "1"); } catch (e) { /* sin almacenamiento */ } pintarArchivos(); }
  else if (a === "cambiar-destino") abrirDialogoProyecto(true);
  else if (a === "seudonimizar-pendientes") {
    const pend = pendientes();
    if (!pend.length) return;
    if (!E.conversacion) {
      const c = await api("POST", `/api/proyectos/${E.proyecto.id}/conversaciones`, { titulo: `Seudonimización · ${new Date().toLocaleDateString("es-ES")}` });
      E.conversacion = c.id;
    }
    await api("POST", `/api/proyectos/${E.proyecto.id}/trabajos`, { archivos: pend.map((x) => x.id), perfil: fondo() ? "intensivo" : "estandar", conversacion: E.conversacion });
    E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`);
    pintarArchivos();
    await refrescarConversaciones();
    mostrarPestana("operaciones");
    await refrescarOperaciones();
    if ($("#hilo .vacio")) pintarVacioProyecto();
    avisoFlotante(`Seudonimizando ${pend.length === 1 ? "el documento" : pend.length + " documentos"}. Los originales no se tocan; puedes cancelarlo en la lista.`);
  }
  else if (a === "exportar-tabla") {
    const ok = await confirmar("Exportar la lista de nombres y etiquetas", "Es una hoja con cada etiqueta y el dato real al que sustituye: permite deshacer la seudonimización. Guárdala en el expediente, fuera de carpetas sincronizadas, y no la subas nunca a ninguna IA.", "Elegir dónde guardarla");
    if (!ok) return;
    const r = await elegir("guardar");
    if (!r[0]) return;
    const res = await api("POST", `/api/proyectos/${E.proyecto.id}/tabla/exportar`, { ruta: r[0] });
    if (res.sincronizada) alerta("La lista se ha guardado en una carpeta que parece sincronizada con la nube. Muévela a una carpeta local.", "Lista exportada");
  }
}

iniciar();
