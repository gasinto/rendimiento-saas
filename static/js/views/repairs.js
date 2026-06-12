// ── JC-Sistema: Vista Reparaciones ─────────────────────────────

/**
 * Carga las reparaciones según filtros (empresa, estado, resultado, búsqueda).
 * Llamado desde cambiarVista('reparaciones') y desde inputs onchange/oninput.
 */
window.cargarReparaciones = async function() {
  const q = (document.getElementById("reparacionesQ")?.value || "").trim();
  const empresa = document.getElementById("reparacionesEmpresa")?.value || "";
  const estado = document.getElementById("reparacionesEstado")?.value || "";
  const resultado = document.getElementById("reparacionesResultado")?.value || "";
  const out = document.getElementById("reparacionesResults");
  out.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--muted)">⏳ Cargando reparaciones…</div>';
  try {
    let url = "/api/ordenes-detalle?";
    const params = [];
    if (empresa) params.push("empresa_id=" + encodeURIComponent(empresa));
    if (estado) params.push("estado=" + encodeURIComponent(estado));
    if (resultado) params.push("resultado=" + encodeURIComponent(resultado));
    if (q) params.push("q=" + encodeURIComponent(q));
    url += params.join("&");
    const r = await apiFetch(url);
    const data = await r.json();
    const ordenes = data.ordenes || [];
    if (!ordenes.length) {
      out.innerHTML = '<div class="empty" style="text-align:center;padding:2rem;color:var(--muted)">' +
        (q ? 'Sin resultados para <b>' + esc(q) + '</b>' : 'Sin reparaciones registradas aún.') + '</div>';
      return;
    }
    let html = "";
    ordenes.forEach(o => {
      let chkHtml = "";
      if (o.checklist) {
        let chk = {};
        try { chk = JSON.parse(o.checklist); } catch(e) {}
        const meds = o.mediciones || [];
        const total = meds.length;
        const checked = meds.filter(m => chk[m.id]).length;
        const pct = total ? Math.round(checked / total * 100) : 0;
        if (total) {
          chkHtml = '<div style="margin-top:6px;font-size:11px;color:var(--text3)">' +
            '<span style="display:inline-flex;align-items:center;gap:6px">' +
              '📋 ' + checked + '/' + total + ' (' + pct + '%) ' +
              '<span style="display:inline-block;width:50px;height:6px;background:var(--border);border-radius:3px;overflow:hidden;vertical-align:middle">' +
                '<span style="display:block;height:100%;width:' + pct + '%;background:var(--success);border-radius:3px"></span>' +
              '</span>' +
            '</span></div>';
        }
      }
      const estadoClass = o.estado === "completado" ? "green" : (o.estado === "en_curso" ? "blue" : "");
      const resultClass = o.resultado === "reparado" ? "green" : (o.resultado === "no_reparado" ? "red" : "");
      html += '<div class="card ics-card" style="margin-bottom:10px">' +
        '<div class="chead"><div>' +
          '<div style="font-family:\'Courier New\',monospace;font-size:14px;font-weight:700;color:var(--accent)">#' + o.numero +
          ' <span style="font-size:11px;color:var(--text3);font-weight:400">' + esc(o.empresa_nombre || '') + '</span>' +
          ' <span style="font-size:11px;padding:2px 8px;border-radius:4px;background:var(--okbg);color:var(--' + estadoClass + ')">' + esc(o.estado || '') + '</span>' +
          (o.resultado ? ' <span style="font-size:11px;padding:2px 8px;border-radius:4px;background:var(--redbg);color:var(--' + resultClass + ')">' + esc(o.resultado) + '</span>' : '') +
          '</div>' +
          '<div style="font-size:12px;color:var(--text3)">' + esc(o.placa || '') + ' · ' + esc(o.falla || '') + '</div>' +
          chkHtml +
        '</div></div>' +
        '<div style="padding:8px 12px;border-top:1px solid var(--border)">' +
          '<button class="tbtn" style="font-size:11px" onclick="verReparacion(' + o.id + ')">🔍 Ver detalle</button>' +
          (o.estado !== "completado" ? ' <button class="tbtn" style="font-size:11px" onclick="completarReparacion(' + o.id + ')">✅ Completar</button>' : '') +
          ' <button class="tbtn" style="font-size:11px" onclick="descargarInformeSolucion(' + o.id + ')">📄 TXT</button>' +
          ' <button class="tbtn" style="font-size:11px" onclick="descargarInformeSolucionPNG(' + o.id + ')">🖼️ PNG</button>' +
          (o.estado === "completado" ? '' : ' <button class="btn-delete" onclick="eliminarReparacion(' + o.id + ')">✕</button>') +
        '</div></div>';
    });
    out.innerHTML = html;
  } catch(e) {
    out.innerHTML = '<div class="msg err show">Error al cargar reparaciones</div>';
  }
};

/**
 * Carga el select de empresas para filtrar reparaciones.
 */
window.cargarEmpresasSelect = async function() {
  try {
    const r = await apiFetch("/api/empresas");
    const d = await r.json();
    const sel = document.getElementById("reparacionesEmpresa");
    sel.innerHTML = '<option value="">Todas las empresas</option>';
    (d.empresas || []).forEach(e => {
      const opt = document.createElement("option");
      opt.value = e.id;
      opt.textContent = e.nombre;
      sel.appendChild(opt);
    });
  } catch(e) {
    console.error("Error cargando empresas:", e);
  }
};

/**
 * Abre el modal para agregar una nueva reparación a una orden.
 */
window.openAddReparacion = async function() {
  const inner = document.getElementById("placaModalInner");
  document.getElementById("placaModal").style.display = "flex";
  inner.classList.remove("modal-wide");
  // Fetch empresas
  let empresasOpts = "";
  try {
    const r = await apiFetch("/api/empresas");
    const d = await r.json();
    empresasOpts = (d.empresas || []).map(e => '<option value="' + e.id + '">' + esc(e.nombre) + '</option>').join("");
  } catch(e) { empresasOpts = '<option value="">Sin empresas</option>'; }
  inner.innerHTML =
    '<h2>➕ Nueva reparación</h2><div class="msub">Vinculada a una orden existente.</div>' +
    '<div class="fg">' +
      '<div class="field"><label>Empresa *</label><select id="reNuevaEmpresa">' + empresasOpts + '</select></div>' +
      '<div class="field"><label>N° de orden *</label><input type="number" id="reNuevoNumero" placeholder="11459"></div>' +
      '<div class="field"><label>Fecha</label><input type="date" id="reNuevaFecha"></div>' +
      '<div class="field full"><label>Placa</label><input id="reNuevaPlaca" placeholder="Ej: NM-C121"></div>' +
      '<div class="field full"><label>Falla</label><textarea id="reNuevaFalla" rows="2" placeholder="Describe la falla"></textarea></div>' +
      '<div class="field"><label>Tipo de equipo</label><input id="reNuevaTipoEquipo" placeholder="Ej: NOTEBOOK"></div>' +
      '<div class="field"><label>Marca</label><input id="reNuevaMarca" placeholder="Ej: HP"></div>' +
      '<div class="field"><label>Modelo</label><input id="reNuevaModelo" placeholder="Ej: 240 G8"></div>' +
      '<div class="field"><label>Estado</label><select id="reNuevoEstado"><option value="en_curso">En curso</option><option value="completado">Completado</option></select></div>' +
      '<div class="field"><label>Resultado</label><select id="reNuevoResultado"><option value="n/a">N/A</option><option value="reparado">Reparado</option><option value="no_reparado">No reparado</option></select></div>' +
    '</div>' +
    '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="submitAddReparacion()">Guardar</button></div>';
  // Set default date
  document.getElementById("reNuevaFecha").value = new Date().toISOString().split("T")[0];
};

/**
 * Envía la nueva reparación a la API.
 */
window.submitAddReparacion = async function() {
  const empresa_id = document.getElementById("reNuevaEmpresa")?.value;
  const numero = document.getElementById("reNuevoNumero")?.value;
  const fecha = document.getElementById("reNuevaFecha")?.value;
  const placa = document.getElementById("reNuevaPlaca")?.value;
  const falla = document.getElementById("reNuevaFalla")?.value;
  const tipo_equipo = document.getElementById("reNuevaTipoEquipo")?.value||"";
  const marca = document.getElementById("reNuevaMarca")?.value||"";
  const modelo = document.getElementById("reNuevaModelo")?.value||"";
  if (!empresa_id || !numero) { alert("Faltan empresa y número de orden"); return; }
  const estado = document.getElementById("reNuevoEstado")?.value||"en_curso";
  const resultado = document.getElementById("reNuevoResultado")?.value||"n/a";
  const r = await apiFetch("/api/ordenes-detalle", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ empresa_id: parseInt(empresa_id), numero: parseInt(numero), fecha, placa, falla, tipo_equipo, marca, modelo, estado, resultado })
  });
  const res = await r.json();
  if (res.ok) { mostrarMsg("✅ Reparación creada","ok"); closeModal(); window.cargarReparaciones(); }
  else { mostrarMsg("❌ "+(res.error||"Error"),"err"); }
};

/**
 * Elimina una reparación por ID.
 */
window.eliminarReparacion = async function(id) {
  if (!confirm("¿Eliminar esta reparación?")) return;
  await apiFetch("/api/ordenes-detalle", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ _method: "DELETE", id })
  });
  window.cargarReparaciones();
};

/**
 * Abre el detalle de una reparación en modal.
 */
window.verReparacion = async function(id) {
  try {
    const r = await apiFetch("/api/ordenes-detalle");
    const data = await r.json();
    const orden = (data.ordenes||[]).find(x => x.id === id);
    if (!orden) { alert("No encontrada"); return; }
    const inner = document.getElementById("placaModalInner");
    document.getElementById("placaModal").style.display = "flex";
    inner.classList.add("modal-wide");
    // Cargar mediciones de la placa asociada
    let medsHtml = "";
    if (orden.placa) {
      try {
        const mr = await apiFetch("/api/mediciones-placa?modelo=" + encodeURIComponent(orden.placa));
        const md = await mr.json();
        const meds = md.mediciones || [];
        if (meds.length) {
          medsHtml = window._renderPtsTableOrder(meds, id);
        }
      } catch(e) {}
    }
    let chk = {};
    try { chk = JSON.parse(orden.checklist||'{}'); } catch(e) {}
    // Mark checked in the rendered table
    medsHtml = medsHtml.replace(/onchange="reOnCheckOrdenMedicion/g,
      (match) => {
        return match;
      }
    );
    // Apply checklist state
    Object.keys(chk).forEach(medId => {
      if (chk[medId]) {
        const cb = inner.querySelector('.ord-checkbox[data-medid="' + medId + '"]');
        if (cb) { cb.checked = true; const tr = cb.closest("tr"); if (tr) tr.classList.add("med-checked"); }
      }
    });

    inner.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">' +
        '<div>' +
          '<h2 style="margin:0;font-size:16px">🔍 #' + orden.numero + '</h2>' +
          '<div style="font-size:13px;color:var(--text3);margin-top:4px">' + esc(orden.empresa_nombre||'') + ' · ' + (orden.placa||'') + '</div>' +
        '</div>' +
        '<button class="btn-delete" onclick="closeModal()" style="font-size:1.2rem">✕</button>' +
      '</div>' +
      '<div class="fg" style="grid-template-columns:1fr 1fr">' +
        '<div><b>Estado:</b> <span style="color:var(--accent)">' + esc(orden.estado||'') + '</span></div>' +
        '<div><b>Resultado:</b> <span style="color:var(--success)">' + esc(orden.resultado||'') + '</span></div>' +
      '</div>' +
      (orden.falla ? '<div style="margin-top:8px"><b>Falla:</b><br>' + esc(orden.falla) + '</div>' : '') +
      (orden.diagnostico ? '<div style="margin-top:8px"><b>Diagnóstico:</b><br>' + esc(orden.diagnostico) + '</div>' : '') +
      (orden.proceso ? '<div style="margin-top:8px"><b>Proceso:</b><br><pre style="white-space:pre-wrap;font-size:12px;color:var(--text2)">' + esc(orden.proceso) + '</pre></div>' : '') +
      (orden.solucion ? '<div style="margin-top:8px"><b>Solución:</b><br><pre style="white-space:pre-wrap;font-size:12px;color:var(--success)">' + esc(orden.solucion) + '</pre></div>' : '') +
      (orden.tipo ? '<div style="margin-top:8px"><b>Tipo:</b> ' + esc(orden.tipo) + ' · <b>Puntaje:</b> ' + orden.puntaje + ' pts</div>' : '') +
      (medsHtml ? '<div style="margin-top:12px"><h3 style="font-size:13px;margin:0 0 6px 0">📋 Checklist mediciones</h3>' +
        '<div id="reChecklist_' + id + '">' + medsHtml + '</div>' +
        '<div style="display:flex;align-items:center;gap:10px;margin-top:8px;padding:6px 0">' +
          '<span id="reChecklistTxt_' + id + '">0/0 (0%)</span>' +
          '<div style="flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden">' +
            '<div id="reChecklistBar_' + id + '" style="height:100%;width:0%;background:var(--success);border-radius:3px;transition:width 0.2s"></div>' +
          '</div>' +
          '<button class="tbtn" style="font-size:10px;padding:2px 8px" onclick="reResetOrdChecklist(' + id + ')">↻ Reset</button>' +
        '</div>' : '') +
      '<div style="margin-top:16px;display:flex;gap:8px">' +
        '<button class="tbtn" onclick="abrirEditarReparacion(' + id + ')">✏️ Editar</button>' +
        (orden.estado !== "completado" ? '<button class="tbtn prim" onclick="completarReparacion(' + id + ')">✅ Completar</button>' : '') +
        '<button class="bcancel" onclick="closeModal()">Cerrar</button>' +
      '</div>';
    // Update checklist counts
    setTimeout(() => { window.reActualizarBarraOrdChecklist(id); }, 100);
  } catch(e) {
    alert("Error al cargar detalle");
  }
};

/**
 * Abre modal para editar una reparación.
 */
window.abrirEditarReparacion = async function(id) {
  try {
    const r = await apiFetch("/api/ordenes-detalle");
    const data = await r.json();
    const orden = (data.ordenes||[]).find(x => x.id === id);
    if (!orden) { alert("No encontrada"); return; }
    let empresasOpts = "";
    const r2 = await apiFetch("/api/empresas");
    const d2 = await r2.json();
    empresasOpts = (d2.empresas || []).map(e =>
      '<option value="' + e.id + '"' + (e.id === orden.empresa_id ? ' selected' : '') + '>' + esc(e.nombre) + '</option>'
    ).join("");
    const inner = document.getElementById("placaModalInner");
    document.getElementById("placaModal").style.display = "flex";
    inner.classList.remove("modal-wide");
    inner.innerHTML =
      '<h2>✏️ Editar reparación #' + orden.numero + '</h2>' +
      '<div style="font-size:12px;color:var(--text3);margin-bottom:12px">ID: ' + id + '</div>' +
      '<div class="fg">' +
        '<div class="field"><label>Empresa</label><select id="reEditEmpresa">' + empresasOpts + '</select></div>' +
        '<div class="field"><label>N° de orden</label><input type="number" id="reEditNumero" value="' + orden.numero + '"></div>' +
        '<div class="field"><label>Fecha</label><input type="date" id="reEditFecha" value="' + (orden.fecha||'') + '"></div>' +
        '<div class="field full"><label>Placa</label><input id="reEditPlaca" value="' + esc(orden.placa||'') + '"></div>' +
        '<div class="field full"><label>Falla</label><textarea id="reEditFalla" rows="2">' + esc(orden.falla||'') + '</textarea></div>' +
        '<div class="field"><label>Tipo equipo</label><input id="reEditTipoEquipo" value="' + esc(orden.tipo_equipo||'') + '"></div>' +
        '<div class="field"><label>Marca</label><input id="reEditMarca" value="' + esc(orden.marca||'') + '"></div>' +
        '<div class="field"><label>Modelo</label><input id="reEditModelo" value="' + esc(orden.modelo||'') + '"></div>' +
        '<div class="field"><label>Estado</label><select id="reEditEstado"><option value="en_curso"' + (orden.estado==='en_curso'?' selected':'') + '>En curso</option><option value="completado"' + (orden.estado==='completado'?' selected':'') + '>Completado</option></select></div>' +
        '<div class="field"><label>Resultado</label><select id="reEditResultado"><option value="n/a"' + (orden.resultado==='n/a'?' selected':'') + '>N/A</option><option value="reparado"' + (orden.resultado==='reparado'?' selected':'') + '>Reparado</option><option value="no_reparado"' + (orden.resultado==='no_reparado'?' selected':'') + '>No reparado</option></select></div>' +
        '<div class="field full"><label>Diagnóstico</label><textarea id="reEditDiagnostico" rows="2">' + esc(orden.diagnostico||'') + '</textarea></div>' +
        '<div class="field full"><label>Proceso</label><textarea id="reEditProceso" rows="3">' + esc(orden.proceso||'') + '</textarea></div>' +
        '<div class="field full"><label>Solución</label><textarea id="reEditSolucion" rows="3">' + esc(orden.solucion||'') + '</textarea></div>' +
      '</div>' +
      '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="guardarEditarReparacion(' + id + ')">Guardar</button></div>';
  } catch(e) {
    alert("Error al cargar datos");
  }
};

/**
 * Guarda los cambios de edición de una reparación.
 */
window.guardarEditarReparacion = async function(id) {
  const empresa_id = parseInt(document.getElementById("reEditEmpresa").value);
  const numero = parseInt(document.getElementById("reEditNumero").value);
  const data = {
    id, _action: "actualizar",
    empresa_id, numero,
    fecha: document.getElementById("reEditFecha").value,
    placa: document.getElementById("reEditPlaca").value,
    falla: document.getElementById("reEditFalla").value,
    tipo_equipo: document.getElementById("reEditTipoEquipo").value,
    marca: document.getElementById("reEditMarca").value,
    modelo: document.getElementById("reEditModelo").value,
    estado: document.getElementById("reEditEstado").value,
    resultado: document.getElementById("reEditResultado").value,
    diagnostico: document.getElementById("reEditDiagnostico").value,
    proceso: document.getElementById("reEditProceso").value,
    solucion: document.getElementById("reEditSolucion").value,
  };
  const r = await apiFetch("/api/ordenes-detalle", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify(data)
  });
  const res = await r.json();
  if (res.ok) { mostrarMsg("✅ Reparación actualizada","ok"); closeModal(); window.cargarReparaciones(); }
  else { mostrarMsg("❌ "+(res.error||"Error"),"err"); }
};

/**
 * Marca una reparación como completada.
 */
window.completarReparacion = async function(id) {
  if (!confirm("¿Marcar esta reparación como completada?")) return;
  const r = await apiFetch("/api/ordenes-detalle", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ id, _action:"actualizar", estado:"completado" })
  });
  const res = await r.json();
  if (res.ok) { mostrarMsg("✅ Reparación completada","ok"); window.cargarReparaciones(); }
  else { mostrarMsg("❌ "+(res.error||"Error"),"err"); }
};
