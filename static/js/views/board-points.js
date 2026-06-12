// ── JC-Sistema: Vista Puntos de Placa (Board-Centric) ──────────

/** @type {Array} Cache de placas cargadas */
let _placasCache = [];

/**
 * Carga y renderiza la vista de Placas con puntos de medición y notas.
 * Llamado desde cambiarVista('puntos-placa') y desde oninput de medicionesPlacaQ.
 */
window.cargarMedicionesPlaca = async function() {
  const q = (document.getElementById("medicionesPlacaQ")?.value || "").trim();
  const out = document.getElementById("medicionesPlacaResults");
  const stat = document.getElementById("medicionesPlacaStat");
  try {
    const [rPlacas, rMeds, rBloques] = await Promise.all([
      apiFetch("/api/placas" + (q ? "?q=" + encodeURIComponent(q) : "")),
      apiFetch("/api/mediciones-placa" + (q ? "?q=" + encodeURIComponent(q) : "")),
      apiFetch("/api/bloques")
    ]);
    const dPlacas = await rPlacas.json();
    const dMeds = await rMeds.json();
    const dBloques = await rBloques.json();
    const placas = dPlacas.placas || [];
    const meds = dMeds.mediciones || [];
    const allBloques = dBloques.bloques || [];
    _placasCache = placas;

    const medsByPlaca = new Map();
    meds.forEach(m => {
      const key = m.modelo_placa || "";
      if (!medsByPlaca.has(key)) medsByPlaca.set(key, []);
      medsByPlaca.get(key).push(m);
    });

    stat.textContent = placas.length + " placa" + (placas.length === 1 ? "" : "s") +
      " · " + meds.length + " punto" + (meds.length === 1 ? "" : "s");

    if (!placas.length) {
      out.innerHTML = '<div class="empty" style="padding:2rem;color:var(--muted)">' +
        (q ? 'Sin resultados para <b>' + esc(q) + '</b>' : 'Sin placas registradas aún.') +
        '</div>';
      return;
    }

    const notesByPlaca = new Map();
    for (const placa of placas) {
      try {
        const rn = await apiFetch("/api/notas-placa?modelo_placa=" + encodeURIComponent(placa.modelo_placa));
        const dn = await rn.json();
        notesByPlaca.set(placa.modelo_placa, dn.notas || []);
      } catch { notesByPlaca.set(placa.modelo_placa, []); }
    }

    if (!window._bloquesByModel) window._bloquesByModel = {};
    placas.forEach(p => {
      if (!_bloquesByModel[p.modelo_placa]) _bloquesByModel[p.modelo_placa] = new Set();
    });
    meds.forEach(m => {
      if (m.bloque && _bloquesByModel[m.modelo_placa]) _bloquesByModel[m.modelo_placa].add(m.bloque);
    });
    for (const [modelo, notas] of notesByPlaca) {
      if (_bloquesByModel[modelo]) notas.forEach(n => { if (n.bloque) _bloquesByModel[modelo].add(n.bloque); });
    }

    let html = "";
    for (const placa of placas) {
      const modelo = placa.modelo_placa || "SIN MODELO";
      const tipoEquipo = placa.tipo_equipo_nombre || "";
      const pts = medsByPlaca.get(modelo) || [];
      const notas = notesByPlaca.get(modelo) || [];

      html += '<div class="card" style="margin-bottom:14px;border-color:var(--accent)">' +
        '<div class="chead" style="padding:8px 12px;background:var(--hbg)">' +
        '<div>' +
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
        '<span style="font-family:\'Courier New\',monospace;font-size:15px;font-weight:700;color:var(--accent)">' + esc(modelo) + '</span>' +
        (tipoEquipo ? '<span style="font-size:11px;padding:2px 10px;border-radius:999px;background:var(--okbg);color:var(--success)">' + esc(tipoEquipo) + '</span>' : '') +
        '<span style="font-size:11px;color:var(--text3)">' + pts.length + ' punto' + (pts.length === 1 ? '' : 's') + '</span>' +
        '</div></div>' +
        '<div style="display:flex;gap:4px;align-items:center">' +
        '<button class="tbtn" style="font-size:11px;padding:3px 8px;font-weight:700;color:var(--accent)" onclick="abrirAddBloque(\'' + escAttr(modelo) + '\')">+ Bloque</button>' +
        '<button class="tbtn" style="font-size:11px;padding:3px 8px" onclick="abrirAddPuntoPlaca(\'' + escAttr(modelo) + '\')">+ Punto</button>' +
        '<button class="tbtn" style="font-size:11px;padding:3px 8px" onclick="abrirAddNotaPlaca(\'' + escAttr(modelo) + '\')">+ Nota</button>' +
        '<button class="btn-delete" onclick="abrirEditarPlaca(' + placa.id + ')" title="Editar placa">✏️</button>' +
        '<button class="btn-delete" onclick="eliminarPlaca(' + placa.id + ')">✕</button>' +
        '</div></div>' +
        (pts.length ? '<div class="checklist-bar" style="padding:4px 12px 6px">' +
          '<span style="white-space:nowrap">☐ <span id="checklistTxt_' + escAttr(modelo) + '">0/' + pts.length + ' (0%)</span></span>' +
          '<div class="bar"><div class="fill" id="checklistBar_' + escAttr(modelo) + '" style="width:0%"></div></div>' +
          '<button class="tbtn" style="font-size:10px;padding:1px 6px" onclick="resetChecklist(\'' + escAttr(modelo) + '\')">↻ Reset</button>' +
          '</div>' : '');

      const bloqueSet = new Set();
      pts.forEach(x => { if (x.bloque) bloqueSet.add(x.bloque); });
      notas.forEach(n => { if (n.bloque) bloqueSet.add(n.bloque); });
      if (window._bloquesByModel && _bloquesByModel[modelo]) {
        _bloquesByModel[modelo].forEach(b => bloqueSet.add(b));
      }
      const boardBloques = allBloques.filter(b => b.modelo_placa === modelo).sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
      const orderedNames = boardBloques.map(b => b.nombre);
      const extra = [...bloqueSet].filter(b => !orderedNames.includes(b)).sort();
      const bloques = [...orderedNames, ...extra];

      if (bloques.length) {
        bloques.forEach(b => {
          const bMeds = pts.filter(x => x.bloque === b).sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || (a.punto_medicion || "").localeCompare(b.punto_medicion || ""));
          const bNotes = notas.filter(n => n.bloque === b).sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
          html += '<div class="bloque-subcard">' +
            '<div class="bloque-header">' +
            '<span>▣ ' + esc(b) + '</span>' +
            '<span style="display:flex;align-items:center;gap:6px">' +
            '<span class="bloque-counts">' + bMeds.length + ' punto' + (bMeds.length !== 1 ? 's' : '') +
            (bNotes.length ? ' · ' + bNotes.length + ' nota' + (bNotes.length !== 1 ? 's' : '') : '') + '</span>' +
            '<button class="btn-delete" style="font-size:10px;margin-right:2px" onclick="reordenarBloque(\'' + escAttr(modelo) + '\',\'' + escAttr(b) + '\',\'up\')">↑</button>' +
            '<button class="btn-delete" style="font-size:10px;margin-right:2px" onclick="reordenarBloque(\'' + escAttr(modelo) + '\',\'' + escAttr(b) + '\',\'down\')">↓</button>' +
            '<button class="btn-delete" style="font-size:10px" onclick="editarBloque(\'' + escAttr(modelo) + '\',\'' + escAttr(b) + '\')">✏️</button>' +
            '<button class="btn-delete" style="font-size:10px" onclick="eliminarBloque(\'' + escAttr(modelo) + '\',\'' + escAttr(b) + '\')">✕</button>' +
            '</span>' +
            '</div>' +
            window._renderMerged(bMeds, bNotes) +
            (!bMeds.length && !bNotes.length ? '<div style="padding:10px;text-align:center;color:var(--muted);font-size:12px">Sin puntos todavía. Usá <b>+ Punto</b> para agregar.</div>' : '') +
            '</div>';
        });
      }

      const sueltosMeds = pts.filter(x => !x.bloque).sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || (a.punto_medicion || "").localeCompare(b.punto_medicion || ""));
      const sueltosNotes = notas.filter(n => !n.bloque).sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
      if (sueltosMeds.length || sueltosNotes.length) {
        html += '<div class="bloque-subcard">' +
          '<div class="bloque-header" style="background:var(--hbg);color:var(--text3)">' +
          '<span>— Sin bloque</span>' +
          '<span class="bloque-counts">' + sueltosMeds.length + ' punto' + (sueltosMeds.length !== 1 ? 's' : '') +
          (sueltosNotes.length ? ' · ' + sueltosNotes.length + ' nota' + (sueltosNotes.length !== 1 ? 's' : '') : '') + '</span>' +
          '</div>' +
          window._renderMerged(sueltosMeds, sueltosNotes) +
          '</div>';
      } else if (!pts.length && !notas.length) {
        html += '<div style="padding:14px;text-align:center;color:var(--muted);font-size:12px">Sin puntos de medición ni notas. Usá <b>+ Bloque</b> o <b>+ Punto</b> para empezar.</div>';
      }

      html += '</div>';
    }
    out.innerHTML = html;
    placas.forEach(p => actualizarBarraChecklist(p.modelo_placa));
  } catch (e) {
    out.innerHTML = '<div class="msg err show">Error al cargar placas y mediciones</div>';
  }
};

// ── Helpers de render para bloques ──────────────────────

/**
 * Renderiza tabla de puntos de medición con checklist.
 */
window._renderPtsTable = function(items, modelo) {
  if (!items.length) return '';
  let t = '<table style="margin:0;width:100%"><thead><tr>' +
    '<th style="width:30px">☐</th><th>Punto</th><th>Nombre</th><th>Valor esperado</th><th>Categoría</th><th>IC ref.</th><th>Notas</th><th></th>' +
    '</tr></thead><tbody>';
  items.forEach(x => {
    const checked = x.checked ? " checked" : "";
    t += '<tr class="' + (x.checked ? 'med-checked' : '') + '">' +
      '<td><input type="checkbox" class="med-checkbox" data-modelo="' + escAttr(modelo || x.modelo_placa) + '" data-punto="' + escAttr(x.punto_medicion) + '" data-id="' + x.id + '"' + checked + ' onchange="onCheckMedicion(this)"></td>' +
      '<td style="font-family:\'Courier New\',monospace;font-weight:700">' + esc(x.punto_medicion) + '</td>' +
      '<td>' + esc(x.nombre) + '</td>' +
      '<td style="font-family:\'Courier New\',monospace;color:var(--accent);font-weight:600">' + esc(x.valor_esperado) + '</td>' +
      '<td style="font-size:12px;color:var(--text3)">' + esc(x.categoria) + '</td>' +
      '<td style="font-size:12px;color:var(--text3)">' + esc(x.ic_referencia) + '</td>' +
      '<td style="font-size:12px;color:var(--text3);max-width:120px;overflow:hidden;text-overflow:ellipsis">' + esc(x.notas) + '</td>' +
      '<td>' +
      '<button class="btn-delete" style="font-size:10px;margin-right:2px" onclick="reordenarMedicion(' + x.id + ',\'up\')">↑</button>' +
      '<button class="btn-delete" style="font-size:10px;margin-right:2px" onclick="reordenarMedicion(' + x.id + ',\'down\')">↓</button>' +
      '<button class="btn-delete" style="margin-right:4px;font-size:11px" onclick="editarMedicionPlaca(' + x.id + ')">✏️</button>' +
      '<button class="btn-delete" onclick="eliminarMedicionPlaca(' + x.id + ')">✕</button>' +
      '</td></tr>';
  });
  t += '</tbody></table>';
  return t;
};

/**
 * Renderiza puntos y notas intercalados por sort_order.
 */
window._renderMerged = function(meds, notas) {
  if (!meds.length && !notas.length) return '';
  const all = [
    ...meds.map(m => ({ ...m, _t: 'med' })),
    ...notas.map(n => ({ ...n, _t: 'nota' }))
  ].sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
  let h = '<table style="margin:0;width:100%"><thead><tr>' +
    '<th style="width:30px">☐</th><th>Punto</th><th>Nombre</th><th>Valor esperado</th><th>Categoría</th><th>IC ref.</th><th>Notas</th><th></th>' +
    '</tr></thead><tbody>';
  all.forEach(x => {
    if (x._t === 'med') {
      const checked = x.checked ? " checked" : "";
      h += '<tr class="' + (x.checked ? 'med-checked' : '') + '">' +
        '<td><input type="checkbox" class="med-checkbox" data-modelo="' + escAttr(x.modelo_placa) + '" data-punto="' + escAttr(x.punto_medicion) + '" data-id="' + x.id + '"' + checked + ' onchange="onCheckMedicion(this)"></td>' +
        '<td style="font-family:\'Courier New\',monospace;font-weight:700">' + esc(x.punto_medicion) + '</td>' +
        '<td>' + esc(x.nombre) + '</td>' +
        '<td style="font-family:\'Courier New\',monospace;color:var(--accent);font-weight:600">' + esc(x.valor_esperado) + '</td>' +
        '<td style="font-size:12px;color:var(--text3)">' + esc(x.categoria) + '</td>' +
        '<td style="font-size:12px;color:var(--text3)">' + esc(x.ic_referencia) + '</td>' +
        '<td style="font-size:12px;color:var(--text3);max-width:120px;overflow:hidden;text-overflow:ellipsis">' + esc(x.notas) + '</td>' +
        '<td>' +
        '<button class="btn-delete" style="font-size:10px;margin-right:2px" onclick="reordenarMedicion(' + x.id + ',\'up\')">↑</button>' +
        '<button class="btn-delete" style="font-size:10px;margin-right:2px" onclick="reordenarMedicion(' + x.id + ',\'down\')">↓</button>' +
        '<button class="btn-delete" style="margin-right:4px;font-size:11px" onclick="editarMedicionPlaca(' + x.id + ')">✏️</button>' +
        '<button class="btn-delete" onclick="eliminarMedicionPlaca(' + x.id + ')">✕</button>' +
        '</td></tr>';
    } else {
      h += '<tr class="nota-interleaved" style="background:var(--hbg)">' +
        '<td colspan="8" style="padding:6px 12px;font-size:12px;color:var(--text);border-bottom:1px solid var(--border)">' +
        '<span style="color:var(--text3);font-weight:600;margin-right:6px">📝</span>' +
        '<span>' + esc(x.contenido) + '</span>' +
        '<span style="float:right;display:flex;gap:4px">' +
        '<button class="btn-delete" style="font-size:10px" onclick="reordenarNota(' + x.id + ',\'up\')">↑</button>' +
        '<button class="btn-delete" style="font-size:10px" onclick="reordenarNota(' + x.id + ',\'down\')">↓</button>' +
        '<button class="btn-delete" style="font-size:10px" onclick="editarNotaPlaca(' + x.id + ')">✏️</button>' +
        '<button class="btn-delete" style="font-size:10px" onclick="eliminarNotaPlaca(' + x.id + ')">✕</button>' +
        '</span></td></tr>';
    }
  });
  h += '</tbody></table>';
  return h;
};

/**
 * Renderiza tabla de puntos para el checklist de orden.
 */
window._renderPtsTableOrder = function(items, ordId) {
  if (!items.length) return '';
  let t = '<table style="margin:0;width:100%"><thead><tr>' +
    '<th style="width:30px">☐</th><th>Punto</th><th>Nombre</th><th>Valor esperado</th><th>Categoría</th><th>IC ref.</th><th>Notas</th>' +
    '</tr></thead><tbody>';
  items.forEach(x => {
    const checked = x._ordChecked ? " checked" : "";
    t += '<tr class="' + (x._ordChecked ? 'med-checked' : '') + '">' +
      '<td><input type="checkbox" class="ord-checkbox" data-ordid="' + ordId + '" data-medid="' + x.id + '"' + checked + ' onchange="reOnCheckOrdenMedicion(this)"></td>' +
      '<td style="font-family:\'Courier New\',monospace;font-weight:700">' + esc(x.punto_medicion) + '</td>' +
      '<td>' + esc(x.nombre) + '</td>' +
      '<td style="font-family:\'Courier New\',monospace;color:var(--accent);font-weight:600">' + esc(x.valor_esperado) + '</td>' +
      '<td style="font-size:12px;color:var(--text3)">' + esc(x.categoria) + '</td>' +
      '<td style="font-size:12px;color:var(--text3)">' + esc(x.ic_referencia) + '</td>' +
      '<td style="font-size:12px;color:var(--text3);max-width:120px;overflow:hidden;text-overflow:ellipsis">' + esc(x.notas) + '</td>' +
      '</tr>';
  });
  t += '</tbody></table>';
  return t;
};

// ── Checklist (per-orden) ──────────────────────────────

/**
 * Maneja el check de un ítem de checklist de orden.
 */
window.reOnCheckOrdenMedicion = async function(cb) {
  const ordId = parseInt(cb.dataset.ordid);
  const medId = parseInt(cb.dataset.medid);
  const checked = cb.checked;
  const tr = cb.closest("tr");
  if (tr) tr.classList.toggle("med-checked", checked);
  reActualizarBarraOrdChecklist(ordId);
  try {
    const r = await apiFetch("/api/ordenes-detalle");
    const d = await r.json();
    const o = (d.ordenes||[]).find(x => x.id===ordId);
    if (!o) return;
    let chk = {};
    try { chk = JSON.parse(o.checklist||'{}'); } catch(e) {}
    if (checked) chk[medId] = true;
    else delete chk[medId];
    const res = await apiFetch("/api/ordenes-detalle", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ id: ordId, _action:"actualizar", checklist: JSON.stringify(chk) })
    });
    const j = await res.json();
    if (!j.ok) cb.checked = !checked;
  } catch { cb.checked = !checked; }
};

/**
 * Actualiza la barra de progreso del checklist de orden.
 */
window.reActualizarBarraOrdChecklist = function(ordId) {
  const cbs = document.querySelectorAll('.ord-checkbox[data-ordid="' + ordId + '"]');
  const total = cbs.length;
  const checked = document.querySelectorAll('.ord-checkbox[data-ordid="' + ordId + '"]:checked').length;
  const pct = total ? Math.round(checked/total*100) : 0;
  const bar = document.getElementById("reChecklistBar_" + ordId);
  const txt = document.getElementById("reChecklistTxt_" + ordId);
  if (bar) bar.style.width = pct + "%";
  if (txt) txt.textContent = checked + "/" + total + " (" + pct + "%)";
};

/**
 * Resetea el checklist de una orden.
 */
window.reResetOrdChecklist = async function(ordId) {
  if (!confirm("¿Resetear checklist de esta orden?")) return;
  try {
    const res = await apiFetch("/api/ordenes-detalle", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ id: ordId, _action:"actualizar", checklist: "{}" })
    });
    const j = await res.json();
    if (j.ok) window.verReparacion(ordId);
  } catch(e) { mostrarMsg("Error al resetear checklist","err"); }
};

// ── Checklist (mediciones, persistido en DB) ────────────

/**
 * Maneja el check de una medición en el checklist de placa.
 */
window.onCheckMedicion = async function(cb) {
  const id = cb.dataset.id;
  const checked = cb.checked;
  const tr = cb.closest("tr");
  if (tr) tr.classList.toggle("med-checked", checked);
  actualizarBarraChecklist(cb.dataset.modelo);
  try {
    const r = await apiFetch("/api/mediciones-placa", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ _action: "check", id: parseInt(id), checked })
    });
    const d = await r.json();
    if (!d.ok) cb.checked = !checked;
  } catch { cb.checked = !checked; }
};

/**
 * Actualiza la barra de progreso del checklist de una placa.
 */
window.actualizarBarraChecklist = function(modelo) {
  const total = document.querySelectorAll('.med-checkbox[data-modelo="' + escAttr(modelo) + '"]').length;
  const checked = document.querySelectorAll('.med-checkbox[data-modelo="' + escAttr(modelo) + '"]:checked').length;
  const pct = total ? Math.round(checked / total * 100) : 0;
  const bar = document.getElementById("checklistBar_" + escAttr(modelo));
  const txt = document.getElementById("checklistTxt_" + escAttr(modelo));
  if (bar) bar.style.width = pct + "%";
  if (txt) txt.textContent = checked + "/" + total + " (" + pct + "%)";
};

/**
 * Resetea el checklist de una placa.
 */
window.resetChecklist = async function(modelo) {
  if (!confirm("¿Resetear checklist de " + modelo + "?")) return;
  await apiFetch("/api/mediciones-placa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _action: "reset-checklist", modelo_placa: modelo })
  });
  window.cargarMedicionesPlaca();
};

// ── Helper: render campo bloque como dropdown ──────────

/**
 * Genera HTML de un select con los bloques disponibles para un modelo.
 */
window._bloqueFieldHtml = function(modelo, currentVal) {
  const bloques = window._bloquesByModel && _bloquesByModel[modelo] ? [..._bloquesByModel[modelo]].filter(b => b).sort() : [];
  const val = esc(currentVal || "");
  let s = '<select onchange="mset(\'bloque\',this.value)" style="padding:8px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font-size:13px;width:100%">' +
    '<option value="">— Sin bloque —</option>';
  bloques.forEach(b => {
    s += '<option value="' + esc(b) + '"' + (b === (currentVal || "").toUpperCase() ? ' selected' : '') + '>' + esc(b) + '</option>';
  });
  s += '</select>';
  return s;
};

// ── CRUD Bloques ───────────────────────────────────────

/**
 * Abre prompt para crear un bloque nuevo.
 */
window.abrirAddBloque = async function(modelo) {
  const nombre = prompt("Nombre del nuevo bloque (ej: ALIMENTACIÓN, PROTECCIÓN, SEÑALIZACIÓN):", "");
  if (!nombre || !nombre.trim()) return;
  const nombreUp = nombre.trim().toUpperCase();
  if (!window._bloquesByModel) window._bloquesByModel = {};
  if (!_bloquesByModel[modelo]) _bloquesByModel[modelo] = new Set();
  _bloquesByModel[modelo].add(nombreUp);
  await apiFetch("/api/bloques", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({_action: "crear", modelo_placa: modelo, nombre: nombreUp})
  });
  cargarMedicionesPlaca();
};

/**
 * Renombra un bloque.
 */
window.editarBloque = async function(modelo, oldName) {
  const nuevo = prompt("Renombrar bloque '" + oldName + "' a:", oldName);
  if (!nuevo || !nuevo.trim() || nuevo.trim().toUpperCase() === oldName.toUpperCase()) return;
  const nuevoUp = nuevo.trim().toUpperCase();
  const r = await apiFetch("/api/bloques", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modelo_placa: modelo, old_name: oldName, new_name: nuevoUp, _action: "renombrar" })
  });
  const d = await r.json();
  if (!d.ok) { alert("Error al renombrar: " + (d.error || "desconocido")); return; }
  if (window._bloquesByModel && _bloquesByModel[modelo]) {
    _bloquesByModel[modelo].delete(oldName.toUpperCase());
    _bloquesByModel[modelo].add(nuevoUp);
  }
  cargarMedicionesPlaca();
};

/**
 * Elimina un bloque.
 */
window.eliminarBloque = async function(modelo, name) {
  if (!confirm("¿Eliminar el bloque '" + name + "'? Los puntos de medición y notas pasarán a 'Sin bloque'.")) return;
  const r = await apiFetch("/api/bloques", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modelo_placa: modelo, name: name, _action: "eliminar" })
  });
  const d = await r.json();
  if (!d.ok) { alert("Error al eliminar: " + (d.error || "desconocido")); return; }
  if (window._bloquesByModel && _bloquesByModel[modelo]) {
    _bloquesByModel[modelo].delete(name.toUpperCase());
  }
  cargarMedicionesPlaca();
};

/**
 * Reordena un bloque (up/down).
 */
window.reordenarBloque = async function(modelo, nombre, dir) {
  await apiFetch("/api/bloques", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({_action: "reordenar", modelo_placa: modelo, nombre, direction: dir})
  });
  cargarMedicionesPlaca();
};

/**
 * Reordena una medición (up/down).
 */
window.reordenarMedicion = async function(id, dir) {
  await apiFetch("/api/mediciones-placa", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({_action: "reordenar", id, direction: dir})
  });
  cargarMedicionesPlaca();
};

/**
 * Reordena una nota (up/down).
 */
window.reordenarNota = async function(id, dir) {
  await apiFetch("/api/notas-placa", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({_action: "reordenar", id, direction: dir})
  });
  cargarMedicionesPlaca();
};

// ── CRUD Placas ────────────────────────────────────────

/**
 * Abre modal para agregar nueva placa.
 */
window.openAddPlaca = function() {
  modal = { type: "addPlaca", modelo: "", tipo_equipo_id: "" };
  renderPlacaModal();
};

/**
 * Renderiza el modal de placa (add/edit) cargando tipos de equipo.
 */
function renderPlacaModal() {
  const isEdit = modal.type === "editPlaca";
  document.getElementById("placaModalInner").innerHTML = '<div style="padding:2rem;text-align:center;color:var(--muted)">⏳ Cargando...</div>';
  document.getElementById("placaModal").style.display = "flex";
  apiFetch("/api/tipos-equipo").then(r => r.json()).then(d => {
    const opts = (d.tipos || []).map(t =>
      '<option value="' + t.id + '"' + (modal.tipo_equipo_id == t.id ? ' selected' : '') + '>' + esc(t.nombre) + '</option>'
    ).join("");
    document.getElementById("placaModalInner").innerHTML =
      '<h2>' + (isEdit ? '✏️' : '➕') + ' ' + (isEdit ? 'Editar' : 'Nueva') + ' placa</h2>' +
      '<div class="fg">' +
      '<div class="field full"><label>Modelo *</label><input id="pmModelo" value="' + esc(modal.modelo) + '" placeholder="Ej: NM-C999" oninput="mset(\'modelo\',this.value.toUpperCase())"></div>' +
      '<div class="field full"><label>Tipo de equipo</label><select id="pmTipo" onchange="mset(\'tipo_equipo_id\',parseInt(this.value)||null)"><option value="">— Sin tipo —</option>' + opts + '</select></div>' +
      '</div>' +
      '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="' + (isEdit ? 'guardarEditarPlaca' : 'agregarPlaca') + '()">Guardar</button></div>';
    const sel = document.getElementById("pmTipo");
    if (sel && modal.tipo_equipo_id) sel.value = modal.tipo_equipo_id;
  }).catch(() => {
    document.getElementById("placaModalInner").innerHTML = '<div style="padding:1rem;text-align:center;color:var(--err)">Error al cargar tipos de equipo</div>';
  });
}

/**
 * Agrega una nueva placa vía API.
 */
window.agregarPlaca = async function() {
  if (!modal || modal.type !== "addPlaca") return;
  if (!modal.modelo.trim()) { alert("Falta el modelo"); return; }
  await apiFetch("/api/placas", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modelo_placa: modal.modelo, tipo_equipo_id: modal.tipo_equipo_id || null })
  });
  closeModal();
  cargarMedicionesPlaca();
};

/**
 * Elimina una placa y todos sus puntos de medición.
 */
window.eliminarPlaca = async function(id) {
  if (!confirm("¿Eliminar esta placa y todos sus puntos de medición?")) return;
  await apiFetch("/api/placas", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _method: "DELETE", id })
  });
  cargarMedicionesPlaca();
};

/**
 * Abre modal para editar una placa.
 */
window.abrirEditarPlaca = function(id) {
  const placa = _placasCache.find(p => p.id === id);
  if (!placa) return;
  modal = { type: "editPlaca", id: placa.id, modelo: placa.modelo_placa, tipo_equipo_id: placa.tipo_equipo_id || "" };
  renderPlacaModal();
};

/**
 * Guarda los cambios de edición de una placa.
 */
window.guardarEditarPlaca = async function() {
  if (!modal || modal.type !== "editPlaca") return;
  if (!modal.modelo.trim()) { alert("Falta el modelo"); return; }
  await apiFetch("/api/placas", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: modal.id, _action: "actualizar", modelo_placa: modal.modelo, tipo_equipo_id: modal.tipo_equipo_id || null })
  });
  closeModal();
  cargarMedicionesPlaca();
};

// ── CRUD Puntos de medición ─────────────────────────────────

/**
 * Abre modal para agregar un punto de medición a una placa.
 */
window.abrirAddPuntoPlaca = function(modelo, bloquePre) {
  modal = {
    type: "addMedicionPlaca",
    modelo_placa: modelo,
    punto_medicion: "",
    nombre: "",
    valor_esperado: "",
    categoria: "",
    ic_referencia: "",
    notas: "",
    bloque: bloquePre || ""
  };
  document.getElementById("placaModal").style.display = "flex";
  document.getElementById("placaModalInner").innerHTML =
    '<h2>📐 Nuevo punto de medición</h2><div class="msub">Placa <b style="color:var(--accent)">' + esc(modelo) + '</b></div>' +
    '<div class="fg">' +
    '<div class="field full"><label>Punto de medición *</label><input value="" oninput="mset(\'punto_medicion\',this.value)" placeholder="Ej: PQ301, Pin 1 BQ24735"></div>' +
    '<div class="field"><label>Nombre</label><input value="" oninput="mset(\'nombre\',this.value)" placeholder="Ej: Alimentación principal"></div>' +
    '<div class="field"><label>Valor esperado</label><input value="" oninput="mset(\'valor_esperado\',this.value)" placeholder="Ej: 19V"></div>' +
    '<div class="field"><label>Categoría</label><input value="" oninput="mset(\'categoria\',this.value)" placeholder="Ej: Tensión, Señal, GND"></div>' +
    '<div class="field"><label>Bloque</label>' + window._bloqueFieldHtml(modelo, bloquePre || "") + '</div>' +
    '<div class="field"><label>IC referencia</label><input value="" oninput="mset(\'ic_referencia\',this.value.toUpperCase())" placeholder="Ej: BQ24735"></div>' +
    '<div class="field full"><label>Notas</label><input value="" oninput="mset(\'notas\',this.value)" placeholder="Ej: Medir con cargador conectado"></div>' +
    '</div>' +
    '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="agregarMedicionPlaca()">Guardar</button></div>';
};

/**
 * Guarda un nuevo punto de medición.
 */
window.agregarMedicionPlaca = async function() {
  if (!modal || modal.type !== "addMedicionPlaca") return;
  if (!modal.punto_medicion.trim()) { alert("Falta el punto de medición"); return; }
  await apiFetch("/api/mediciones-placa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      modelo_placa: modal.modelo_placa,
      punto_medicion: modal.punto_medicion,
      nombre: modal.nombre,
      valor_esperado: modal.valor_esperado,
      categoria: modal.categoria,
      ic_referencia: modal.ic_referencia,
      notas: modal.notas,
      bloque: modal.bloque
    })
  });
  closeModal();
  cargarMedicionesPlaca();
};

/**
 * Elimina un punto de medición.
 */
window.eliminarMedicionPlaca = async function(id) {
  if (!confirm("¿Eliminar este punto de medición?")) return;
  await apiFetch("/api/mediciones-placa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _method: "DELETE", id })
  });
  cargarMedicionesPlaca();
};

/**
 * Abre modal para editar un punto de medición.
 */
window.editarMedicionPlaca = function(id) {
  apiFetch("/api/mediciones-placa").then(r => r.json()).then(d => {
    const item = (d.mediciones || []).find(x => x.id === id);
    if (!item) return;
    modal = {
      type: "editMedicionPlaca", id: item.id,
      modelo_placa: item.modelo_placa,
      punto_medicion: item.punto_medicion,
      nombre: item.nombre,
      valor_esperado: item.valor_esperado,
      categoria: item.categoria,
      ic_referencia: item.ic_referencia,
      notas: item.notas,
      bloque: item.bloque
    };
    document.getElementById("placaModal").style.display = "flex";
    document.getElementById("placaModalInner").innerHTML =
      '<h2>✏️ Editar punto de medición</h2><div class="msub">Modelo <b style="color:var(--accent)">' + esc(item.modelo_placa) + '</b></div>' +
      '<div class="fg">' +
      '<div class="field"><label>Punto de medición</label><input value="' + esc(modal.punto_medicion) + '" oninput="mset(\'punto_medicion\',this.value)" placeholder="Ej: PQ301"></div>' +
      '<div class="field"><label>Nombre</label><input value="' + esc(modal.nombre) + '" oninput="mset(\'nombre\',this.value)" placeholder="Ej: Alimentación principal"></div>' +
      '<div class="field"><label>Valor esperado</label><input value="' + esc(modal.valor_esperado) + '" oninput="mset(\'valor_esperado\',this.value)" placeholder="Ej: 19V"></div>' +
      '<div class="field"><label>Categoría</label><input value="' + esc(modal.categoria) + '" oninput="mset(\'categoria\',this.value)" placeholder="Ej: Tensión, Señal, GND"></div>' +
      '<div class="field"><label>Bloque</label>' + window._bloqueFieldHtml(item.modelo_placa, item.bloque || "") + '</div>' +
      '<div class="field"><label>IC referencia</label><input value="' + esc(modal.ic_referencia) + '" oninput="mset(\'ic_referencia\',this.value.toUpperCase())" placeholder="Ej: BQ24735"></div>' +
      '<div class="field full"><label>Notas</label><input value="' + esc(modal.notas) + '" oninput="mset(\'notas\',this.value)" placeholder="Ej: Medir con cargador conectado"></div>' +
      '</div>' +
      '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok blue" onclick="guardarEdicionMedicionPlaca()">Guardar</button></div>';
  });
};

/**
 * Guarda edición de un punto de medición.
 */
window.guardarEdicionMedicionPlaca = async function() {
  if (!modal || modal.type !== "editMedicionPlaca") return;
  await apiFetch("/api/mediciones-placa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id: modal.id, _action: "actualizar",
      punto_medicion: modal.punto_medicion,
      nombre: modal.nombre,
      valor_esperado: modal.valor_esperado,
      categoria: modal.categoria,
      ic_referencia: modal.ic_referencia,
      notas: modal.notas,
      bloque: modal.bloque
    })
  });
  closeModal();
  cargarMedicionesPlaca();
};

// ── CRUD Notas de placa ──────────────────────────────────

/**
 * Abre modal para agregar una nota a una placa.
 */
window.abrirAddNotaPlaca = function(modelo, bloquePre) {
  modal = { type: "addNotaPlaca", modelo_placa: modelo, contenido: "", bloque: bloquePre || "" };
  document.getElementById("placaModal").style.display = "flex";
  document.getElementById("placaModalInner").innerHTML =
    '<h2>📝 Nueva nota</h2><div class="msub">Placa <b style="color:var(--accent)">' + esc(modelo) + '</b></div>' +
    '<div class="fg">' +
    '<div class="field full"><label>Contenido</label><textarea rows="3" oninput="mset(\'contenido\',this.value)" placeholder="Ej: Revisar diodo de protección D4801 antes de probar"></textarea></div>' +
    '<div class="field full"><label>Bloque</label>' + window._bloqueFieldHtml(modelo, bloquePre || "") + '</div>' +
    '</div>' +
    '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="agregarNotaPlaca()">Guardar</button></div>';
};

/**
 * Guarda una nueva nota de placa.
 */
window.agregarNotaPlaca = async function() {
  if (!modal || modal.type !== "addNotaPlaca") return;
  if (!modal.contenido.trim()) { alert("Falta el contenido"); return; }
  await apiFetch("/api/notas-placa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modelo_placa: modal.modelo_placa, contenido: modal.contenido, bloque: modal.bloque })
  });
  closeModal();
  cargarMedicionesPlaca();
};

/**
 * Elimina una nota de placa.
 */
window.eliminarNotaPlaca = async function(id) {
  if (!confirm("¿Eliminar esta nota?")) return;
  await apiFetch("/api/notas-placa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ _method: "DELETE", id })
  });
  cargarMedicionesPlaca();
};

/**
 * Abre modal para editar una nota de placa.
 */
window.editarNotaPlaca = function(id) {
  apiFetch("/api/notas-placa").then(r => r.json()).then(d => {
    const item = (d.notas || []).find(x => x.id === id);
    if (!item) return;
    modal = { type: "editNotaPlaca", id: item.id, modelo_placa: item.modelo_placa, contenido: item.contenido, bloque: item.bloque || "" };
    document.getElementById("placaModal").style.display = "flex";
    document.getElementById("placaModalInner").innerHTML =
      '<h2>✏️ Editar nota</h2><div class="msub">Placa <b style="color:var(--accent)">' + esc(item.modelo_placa) + '</b></div>' +
      '<div class="fg">' +
      '<div class="field full"><label>Contenido</label><textarea rows="3" oninput="mset(\'contenido\',this.value)">' + esc(item.contenido) + '</textarea></div>' +
      '<div class="field full"><label>Bloque</label>' + window._bloqueFieldHtml(item.modelo_placa, item.bloque || "") + '</div>' +
      '</div>' +
      '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok blue" onclick="guardarEditarNotaPlaca()">Guardar</button></div>';
  });
};

/**
 * Guarda edición de una nota de placa.
 */
window.guardarEditarNotaPlaca = async function() {
  if (!modal || modal.type !== "editNotaPlaca") return;
  await apiFetch("/api/notas-placa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: modal.id, _action: "actualizar", contenido: modal.contenido, bloque: modal.bloque })
  });
  closeModal();
  cargarMedicionesPlaca();
};
