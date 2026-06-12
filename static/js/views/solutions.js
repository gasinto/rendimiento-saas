// ── JC-Sistema: Vista Soluciones ───────────────────────────────

/**
 * Carga y renderiza las soluciones registradas y las ├│rdenes completadas.
 * Llamado desde cambiarVista() y desde eventos de b├║squeda/CRUD.
 */
window.cargarSoluciones = async () => {
  const q = (document.getElementById("solucionesQ")?.value || "").trim();
  try {
    const [r1, r2] = await Promise.all([
      apiFetch("/api/soluciones" + (q ? "?q=" + encodeURIComponent(q) : "")),
      apiFetch("/api/ordenes-detalle?estado=completado" + (q ? "&q=" + encodeURIComponent(q) : ""))
    ]);
    const d1 = await r1.json();
    const d2 = await r2.json();
    const sols = d1.soluciones || [];
    const ords = d2.ordenes || [];
    const stat = document.getElementById("solucionesStat");
    const out = document.getElementById("solucionesResults");
    const total = sols.length + ords.length;
    stat.textContent = total + " solució" + (total===1?"n":"nes");
    if (!total) {
      out.innerHTML = '<div class="empty" style="padding:2rem;color:var(--muted)">'+(q?'Sin resultados para <b>'+esc(q)+'</b>':'Sin soluciones registradas a├║n.')+'</div>';
      return;
    }
    let html = "";
    // Completed ordenes (richer detail)
    ords.forEach(o => {
      html += '<div class="card ics-card" style="margin-bottom:10px;border-color:var(--okbg)">'+
        '<div class="chead"><div>'+
          '<div style="font-family:\'Courier New\',monospace;font-size:14px;font-weight:700;color:var(--success)">'+esc(o.placa||'')+
          ' <span style="font-size:11px;color:var(--text3);font-weight:400">#'+o.numero+' — '+esc(o.empresa_nombre||'')+'</span></div>'+
          '<div style="font-size:12px;color:var(--text3)">'+esc(o.falla||'')+'</div>'+
        '</div></div>'+
        '<div style="padding:8px 12px;font-size:13px;border-top:1px solid var(--border)">'+
          (o.diagnostico?'<div style="margin-bottom:4px"><span style="font-weight:600;color:var(--accent)">Diagn├│stico:</span> <span style="color:#bbb">'+esc(o.diagnostico)+'</span></div>':'')+
          (o.proceso?'<div style="margin-bottom:4px"><span style="font-weight:600;color:var(--accent)">Proceso:</span> <span style="color:#bbb;white-space:pre-wrap">'+esc(o.proceso)+'</span></div>':'')+
          '<div><span style="font-weight:600;color:var(--success)">Soluci├│n:</span> <span style="white-space:pre-wrap">'+esc(o.solucion)+'</span></div>'+
          (o.tipo?'<div style="font-size:10px;color:var(--text3);margin-top:4px">Tipo: '+esc(o.tipo)+' ('+o.puntaje+' pts)</div>':'')+
          (o.created_at?'<div style="font-size:10px;color:var(--text3);margin-top:2px">'+o.fecha+'</div>':'')+
          '<div style="margin-top:6px"><button class="tbtn" style="font-size:11px" onclick="descargarInformeSolucion('+o.id+')">📄 TXT</button> <button class="tbtn" style="font-size:11px" onclick="descargarInformeSolucionPNG('+o.id+')">🖼️ PNG</button></div>'+
        '</div></div>';
    });
    // Old soluciones (legacy)
    sols.forEach(s => {
      let icsList = "";
      try { const parsed = JSON.parse(s.ics||"[]"); if (Array.isArray(parsed) && parsed.length) icsList = '<div style="font-size:11px;color:var(--text3);margin-top:4px">ICs: '+parsed.join(", ")+'</div>'; } catch(e) {}
      html += '<div class="card ics-card" style="margin-bottom:10px">'+
        '<div class="chead"><div>'+
          '<div style="font-family:\'Courier New\',monospace;font-size:14px;font-weight:700;color:var(--accent)">'+esc(s.placa)+'</div>'+
          '<div style="font-size:12px;color:#bbb">'+esc(s.falla)+'</div>'+
        '</div>'+
        '<div style="display:flex;gap:4px">'+
        '<button class="btn-delete" onclick="window.openEditSolucion('+s.id+')" title="Editar">✏️</button>'+
        '<button class="btn-delete" onclick="window.eliminarSolucion('+s.id+')" title="Eliminar">✕</button></div></div>'+
        '<div style="padding:8px 12px;font-size:13px;border-top:1px solid var(--border)">'+
          '<div style="white-space:pre-wrap">'+esc(s.solucion)+'</div>'+
          icsList+
          (s.created_at?'<div style="font-size:10px;color:#bbb;margin-top:6px">'+esc(s.created_at)+'</div>':'')+
          '<div style="margin-top:6px"><button class="tbtn" style="font-size:11px" onclick="descargarInformeSolucion('+s.id+')">📄 TXT</button> <button class="tbtn" style="font-size:11px" onclick="descargarInformeSolucionPNG('+s.id+')">🖼️ PNG</button></div>'+
        '</div></div>';
    });
    out.innerHTML = html;
  } catch(e) {
    const out = document.getElementById("solucionesResults");
    if (out) out.innerHTML = '<div class="msg err show">Error al cargar soluciones</div>';
  }
};

/**
 * Elimina una soluci├│n por ID.
 * @param {number} id - ID de la soluci├│n
 */
window.eliminarSolucion = async (id) => {
  if (!confirm("Eliminar esta solución?")) return;
  await apiFetch("/api/soluciones", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ _method: "DELETE", id })
  });
  window.cargarSoluciones();
};

/**
 * Descarga un informe TXT de la soluci├│n.
 * @param {number} id - ID de la orden/soluci├│n
 */
window.descargarInformeSolucion = async (id) => {
  const r = await apiFetch("/api/soluciones/reporte?id=" + id);
  const data = await r.json();
  if (data.error) { alert(data.error); return; }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([data.contenido], {type:"text/plain;charset=utf-8"}));
  a.download = data.nombre_archivo;
  a.click();
  URL.revokeObjectURL(a.href);
};

/**
 * Descarga un informe PNG de la soluci├│n con mediciones incluidas.
 * Renderiza un canvas con toda la informaci├│n t├ęcnica.
 * @param {number} id - ID de la orden/soluci├│n
 */
window.descargarInformeSolucionPNG = async (id) => {
  // ── 1. Fetch data (try soluciones first, then ordenes)
  const [solRes, ordRes] = await Promise.all([
    apiFetch("/api/soluciones"),
    apiFetch("/api/ordenes-detalle?estado=completado")
  ]);
  const solData = await solRes.json();
  const ordData = await ordRes.json();

  // Try soluciones first by id
  let sol = (solData.soluciones||[]).find(x => x.id === id);
  let isOrder = false;
  // If not found, try ordenes by id
  if (!sol) {
    const ord = (ordData.ordenes||[]).find(x => x.id === id);
    if (ord) {
      sol = ord;
      isOrder = true;
    }
  }
  if (!sol) { alert("Solución no encontrada"); return; }

  // Normalize fields
  const placa = sol.placa || "";
  const falla = sol.falla || "";
  // For soluciones table: solucion is direct; for ordenes: solucion field
  const solucionText = sol.solucion || "";
  const icsRaw = sol.ics || "[]";
  const icsArr = (() => { try { const p = JSON.parse(icsRaw); return Array.isArray(p) ? p : []; } catch(e) { return []; } })();
  const fechaSol = sol.created_at ? sol.created_at.slice(0,10) : "";
  const diagnostico = isOrder ? (sol.diagnostico || "") : "";
  const proceso = isOrder ? (sol.proceso || "") : "";
  const tipo = isOrder ? (sol.tipo || "") : "";
  const puntaje = isOrder ? (sol.puntaje || "") : "";

  const nowStr = new Date().toLocaleString("es-AR", { day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit" });

  // ── Fetch mediciones for the board
  let mediciones = [];
  try {
    const medRes = await apiFetch("/api/mediciones-placa?modelo=" + encodeURIComponent(placa));
    const medData = await medRes.json();
    mediciones = medData.mediciones || [];
  } catch(e) {}
  // Group by bloque
  const bloques = {};
  mediciones.forEach(m => {
    const b = m.bloque || "—";
    if (!bloques[b]) bloques[b] = [];
    bloques[b].push(m);
  });

  // Measure layout
  const margin = 50;
  const lineH = 34;
  const titleSize = 28;
  const labelSize = 22;
  const valSize = 21;
  const medSize = 19;
  const pad = margin;
  const maxW = 1000;
  const wrapW = maxW - 16;

  // ── Colors ──
  const bg = "#1e1e2e";
  const text = "#e0e0e0";
  const accent = "#89b4fa";
  const success = "#a6e3a1";
  const dim = "#6c7086";
  const border = "#313244";
  const highlight = "#cba6f7";

  // ── Render content; returns final Y ──
  function renderContent(cx) {
    function d(str, x, y, sz, clr, bld) {
      cx.font = (bld ? "bold " : "") + sz + "px 'Courier New', monospace";
      cx.fillStyle = clr || text;
      cx.fillText(str, x, y);
    }
    function wrap(str, x, y, mw, sz, clr, bld) {
      cx.font = (bld ? "bold " : "") + sz + "px 'Courier New', monospace";
      cx.fillStyle = clr || text;
      const perLine = Math.floor(mw / (sz * 0.6));
      for (let i = 0; i < str.length; i += perLine) {
        cx.fillText(str.slice(i, i + perLine), x, y);
        y += lineH;
      }
      return y;
    }
    function head(lbl, yy) {
      cx.fillStyle = "#313244";
      cx.fillRect(pad, yy - labelSize + 2, maxW, lineH + 6);
      d("  " + lbl, pad + 4, yy, labelSize, accent, true);
      return yy + lineH + 4;
    }

    let y = pad;
    // Title
    d("▌ INFORME TÉCNICO — SOLUCIÓN", pad, y, titleSize, accent, true);
    y += lineH + 4;
    // Separator
    cx.strokeStyle = border;
    cx.lineWidth = 1.5;
    cx.beginPath();
    cx.moveTo(pad, y);
    cx.lineTo(pad + maxW, y);
    cx.stroke();
    y += lineH;
    // Date
    d(nowStr, pad, y, labelSize, dim);
    y += lineH + 4;
    // Placa
    y = head("PLACA", y);
    d("  " + (placa || "—"), pad + 4, y, valSize, text);
    y += lineH + 6;
    // Falla
    y = head("FALLA REPORTADA", y);
    y = wrap(falla || "—", pad + 4, y, wrapW, valSize, text);
    y += 6;
    // Solución
    y = head("SOLUCIÓN APLICADA", y);
    y = wrap(solucionText || "—", pad + 4, y, wrapW, valSize, success);
    y += 6;
    // Diagnóstico
    if (diagnostico) { y = head("DIAGNÓSTICO", y); y = wrap(diagnostico, pad + 4, y, wrapW, valSize, text); y += 6; }
    // Proceso
    if (proceso) { y = head("PROCESO", y); y = wrap(proceso, pad + 4, y, wrapW, valSize, text); y += 6; }
    // ICs
    if (icsArr.length) {
      cx.fillStyle = "#313244";
      cx.fillRect(pad, y - labelSize + 2, maxW, lineH + 6);
      d("  CIRCUITOS INTEGRADOS", pad + 4, y, labelSize, highlight, true);
      y += lineH + 4;
      icsArr.forEach(ic => { d("  • " + ic, pad + 4, y, valSize, text); y += lineH; });
      y += 6;
    }
    // Fecha / tipo
    let info = "";
    if (fechaSol) info += "Fecha: " + fechaSol;
    if (tipo) info += (info ? "  |  " : "") + tipo + " — " + puntaje + " pts";
    if (info) { d(info, pad, y, labelSize, dim); y += lineH + 6; }
    // Mediciones separator
    if (Object.keys(bloques).length) {
      cx.strokeStyle = border;
      cx.lineWidth = 1.5;
      cx.beginPath();
      cx.moveTo(pad, y);
      cx.lineTo(pad + maxW, y);
      cx.stroke();
      y += 6;
      for (const [bloque, meds] of Object.entries(bloques)) {
        cx.fillStyle = "#45475a";
        cx.fillRect(pad, y - labelSize + 2, maxW, lineH + 6);
        d("  ▌ " + bloque, pad + 4, y, labelSize, accent, true);
        y += lineH + 6;
        meds.forEach(m => {
          const lbl = (m.punto_medicion || "") + " — " + (m.nombre || "");
          const v = m.valor_esperado || "";
          cx.fillStyle = "#2a2a3e";
          cx.fillRect(pad, y - medSize + 2, maxW, lineH + 3);
          let disp = lbl.length > 60 ? lbl.slice(0,57) + "..." : lbl;
          d("    " + disp, pad + 4, y, medSize, text);
          if (v) d(v, pad + maxW - cx.measureText(v).width - 8, y, medSize, success);
          y += lineH + 3;
        });
        y += 4;
      }
    }
    return y;
  }

  // ── Measure exact height ──
  const meas = document.createElement("canvas");
  meas.width = maxW + pad * 2;
  meas.height = 5000;
  const measuredY = renderContent(meas.getContext("2d"));
  const canvasH = measuredY + pad + 8;

  // ── Real render ──
  const canvas = document.createElement("canvas");
  canvas.width = maxW + pad * 2;
  canvas.height = canvasH;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  renderContent(ctx);
  // Footer
  ctx.fillStyle = "#181825";
  ctx.fillRect(0, canvas.height - 42, canvas.width, 42);
  ctx.font = "14px 'Courier New', monospace";
  ctx.fillStyle = dim;
  ctx.fillText("  TrabajoIA · Informe generado automáticamente", pad, canvas.height - 14);

  // ── Download ──
  canvas.toBlob(blob => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (placa + "_informe.png").replace(/[^a-zA-Z0-9_.\-]/g, "_");
    a.click();
    URL.revokeObjectURL(a.href);
  }, "image/png");
};

/**
 * Abre el modal para agregar una nueva soluci├│n.
 * Llamado desde onclick en viewSoluciones.
 */
window.openAddSolucion = () => {
  modal = { type:"addSolucion", placa:"", falla:"", solucion:"", ics:"" };
  document.getElementById("placaModal").style.display = "flex";
  document.getElementById("placaModalInner").innerHTML =
    '<h2>\uD83D\uDCA1 Nueva soluci\u00F3n</h2><div class="msub">Registr\u00E1 una reparaci\u00F3n para referencia futura.</div>' +
    '<div class="fg">' +
      '<div class="field full"><label>Placa *</label><input value="" oninput="mset(\'placa\',this.value.toUpperCase())" placeholder="Ej: NM-B321, 17807-3M"></div>' +
      '<div class="field full"><label>Falla</label><textarea rows="2" oninput="mset(\'falla\',this.value)" placeholder="Ej: Consume 9mA, no da video"></textarea></div>' +
      '<div class="field full"><label>Soluci\u00F3n *</label><textarea rows="4" oninput="mset(\'solucion\',this.value)" placeholder="Ej: Reemplazar PD4402, reconstruir pistas entre PIN X y Y del ISL9538H"></textarea></div>' +
      '<div class="field full"><label>ICs involucrados (separados por coma)</label><input value="" oninput="mset(\'ics\',this.value)" placeholder="Ej: ISL9538H, PD4402"></div>' +
    '</div>' +
    '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="submitAddSolucion()">Guardar</button></div>';
};

/**
 * Env├şa el formulario para agregar una nueva soluci├│n.
 * Llamado desde onclick en el modal de nueva soluci├│n.
 */
window.submitAddSolucion = async () => {
  const m = modal; if (!m) return;
  if (!m.placa.trim()) { alert("Falta el modelo de placa"); return; }
  if (!m.solucion.trim()) { alert("Falta la solución"); return; }
  const icsList = m.ics.split(",").map(s => s.trim()).filter(Boolean);
  await apiFetch("/api/soluciones", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ placa: m.placa, falla: m.falla, solucion: m.solucion, ics: icsList })
  });
  closeModal();
  cargarSoluciones();
};

/**
 * Abre el modal para editar una soluci├│n existente.
 * @param {number} id - ID de la soluci├│n
 */
window.openEditSolucion = async (id) => {
  const r = await apiFetch("/api/soluciones");
  const d = await r.json();
  const s = (d.soluciones||[]).find(x => x.id === id);
  if (!s) return;
  let icsStr = "";
  try { const arr = JSON.parse(s.ics||"[]"); icsStr = Array.isArray(arr) ? arr.join(", ") : ""; } catch(e) {}
  modal = { type:"editSolucion", id: s.id, placa: s.placa, falla: s.falla||"", solucion: s.solucion||"", ics: icsStr };
  document.getElementById("placaModal").style.display = "flex";
  document.getElementById("placaModalInner").innerHTML =
    '<h2>\u270F\uFE0F Editar soluci\u00F3n</h2><div class="msub">Modific\u00E1 la soluci\u00F3n registrada.</div>' +
    '<div class="fg">' +
      '<div class="field full"><label>Placa *</label><input value="'+esc(s.placa)+'" oninput="mset(\'placa\',this.value.toUpperCase())"></div>' +
      '<div class="field full"><label>Falla</label><textarea rows="2" oninput="mset(\'falla\',this.value)">'+esc(s.falla||'')+'</textarea></div>' +
      '<div class="field full"><label>Soluci\u00F3n *</label><textarea rows="4" oninput="mset(\'solucion\',this.value)">'+esc(s.solucion||'')+'</textarea></div>' +
      '<div class="field full"><label>ICs involucrados (separados por coma)</label><input value="'+esc(icsStr)+'" oninput="mset(\'ics\',this.value)"></div>' +
    '</div>' +
    '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="submitEditSolucion()">\uD83D\uDCBE Guardar</button></div>';
};

/**
 * Env├şa el formulario para editar una soluci├│n existente.
 * Llamado desde onclick en el modal de edici├│n.
 */
window.submitEditSolucion = async () => {
  const m = modal; if (!m || m.type !== "editSolucion") return;
  if (!m.placa.trim()) { alert("Falta el modelo de placa"); return; }
  if (!m.solucion.trim()) { alert("Falta la solución"); return; }
  const icsList = m.ics.split(",").map(s => s.trim()).filter(Boolean);
  const r = await apiFetch("/api/soluciones", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ id: m.id, _action: "actualizar", placa: m.placa, falla: m.falla, solucion: m.solucion, ics: icsList })
  });
  const res = await r.json();
  if (res.ok) { closeModal(); cargarSoluciones(); }
  else { alert(res.error||"Error al guardar"); }
};
