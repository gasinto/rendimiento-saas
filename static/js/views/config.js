// ── JC-Sistema: Vista Configuraci├│n ───────────────────────────

/**
 * Carga la configuraci├│n completa: valor por punto, puntajes,
 * tipos de equipo y empresas.
 */
async function cargarConfiguracion() {
  await Promise.all([
    cargarValorPuntoConfig(),
    cargarPuntajesConfig(),
    cargarTiposEquipoConfig(),
    cargarEmpresasConfig(),
  ]);
}
window.cargarConfiguracion = cargarConfiguracion;

// ── Valor por punto ────────────────────────────────────────────

/** Carga el valor actual del punto en el input de configuraci├│n. */
async function cargarValorPuntoConfig() {
  try {
    const r = await apiFetch("/api/scores/");
    const d = await r.json();
    const inp = document.getElementById("configValorPunto");
    if (inp) inp.value = d.valor_punto || 2000;
  } catch (e) { /* ignore */ }
}

/**
 * Guarda el nuevo valor por punto.
 * Llamado desde onclick en viewConfig.
 */
window.guardarValorPunto = async () => {
  const inp = document.getElementById("configValorPunto");
  const valor = parseFloat(inp?.value);
  if (isNaN(valor) || valor <= 0) { alert("Valor inv├ílido"); return; }
  await apiFetch("/api/puntajes", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _action: "actualizar-valor", valor })
  });
  mostrarMsg("✅ Valor por punto actualizado a $" + valor, "ok");
};

// ── Puntajes por tipo ──────────────────────────────────────────

/** Carga y renderiza la lista de puntajes por tipo de equipo. */
async function cargarPuntajesConfig() {
  try {
    const r = await apiFetch("/api/puntajes");
    const d = await r.json();
    const list = document.getElementById("configPuntajesList");
    const puntajes = d.puntajes || [];
    if (!puntajes.length) {
      list.innerHTML = '<div style="color:var(--muted);font-size:13px">Sin puntajes registrados.</div>';
      return;
    }
    list.innerHTML = '<table style="width:100%"><thead><tr><th>Tipo</th><th>Pts</th><th></th></tr></thead><tbody>' +
      puntajes.map(p =>
        '<tr><td>' + esc(p.tipo) + '</td>' +
        '<td><input type="number" min="1" value="' + p.puntaje + '" ' +
        'onchange="actualizarPuntaje(\'' + escAttr(p.tipo) + '\',this.value)" ' +
        'style="width:60px;padding:3px 6px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);font-size:13px"></td>' +
        '<td style="text-align:right"><button class="btn-delete" onclick="eliminarPuntaje(\'' + escAttr(p.tipo) + '\')">✕</button></td></tr>'
      ).join("") +
      '</tbody></table>';
  } catch (e) { /* ignore */ }
}

/**
 * Agrega un nuevo puntaje por tipo.
 * Llamado desde onclick en viewConfig.
 */
window.agregarPuntaje = async () => {
  const tipoInp = document.getElementById("configPuntajeTipoInput");
  const valInp = document.getElementById("configPuntajeValorInput");
  const tipo = tipoInp?.value.trim().toUpperCase();
  const puntaje = parseFloat(valInp?.value);
  if (!tipo) { alert("Falta el tipo"); return; }
  if (isNaN(puntaje) || puntaje <= 0) { alert("Puntaje inv├ílido"); return; }
  await apiFetch("/api/puntajes", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo, puntaje })
  });
  tipoInp.value = ""; valInp.value = "";
  cargarPuntajesConfig();
};

/**
 * Elimina un puntaje por tipo.
 * Llamado desde onclick en la tabla de puntajes.
 * @param {string} tipo - Tipo de equipo a eliminar
 */
window.eliminarPuntaje = async (tipo) => {
  if (!confirm("┐Eliminar puntaje para ô¨" + tipo + "¨?")) return;
  await apiFetch("/api/puntajes", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _method: "DELETE", tipo })
  });
  cargarPuntajesConfig();
};

/**
 * Actualiza el puntaje de un tipo existente.
 * Llamado desde onchange en el input de puntaje.
 * @param {string} tipo - Tipo de equipo
 * @param {string|number} valor - Nuevo valor del puntaje
 */
window.actualizarPuntaje = async (tipo, valor) => {
  const puntaje = parseFloat(valor);
  if (isNaN(puntaje) || puntaje <= 0) { cargarPuntajesConfig(); return; }
  await apiFetch("/api/puntajes", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _action: "actualizar", tipo, puntaje })
  });
};

// ── Tipos de equipo ────────────────────────────────────────────

/** Carga y renderiza la lista de tipos de equipo. */
async function cargarTiposEquipoConfig() {
  try {
    const r = await apiFetch("/api/tipos-equipo");
    const d = await r.json();
    const list = document.getElementById("configTiposEquipoList");
    const tipos = d.tipos || [];
    if (!tipos.length) {
      list.innerHTML = '<div style="color:var(--muted);font-size:13px">Sin tipos de equipo registrados.</div>';
      return;
    }
    list.innerHTML = '<table style="width:100%"><thead><tr><th>Nombre</th><th></th></tr></thead><tbody>' +
      tipos.map(t => '<tr><td>' + esc(t.nombre) + '</td>' +
        '<td style="text-align:right"><button class="btn-delete" onclick="eliminarTipoEquipo(' + t.id + ')">✕</button></td></tr>'
      ).join("") +
      '</tbody></table>';
  } catch (e) { /* ignore */ }
}

/**
 * Agrega un nuevo tipo de equipo.
 * Llamado desde onclick en viewConfig.
 */
window.agregarTipoEquipo = async () => {
  const input = document.getElementById("configTipoEquipoInput");
  const nombre = input?.value.trim();
  if (!nombre) { alert("Falta el nombre del tipo"); return; }
  await apiFetch("/api/tipos-equipo", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nombre })
  });
  input.value = "";
  cargarConfiguracion();
};

/**
 * Elimina un tipo de equipo por ID.
 * @param {number} id - ID del tipo de equipo
 */
window.eliminarTipoEquipo = async (id) => {
  if (!confirm("┐Eliminar este tipo de equipo?")) return;
  await apiFetch("/api/tipos-equipo", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _method: "DELETE", id })
  });
  cargarConfiguracion();
};

// ── Empresas ───────────────────────────────────────────────────

/** Carga y renderiza la lista de empresas. */
async function cargarEmpresasConfig() {
  try {
    const r = await apiFetch("/api/empresas");
    const d = await r.json();
    const list = document.getElementById("configEmpresasList");
    const emps = d.empresas || [];
    if (!emps.length) {
      list.innerHTML = '<div style="color:var(--muted);font-size:13px">Sin empresas registradas.</div>';
      return;
    }
    list.innerHTML = '<table style="width:100%"><thead><tr><th>Nombre</th><th></th></tr></thead><tbody>' +
      emps.map(e => '<tr><td>' + esc(e.nombre) + '</td>' +
        '<td style="text-align:right"><button class="btn-delete" onclick="eliminarEmpresa(' + e.id + ',\'' + escAttr(e.nombre) + '\')">✕</button></td></tr>'
      ).join("") +
      '</tbody></table>';
  } catch (e) { /* ignore */ }
}

/**
 * Agrega una nueva empresa.
 * Llamado desde onclick en viewConfig.
 */
window.agregarEmpresa = async () => {
  const input = document.getElementById("configEmpresaInput");
  const nombre = input?.value.trim();
  if (!nombre) { alert("Falta el nombre de la empresa"); return; }
  const r = await apiFetch("/api/empresas", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nombre })
  });
  const d = await r.json();
  if (!d.ok) { alert(d.error || "Error al agregar"); return; }
  input.value = "";
  cargarEmpresasConfig();
};

/**
 * Elimina una empresa por ID.
 * @param {number} id - ID de la empresa
 * @param {string} nombre - Nombre de la empresa (para confirmaci├│n)
 */
window.eliminarEmpresa = async (id, nombre) => {
  if (!confirm("┐Eliminar empresa ô¨" + nombre + "¨?")) return;
  const r = await apiFetch("/api/empresas", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _method: "DELETE", id })
  });
  const d = await r.json();
  if (!d.ok) { alert(d.error || "Error al eliminar"); return; }
  cargarEmpresasConfig();
};
