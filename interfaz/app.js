/* Áurea Asistente Local · interfaz
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

const ESTADOS = {
  nuevo: "Sin tratar", no_admitido: "No admitido", en_cola: "En cola", procesando: "Procesando",
  sin_hallazgos: "Sin hallazgos", revision: "Requiere revisión", error: "Error", cancelado: "Cancelado", pendiente: "Pendiente",
};

// ------------------------------------------------------------------ conexión

async function conectar() {
  if (window.AUREA_CONEXION) return { base: "", token: window.AUREA_CONEXION.token };
  if (T) {
    const c = await T.core.invoke("conexion");   // puerto y token que ha elegido la ventana
    const base = `http://127.0.0.1:${c.puerto}`;
    for (let i = 0; i < 180; i++) {               // el servicio tarda unos segundos en arrancar
      try {
        const r = await fetch(base + "/api/salud", { headers: { "X-Aurea-Token": c.token } });
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
    headers: { "Content-Type": "application/json", "X-Aurea-Token": E.conexion.token },
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
    document.body.innerHTML = `<div class="vacio"><h2>No se ha podido arrancar Áurea</h2><p>${esc(e.message || e)}</p></div>`;
    return;
  }
  enlazar();
  await refrescarSalud();
  await refrescarModelos();
  await refrescarProyectos();
  if (E.proyectos.length) await abrirProyecto(E.proyectos[0].id);
  else pintarBienvenida();
  setInterval(refrescarSalud, 15000);
  if (T && T.webview) {
    // arrastrar archivos o carpetas sobre la ventana los añade al proyecto
    try {
      T.webview.getCurrentWebview().onDragDropEvent((ev) => {
        if (ev.payload.type === "drop" && ev.payload.paths?.length && E.proyecto) anadirRutas(ev.payload.paths);
      });
    } catch (e) { /* versión sin soporte */ }
  }
}

async function refrescarSalud() {
  try {
    E.salud = await api("GET", "/api/salud");
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
  const sel = $("#selector-modelo");
  const actual = E.proyecto?.modelo || E.modeloDefecto;
  const nombres = E.modelos.map((m) => m.nombre);
  if (actual && !nombres.includes(actual)) nombres.unshift(actual);
  sel.innerHTML = nombres.map((n) => `<option value="${esc(n)}"${n === actual ? " selected" : ""}>${esc(n)}${E.modelos.some((m) => m.nombre === n) ? "" : " (sin descargar)"}</option>`).join("");
  pintarAviso();
}

function pintarAviso() {
  const b = $("#aviso-banda");
  let html = "";
  if (E.salud && !E.salud.instalado && !E.salud.ollama) {
    html = `<span>Para trabajar hace falta Ollama, el programa que ejecuta los modelos en este ordenador.</span><button class="boton boton-principal" data-accion="instalar-ollama">Instalar Ollama</button>`;
  } else if (E.salud && !E.salud.ollama) {
    html = `<span>Ollama está instalado pero detenido. Ábrelo y vuelve a intentarlo.</span>`;
  } else if (E.salud && E.salud.ollama && !E.modelos.length) {
    html = `<span>No hay ningún modelo descargado. Elige uno para empezar.</span><button class="boton boton-principal" data-accion="abrir-modelos">Elegir modelo</button>`;
  } else if (E.proyecto && E.modelos.length && !E.modelos.some((m) => m.nombre === (E.proyecto.modelo || E.modeloDefecto))) {
    html = `<span>El modelo de este proyecto (${esc(E.proyecto.modelo)}) no está descargado.</span><button class="boton" data-accion="abrir-modelos">Gestionar modelos</button>`;
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
  if (!E.proyectos.length) { el.innerHTML = `<p class="nota" style="padding:8px">Todavía no hay proyectos.</p>`; return; }
  el.innerHTML = E.proyectos.map((p) => {
    const activo = E.proyecto && E.proyecto.id === p.id;
    const convs = activo ? (E.conversaciones[p.id] || []) : [];
    return `<div class="proyecto${activo ? " activo" : ""}">
      <button class="proyecto-cab" data-proyecto="${p.id}">${esc(p.nombre)}${p.temporal ? ' <span class="temporal">temporal</span>' : ""}</button>
      ${activo ? `<div class="conversaciones">
        <button class="conv conv-nueva" data-nueva-conv="${p.id}">Nueva conversación</button>
        ${convs.map((c) => `<button class="conv${c.id === E.conversacion ? " activa" : ""}" data-conv="${c.id}" title="${esc(c.titulo)}">${esc(c.titulo)}</button>`).join("")}
      </div>` : ""}
    </div>`;
  }).join("");
}

async function abrirProyecto(pid, conv) {
  E.proyecto = await api("GET", `/api/proyectos/${pid}`);
  E.conversaciones[pid] = await api("GET", `/api/proyectos/${pid}/conversaciones`);
  $("#titulo-proyecto").textContent = E.proyecto.nombre;
  $("#ajustes-proyecto").hidden = false;
  $("#redactor").hidden = false;
  $("#intensiva").checked = E.proyecto.perfil === "intensivo";
  await refrescarModelos();
  const convs = E.conversaciones[pid];
  E.conversacion = conv || (convs[0] && convs[0].id) || null;
  pintarLateral();
  pintarArchivos();
  await refrescarOperaciones();
  if (E.conversacion) await abrirConversacion(E.conversacion);
  else pintarVacioProyecto();
  if (!$("#panel-revision").hidden) pintarRevision();
}

async function abrirConversacion(cid) {
  E.conversacion = cid;
  const c = await api("GET", `/api/conversaciones/${cid}`);
  $("#titulo-conversacion").textContent = c.titulo || "";
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
  $("#titulo-proyecto").textContent = "Áurea Asistente Local";
  $("#titulo-conversacion").textContent = "";
  $("#redactor").hidden = true;
  $("#ajustes-proyecto").hidden = true;
  $("#hilo").innerHTML = `<div class="vacio">
    <h2>Tus expedientes, sin salir de este ordenador</h2>
    <p>Un proyecto reúne las carpetas de un asunto y sus conversaciones. Añade la carpeta del expediente y pídele a Áurea que la seudonimice: el modelo local hace varias pasadas y se comprueba a sí mismo antes de dar nada por bueno.</p>
    <button class="boton boton-principal" data-accion="nuevo-proyecto">Crear el primer proyecto</button>
  </div>`;
  $("#panel-archivos").innerHTML = `<p class="nota">Crea un proyecto para añadir carpetas y archivos.</p>`;
  $("#panel-operaciones").innerHTML = "";
  $("#panel-revision").innerHTML = "";
}

function pintarVacioProyecto() {
  const n = (E.proyecto.archivos || []).filter((a) => a.admitido).length;
  const sug = n
    ? ["Seudonimiza todos los archivos del proyecto y conserva el formato", "¿Qué archivos hay y cuáles no se pueden tratar?", "Resume el primer documento"]
    : [];
  $("#hilo").innerHTML = `<div class="vacio">
    <h2>${esc(E.proyecto.nombre)}</h2>
    <p>${n ? `${n} archivo${n === 1 ? "" : "s"} listo${n === 1 ? "" : "s"} para trabajar. Escribe qué necesitas.` : "Añade la carpeta del expediente o algunos archivos para empezar. Los originales nunca se modifican."}</p>
    ${n ? "" : `<div class="plan-acciones" style="justify-content:center"><button class="boton boton-principal" data-accion="adjuntar-carpeta">Añadir carpeta</button><button class="boton" data-accion="adjuntar-archivos">Añadir archivos</button></div>`}
    <div class="sugerencias">${sug.map((s) => `<button class="sugerencia" data-sugerencia="${esc(s)}">${esc(s)}</button>`).join("")}</div>
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
  return d;
}

function nombreHerramienta(n) {
  return { inspeccionar_carpeta: "Inventario del proyecto", inspeccionar_documento: "Ficha del documento", extraer_texto: "Lectura del documento",
    seudonimizar: "Plan de seudonimización", estado_trabajos: "Estado de los trabajos", verificar_documento: "Auditoría del documento" }[n] || n;
}

function nodoPlan(plan, mid, datos) {
  const d = document.createElement("div");
  d.className = "plan";
  const n = plan.archivos.length;
  const estado = plan.estado;   // confirmado | descartado | undefined
  if (estado) {
    d.classList.add("cerrado");
    d.innerHTML = `<h4>Seudonimización de ${n} archivo${n === 1 ? "" : "s"}</h4>
      <p class="resultado">${estado === "confirmado" ? `Confirmada (${plan.perfil === "intensivo" ? "verificación intensiva" : "verificación estándar"}). El avance está en la pestaña Operaciones.` : "Descartada."}</p>`;
    return d;
  }
  const intensivo = plan.perfil === "intensivo";
  d.innerHTML = `<h4>Seudonimizar ${n} archivo${n === 1 ? "" : "s"}</h4>
    <ul class="plan-archivos">${plan.nombres.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <div class="plan-opciones">
      <label class="opcion"><input type="radio" name="perfil-${mid}" value="estandar"${intensivo ? "" : " checked"}> <span>Verificación estándar</span></label>
      <label class="opcion"><input type="radio" name="perfil-${mid}" value="intensivo"${intensivo ? " checked" : ""}> <span>Verificación intensiva (más lenta)</span></label>
    </div>
    <p class="nota">Se crean copias en la carpeta de resultados del proyecto, separadas en «Aprobados» y «Para revisar». Los originales no se tocan.</p>
    <div class="plan-acciones">
      <button class="boton boton-principal" data-confirmar>Seudonimizar ${n} archivo${n === 1 ? "" : "s"}</button>
      <button class="boton" data-descartar>Descartar</button>
    </div>`;
  $("[data-confirmar]", d).onclick = async () => {
    const perfil = $(`input[name="perfil-${mid}"]:checked`, d).value;
    try {
      const r = await api("POST", `/api/proyectos/${E.proyecto.id}/trabajos`, { archivos: plan.archivos, perfil, conversacion: E.conversacion });
      plan.estado = "confirmado"; plan.perfil = perfil; plan.trabajo = r.id;
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
  if ($("#intensiva").checked && /seudonim|anonim/i.test(texto) && !/intensiv/i.test(texto)) texto += " (con verificación intensiva)";
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
      method: "POST", headers: { "Content-Type": "application/json", "X-Aurea-Token": E.conexion.token },
      body: JSON.stringify({ texto, modelo: $("#selector-modelo").value }),
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
          for (const p of planes) nodo.append(nodoPlan(p, ev.mensaje, datos));
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
  const p = E.proyecto;
  const el = $("#panel-archivos");
  const adm = p.archivos.filter((a) => a.admitido);
  el.innerHTML = `
    <div class="acciones-panel">
      <button class="boton" data-accion="adjuntar-carpeta">Añadir carpeta</button>
      <button class="boton" data-accion="adjuntar-archivos">Añadir archivos</button>
      ${p.carpetas.length ? `<button class="boton-texto" data-accion="actualizar-carpetas" title="Volver a leer las carpetas">Actualizar</button>` : ""}
    </div>
    ${p.carpetas.length ? `<h3>Carpetas y archivos autorizados</h3>${p.carpetas.map((c) => `<div class="carpeta"><span>${esc(c.ruta)}</span><button class="boton-texto" data-quitar-carpeta="${c.id}" title="Quitar del proyecto (no borra nada del disco)">Quitar</button></div>`).join("")}` : `<p class="nota">Los archivos que añadas se leen desde su sitio; nunca se modifican ni se mueven. También puedes arrastrarlos a la ventana.</p>`}
    ${p.archivos.length ? `<h3>${adm.length} de ${p.archivos.length} archivo${p.archivos.length === 1 ? "" : "s"} admitido${adm.length === 1 ? "" : "s"}</h3>
      ${p.archivos.map((a) => `<div class="archivo"><span class="nombre">${esc(a.rel)}</span><span class="chip ${esc(a.estado)}">${esc(ESTADOS[a.estado] || a.estado)}</span>${a.motivo ? `<span class="motivo">${esc(a.motivo)}</span>` : ""}</div>`).join("")}` : ""}
    ${p.salida_efectiva ? `<h3>Resultados</h3><div class="carpeta"><span>${esc(p.salida_efectiva)}</span></div>${p.salida_sincronizada ? `<p class="aviso-campo" style="margin:4px 0">Esta carpeta parece sincronizada con la nube.</p>` : ""}` : ""}`;
}

async function anadirRutas(rutas) {
  if (!rutas.length) return;
  try {
    await api("POST", `/api/proyectos/${E.proyecto.id}/carpetas`, { rutas });
    E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`);
    pintarArchivos();
    mostrarPestana("archivos");
    if ($("#hilo .vacio")) pintarVacioProyecto();
  } catch (e) { alerta(e.message); }
}

// ------------------------------------------------------------------ panel: operaciones

async function refrescarOperaciones() {
  if (!E.proyecto) return;
  const r = await api("GET", `/api/proyectos/${E.proyecto.id}/trabajos`);
  E.historial = r.historial;
  for (const t of r.activos) E.trabajos[t.id] = t;
  // los trabajos vivos de este proyecto, con su detalle
  const vivos = r.historial.filter((h) => ["en_cola", "procesando", "pendiente"].includes(h.estado) || E.trabajos[h.id]);
  for (const h of vivos) {
    try { E.trabajos[h.id] = await api("GET", `/api/trabajos/${h.id}`); } catch (e) { /* de una sesión anterior */ }
  }
  pintarOperaciones();
  const hayActivos = Object.values(E.trabajos).some((t) => t && ["pendiente", "procesando"].includes(t.estado));
  clearTimeout(E.sondeo);
  if (hayActivos) E.sondeo = setTimeout(async () => {
    const antes = Object.values(E.trabajos).filter((t) => t && ["pendiente", "procesando"].includes(t.estado)).length;
    await refrescarOperaciones();
    const despues = Object.values(E.trabajos).filter((t) => t && ["pendiente", "procesando"].includes(t.estado)).length;
    if (despues < antes) {            // algún trabajo ha terminado
      E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`);
      pintarArchivos();
      if (!$("#panel-revision").hidden) pintarRevision();
    }
  }, 2000);
}

function pistaDoc(d) {
  return (d.pasadas || []).map((p) => {
    if (p.tipo === "deteccion") return `<span class="paso${p.nuevos ? " nuevos" : ""}" title="Detección ${p.n}: ${p.nuevos} dato(s) nuevo(s)">D${p.n}</span>`;
    const cls = p.restos || p.incidencias_graves ? "restos" : p.nuevos ? "nuevos" : "limpio";
    return `<span class="paso ${cls}" title="Verificación ${p.ciclo} (método ${p.metodo}): ${p.nuevos} nuevo(s), ${p.restos} resto(s), ${p.incidencias_graves} incidencia(s) grave(s)">V${p.ciclo}</span>`;
  }).join("");
}

function pintarOperaciones() {
  const el = $("#panel-operaciones");
  const vivos = Object.values(E.trabajos).filter(Boolean).filter((t) => (E.historial || []).some((h) => h.id === t.id));
  const terminados = (E.historial || []).filter((h) => !vivos.some((v) => v.id === h.id));
  if (!vivos.length && !terminados.length) {
    el.innerHTML = `<p class="nota">Aquí verás cada seudonimización: el avance por archivo, cada pasada de detección (D) y de verificación (V), y dónde quedan las copias.</p>`;
    return;
  }
  el.innerHTML = vivos.sort((a, b) => b.id.localeCompare(a.id)).map((t) => {
    const activo = ["pendiente", "procesando"].includes(t.estado);
    const cuenta = (k) => t.docs.filter((d) => d.estado === k).length;
    return `<div class="trabajo">
      <div class="trabajo-cab"><b>${activo ? "En curso" : t.estado === "terminado" ? "Terminado" : esc(t.estado)} · ${t.perfil === "intensivo" ? "verificación intensiva" : "verificación estándar"}</b>
        ${activo ? `<button class="boton-texto peligro" data-cancelar="${t.id}">Cancelar</button>` : t.destino ? `<button class="boton-texto" data-abrir="${esc(t.destino)}">Abrir carpeta</button>` : ""}</div>
      ${activo ? `<div class="progreso"><i style="width:${Math.round(t.progreso * 100)}%"></i></div><div class="trabajo-msg">${esc(t.mensaje)}</div>` :
        `<p class="nota">${cuenta("sin_hallazgos")} sin hallazgos · ${cuenta("revision")} para revisar · ${cuenta("error")} con error${cuenta("cancelado") ? ` · ${cuenta("cancelado")} cancelados` : ""}</p>`}
      ${t.docs.map((d) => `<div class="doc">
        <div class="doc-cab"><span>${esc(d.rel)}</span><span class="chip ${esc(d.estado)}">${esc(ESTADOS[d.estado] || d.estado)}</span></div>
        <div class="pista">${pistaDoc(d)}</div>
        ${d.motivos && d.motivos.length ? `<ul class="doc-motivos">${d.motivos.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}
      </div>`).join("")}
      ${!activo ? `<p class="leyenda">D = detección · V = verificación. Dorado: encontró datos nuevos; verde: limpia; ámbar: quedan restos o incidencias.</p>` : ""}
    </div>`;
  }).join("") + (terminados.length ? `<h3>Anteriores</h3>` + terminados.map((h) => `<div class="archivo"><span class="nombre">${esc(new Date(h.creado * 1000).toLocaleString("es-ES"))} · ${h.perfil === "intensivo" ? "intensiva" : "estándar"}${h.resumen ? ` · ${h.resumen.recuento.sin_hallazgos} sin hallazgos, ${h.resumen.recuento.revision} para revisar, ${h.resumen.recuento.error} con error` : ""}</span>${h.destino ? `<button class="boton-texto" data-abrir="${esc(h.destino)}">Abrir</button>` : `<span class="chip">${esc(h.estado)}</span>`}</div>`).join("") : "");
}

// ------------------------------------------------------------------ panel: revisión

async function pintarRevision() {
  const el = $("#panel-revision");
  if (!E.proyecto) return;
  let r;
  try { r = await api("GET", `/api/proyectos/${E.proyecto.id}/registro`); } catch (e) { el.innerHTML = `<p class="nota">${esc(e.message)}</p>`; return; }
  const grupos = {};
  for (const e of r.entidades) (grupos[e.tipo] = grupos[e.tipo] || []).push(e);
  const tipos = Object.keys(r.etiquetas);
  el.innerHTML = `
    <p class="nota">Datos que el proyecto seudonimiza, con su marcador. Si algo no es un dato personal, descártalo: no volverá a proponerse. Si falta algo, añádelo. Después, regenera las copias.</p>
    <form class="form-anadir" id="form-anadir">
      <input name="texto" placeholder="Dato que se ha escapado" required>
      <button class="boton">Añadir</button>
      <select name="tipo">${tipos.map((t) => `<option value="${t}">${esc(r.etiquetas[t])}</option>`).join("")}</select>
    </form>
    <div class="acciones-panel">
      <button class="boton boton-principal" data-accion="regenerar" ${r.entidades.length ? "" : "disabled"}>Regenerar copias</button>
      ${E.proyecto.tabla === "cifrada" && r.entidades.length ? `<button class="boton-texto" data-accion="exportar-tabla">Exportar tabla…</button>` : ""}
    </div>
    ${r.entidades.length ? "" : `<p class="nota">Todavía no hay datos detectados en este proyecto.</p>`}
    ${Object.entries(grupos).map(([tipo, ents]) => `<div class="grupo-tipo"><h3>${esc(r.etiquetas[tipo] || tipo)} · ${ents.filter((e) => e.activo).length}</h3>
      ${ents.map((e) => `<div class="entidad${e.activo ? "" : " inactiva"}">
        <span class="tachon${e.activo ? "" : " descartado"}">${esc(e.marcador)}</span>
        <span class="formas">${e.formas.map(esc).join(" · ")}</span>
        ${e.activo ? `<button class="boton-texto" data-descartar-ent="${e.id}" title="No es un dato personal">Descartar</button>` : `<button class="boton-texto" data-reactivar-ent="${e.id}">Recuperar</button>`}
        <span class="meta">${e.docs.length} documento${e.docs.length === 1 ? "" : "s"} · ${esc(e.origenes.join(", "))}${e.ambigua ? " · ambigua: revisa si es la misma persona" : ""}</span>
      </div>`).join("")}</div>`).join("")}`;
  $("#form-anadir").onsubmit = async (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    try { await api("POST", `/api/proyectos/${E.proyecto.id}/registro`, { texto: f.get("texto"), tipo: f.get("tipo") }); pintarRevision(); } catch (e) { alerta(e.message); }
  };
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

function abrirDialogoProyecto(editar) {
  const d = $("#dlg-proyecto");
  const f = $("#form-proyecto");
  d.className = "dialogo " + (editar ? "edicion" : "alta");
  $("#dlg-proyecto-titulo").textContent = editar ? "Ajustes del proyecto" : "Nuevo proyecto";
  $("#guardar-proyecto").textContent = editar ? "Guardar" : "Crear proyecto";
  const sel = $("#proyecto-modelo");
  const nombres = E.modelos.map((m) => m.nombre);
  const actual = editar ? E.proyecto.modelo : E.modeloDefecto;
  if (actual && !nombres.includes(actual)) nombres.unshift(actual);
  sel.innerHTML = nombres.map((n) => `<option${n === actual ? " selected" : ""}>${esc(n)}</option>`).join("");
  const p = editar ? E.proyecto : { nombre: "", perfil: "estandar", tabla: "cifrada", salida: "", instrucciones: "", logos: 1 };
  f.nombre.value = p.nombre;
  f.perfil.value = p.perfil;
  f.tabla.value = p.tabla;
  f.salida.value = editar ? (p.salida || "") : "";
  f.salida.placeholder = editar ? p.salida_efectiva : "";
  f.instrucciones.value = p.instrucciones || "";
  f.logos.checked = !!p.logos;
  f.temporal.checked = false;
  $("#aviso-salida").hidden = !(editar && p.salida_sincronizada);
  d.showModal();
  d.onclose = async () => {
    if (d.returnValue !== "aceptar") return;
    const datos = { nombre: f.nombre.value.trim(), modelo: sel.value, perfil: f.perfil.value, tabla: f.tabla.value };
    try {
      if (editar) {
        if (E.proyecto.tabla === "cifrada" && datos.tabla === "sin_tabla") {
          const ok = await confirmar("Dejar de guardar la tabla", "Se destruirá la tabla de correspondencias cifrada de este proyecto. No se podrá deshacer la seudonimización de las copias ya generadas.", "Destruir la tabla");
          if (!ok) return;
        }
        Object.assign(datos, { salida: f.salida.value || null, instrucciones: f.instrucciones.value, logos: f.logos.checked ? 1 : 0 });
        await api("PATCH", `/api/proyectos/${E.proyecto.id}`, datos);
        await refrescarProyectos();
        await abrirProyecto(E.proyecto.id, E.conversacion);
      } else {
        datos.temporal = f.temporal.checked;
        const nuevo = await api("POST", "/api/proyectos", datos);
        await refrescarProyectos();
        await abrirProyecto(nuevo.id);
      }
    } catch (e) { alerta(e.message); }
  };
}

async function abrirModelos() {
  await refrescarModelos();
  pintarModelos();
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

function mostrarPestana(n) {
  $$(".pestana").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.pestana === n)));
  for (const k of ["archivos", "operaciones", "revision"]) $(`#panel-${k}`).hidden = k !== n;
  if (n === "revision") pintarRevision();
  if (n === "operaciones") refrescarOperaciones();
}

// ------------------------------------------------------------------ eventos

function enlazar() {
  $("#nuevo-proyecto").onclick = () => abrirDialogoProyecto(false);
  $("#ajustes-proyecto").onclick = () => abrirDialogoProyecto(true);
  $("#abrir-modelos").onclick = abrirModelos;
  $("#alternar-panel").onclick = () => {
    const app = $("#app");
    app.classList.toggle("sin-panel");
    $("#alternar-panel").setAttribute("aria-expanded", String(!app.classList.contains("sin-panel")));
  };
  $$(".pestana").forEach((b) => (b.onclick = () => mostrarPestana(b.dataset.pestana)));
  $("#selector-modelo").onchange = async (ev) => {
    if (E.proyecto) { await api("PATCH", `/api/proyectos/${E.proyecto.id}`, { modelo: ev.target.value }); E.proyecto.modelo = ev.target.value; pintarAviso(); }
  };
  $("#intensiva").onchange = async (ev) => {
    if (E.proyecto) await api("PATCH", `/api/proyectos/${E.proyecto.id}`, { perfil: ev.target.checked ? "intensivo" : "estandar" });
  };
  const entrada = $("#entrada");
  entrada.addEventListener("input", () => { entrada.style.height = "auto"; entrada.style.height = Math.min(entrada.scrollHeight, 240) + "px"; });
  entrada.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); $("#redactor").requestSubmit(); }
  });
  $("#redactor").onsubmit = (ev) => { ev.preventDefault(); const t = entrada.value; entrada.value = ""; entrada.style.height = "auto"; enviar(t); };
  $("#adjuntar-archivos").onclick = async () => anadirRutas(await elegir("archivos"));
  $("#adjuntar-carpeta").onclick = async () => anadirRutas(await elegir("carpeta"));
  $("#elegir-salida").onclick = async () => {
    const r = await elegir("carpeta_salida");
    if (r[0]) $("#form-proyecto").salida.value = r[0];
  };
  $("#borrar-proyecto").onclick = async () => {
    const ok = await confirmar("Borrar el proyecto", `Se borrarán sus conversaciones, su registro de entidades y la tabla de correspondencias cifrada (y su clave). Tus archivos originales y las copias ya exportadas no se tocan.`, "Borrar proyecto");
    if (!ok) return;
    $("#dlg-proyecto").close("cancelar");
    await api("DELETE", `/api/proyectos/${E.proyecto.id}`);
    E.proyecto = null; E.conversacion = null;
    await refrescarProyectos();
    if (E.proyectos.length) await abrirProyecto(E.proyectos[0].id); else pintarBienvenida();
  };
  $("#descargar-libre").onclick = async () => {
    const n = $("#modelo-libre").value.trim();
    if (!n) return;
    try { await api("POST", "/api/modelos/descargar", { nombre: n }); $("#modelo-libre").value = ""; await refrescarModelos(); pintarModelos(); } catch (e) { alerta(e.message); }
  };

  document.addEventListener("click", async (ev) => {
    const b = ev.target.closest("button, [data-proyecto]");
    if (!b) return;
    const d = b.dataset;
    try {
      if (d.proyecto) await abrirProyecto(+d.proyecto);
      else if (d.conv) await abrirConversacion(+d.conv);
      else if (d.nuevaConv) await nuevaConversacion();
      else if (d.sugerencia) enviar(d.sugerencia);
      else if (d.quitarCarpeta) { await api("DELETE", `/api/proyectos/${E.proyecto.id}/carpetas/${d.quitarCarpeta}`); E.proyecto = await api("GET", `/api/proyectos/${E.proyecto.id}`); pintarArchivos(); }
      else if (d.cancelar) { if (await confirmar("Cancelar la seudonimización", "Los documentos ya terminados se exportan; el resto queda cancelado.", "Cancelar el trabajo")) { await api("POST", `/api/trabajos/${d.cancelar}/cancelar`); refrescarOperaciones(); } }
      else if (d.abrir) await api("POST", "/api/abrir", { ruta: d.abrir });
      else if (d.descartarEnt) { await api("POST", `/api/proyectos/${E.proyecto.id}/registro/${d.descartarEnt}/descartar`); pintarRevision(); }
      else if (d.reactivarEnt) { await api("POST", `/api/proyectos/${E.proyecto.id}/registro/${d.reactivarEnt}/reactivar`); pintarRevision(); }
      else if (d.descargar) { await api("POST", "/api/modelos/descargar", { nombre: d.descargar }); await refrescarModelos(); pintarModelos(); }
      else if (d.defecto) { await api("POST", "/api/modelos/defecto", { nombre: d.defecto }); await refrescarModelos(); pintarModelos(); }
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
  else if (a === "regenerar") {
    const ultimos = (E.proyecto.archivos || []).filter((x) => ["sin_hallazgos", "revision"].includes(x.estado));
    if (!ultimos.length) { alerta("Todavía no hay copias generadas en este proyecto.", "Nada que regenerar"); return; }
    const ok = await confirmar("Regenerar copias", `Se vuelven a generar y verificar ${ultimos.length} copia${ultimos.length === 1 ? "" : "s"} con los datos revisados, en una carpeta de resultados nueva, con verificación ${$("#intensiva").checked ? "intensiva" : "estándar"}. No se repite la detección.`, "Regenerar");
    if (!ok) return;
    await api("POST", `/api/proyectos/${E.proyecto.id}/trabajos`, { archivos: ultimos.map((x) => x.id), solo_ciclos: true,
      perfil: $("#intensiva").checked ? "intensivo" : "estandar", conversacion: E.conversacion });
    mostrarPestana("operaciones");
  }
  else if (a === "exportar-tabla") {
    const ok = await confirmar("Exportar la tabla de correspondencias", "La tabla contiene los datos originales y permite deshacer la seudonimización. Guárdala en el expediente, fuera de carpetas sincronizadas, y no la subas nunca a ninguna IA.", "Elegir dónde guardarla");
    if (!ok) return;
    const r = await elegir("guardar");
    if (!r[0]) return;
    const res = await api("POST", `/api/proyectos/${E.proyecto.id}/tabla/exportar`, { ruta: r[0] });
    if (res.sincronizada) alerta("La tabla se ha guardado en una carpeta que parece sincronizada con la nube. Muévela a una carpeta local.", "Tabla exportada");
  }
}

iniciar();
