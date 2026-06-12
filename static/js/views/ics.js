// ── JC-Sistema: Vista ICs (Circuitos Integrados) ──────────────
// Script regular — depende de window.modal, window.inventory, window.renderPlacas (boards.js)

// ── Estado ─────────────────────────────────────────────────
/** @type {Array} Cache de circuitos integrados */
let _icsCache = [];
/** @type {Array} Cache de mediciones para el modal de IC */
let _medCache = [];

// ── Helpers ────────────────────────────────────────────────

/**
 * Retorna la caja donde está una placa (desde inventory() de boards.js).
 * @param {string} placa
 * @returns {string}
 */
function getCajaForPlaca(placa) {
  const inv = typeof window.inventory === 'function' ? window.inventory() : [];
  const r = inv.find(x => {
    const N = s => (s||"").toString().toUpperCase().replace(/\s+/g," ").trim();
    return N(x.placa) === N(placa);
  });
  return r ? r.caja : '\u2014';
}

// ── ICs CRUD ──────────────────────────────────────────────

/**
 * Busca ICs por query (o carga todos).
 * @param {string} [q]
 */
window.fetchIcs = async function(q) {
  const url = q ? ("/api/ics?q=" + encodeURIComponent(q)) : "/api/ics/";
  try {
    const r = await apiFetch(url);
    const data = await r.json();
    _icsCache = data.circuitos || [];
  } catch(e) { _icsCache = []; }
  renderIcs();
};

/** Abre modal para agregar un IC nuevo. */
window.openAddIc = () => {
  window.modal = { type:"addIc", code:"", desc:"", placa:"", qty:"1" };
  renderIcs();
};

/** Guarda un IC nuevo vía API. */
window.submitAddIc = async () => {
  const m = window.modal;
  const code = (m.code||"").trim().toUpperCase();
  if (!code) { alert("Falta el c\u00f3digo del IC"); return; }
  const placa = (m.placa||"").trim().toUpperCase();
  if (!placa) { alert("Falta la placa donde est\u00e1 el IC"); return; }
  await apiFetch("/api/circuitos", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ codigo:code, descripcion:m.desc, placa, cantidad:parseInt(m.qty)||1 })
  });
  window.modal = null; document.getElementById("icsQ").value = code; fetchIcs();
};

/**
 * Abre modal para editar un IC existente.
 * @param {string} code
 */
window.openEditIc = (code) => {
  const items = _icsCache.filter(x => x.codigo === code);
  window.modal = {
    type:"editIc", code,
    desc: items.length ? items[0].descripcion : "",
    items: items.map(x => ({ id:x.id, placa:x.placa, qty:x.cantidad }))
  };
  renderIcs();
};

/** Guarda los cambios de un IC editado. */
window.submitEditIc = async () => {
  const m = window.modal; if (!m) return;
  const code = (m.code||"").trim().toUpperCase(); if (!code) return;
  for (const row of _icsCache.filter(x => x.codigo === code)) {
    await apiFetch("/api/circuitos", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({_method:"DELETE", id:row.id}) });
  }
  for (const item of (m.items||[])) {
    await apiFetch("/api/circuitos", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ codigo:code, descripcion:m.desc, placa:item.placa, cantidad:item.qty }) });
  }
  window.modal = null; fetchIcs();
};

/** Agrega una placa al IC en edición (modal editIc). */
window.addIcPlaca = () => {
  const m = window.modal; if (!m) return;
  const placa = prompt("N\u00b0 de placa donde est\u00e1 el IC:");
  if (!placa) return;
  const qty = parseInt(prompt("Cantidad:")||"1")||1;
  if (!m.items) m.items = [];
  const idx = m.items.findIndex(x => {
    const N = s => (s||"").toString().toUpperCase().replace(/\s+/g," ").trim();
    return N(x.placa) === N(placa);
  });
  if (idx >= 0) m.items[idx].qty += qty;
  else m.items.push({ id:null, placa:N(placa), qty });
  renderIcs();
};

/**
 * Quita una placa del IC en edición.
 * @param {number} idx
 */
window.removeIcPlaca = (idx) => {
  const m = window.modal; if (!m||!m.items) return;
  if (!confirm("Quitar esta placa del IC?")) return;
  m.items.splice(idx, 1); renderIcs();
};

/**
 * Elimina un IC completo (todas sus filas).
 * @param {string} code
 */
window.delIc = async (code) => {
  if (!confirm("Eliminar IC " + code + "?")) return;
  for (const row of _icsCache.filter(x => x.codigo === code)) {
    await apiFetch("/api/circuitos", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({_method:"DELETE", id:row.id}) });
  }
  fetchIcs();
};

/**
 * Abre modal con información detallada de un IC.
 * @param {string} codigo
 */
window.openIcInfo = (codigo) => {
  const items = _icsCache.filter(x => x.codigo === codigo);
  if (!items.length) { alert("No se encontr\u00f3 " + codigo); return; }
  window.modal = {
    type: "icInfo",
    codigo: codigo,
    desc: items[0].descripcion || "",
    info: items[0].info_detallada || "",
    editing: false
  };
  renderIcs();
};

/** Activa el modo edición de la info detallada del IC. */
window.editIcInfo = () => {
  if (!window.modal || window.modal.type !== "icInfo") return;
  window.modal.editing = true;
  renderIcs();
};

/** Cancela la edición de info detallada. */
window.cancelEditIcInfo = () => {
  if (!window.modal || window.modal.type !== "icInfo") return;
  const items = _icsCache.filter(x => x.codigo === window.modal.codigo);
  if (items.length) {
    window.modal.info = items[0].info_detallada || "";
    window.modal.editing = false;
  }
  renderIcs();
};

/** Guarda la info detallada del IC. */
window.submitIcInfo = async () => {
  if (!window.modal || window.modal.type !== "icInfo") return;
  const item = _icsCache.find(x => x.codigo === window.modal.codigo);
  if (!item) return;
  await apiFetch("/api/circuitos", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ id: item.id, info_detallada: window.modal.info, _action: "actualizar" })
  });
  _icsCache.forEach(x => { if (x.codigo === window.modal.codigo) x.info_detallada = window.modal.info; });
  window.modal.editing = false;
  renderIcs();
};

/**
 * Renderiza Markdown simple a HTML (usado en icInfo).
 * @param {string} txt
 * @returns {string}
 */
window.renderMd = (txt) => {
  if (!txt) return "";
  let h = txt.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  h = h.replace(/`([^`]+)`/g, "<code>$1</code>");
  h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/^## (.+)$/gm, '<h4 style="margin:16px 0 6px;color:var(--accent);font-size:14px">$1</h4>');
  h = h.replace(/^# (.+)$/gm, '<h3 style="margin:20px 0 8px;color:var(--accent);font-size:16px">$1</h3>');
  h = h.replace(/^- (.+)$/gm, '<li style="margin:2px 0">$1</li>');
  h = h.replace(/^\|(.+)\|$/gm, function(m) {
    const cells = m.slice(1,-1).split("|").map(c => c.trim());
    if (cells.every(c => /^-+$/.test(c))) return "";
    return "<tr><td style='padding:2px 8px;border:1px solid var(--border)'>" + cells.join("</td><td style='padding:2px 8px;border:1px solid var(--border)'>") + "</td></tr>";
  });
  h = h.replace(/((?:<li[^>]*>.*?<\/li>\s*)+)/g, '<ul style="margin:4px 0;padding-left:20px">$1</ul>');
  h = h.replace(/^---$/gm, '<hr style="margin:12px 0;border:none;border-top:1px solid var(--border)">');
  h = h.split("\n").map(l => {
    l = l.trim();
    if (!l) return "<br>";
    if (l.startsWith("<h") || l.startsWith("<ul") || l.startsWith("<li") || l.startsWith("<tr") || l.startsWith("<hr") || l.startsWith("</ul")) return l;
    return '<div style="line-height:1.6;margin:2px 0">'+l+'</div>';
  }).join("\n");
  return h;
};

// ── Render ICs ─────────────────────────────────────────────

/** Renderiza la lista de ICs o el modal IC activo. */
function renderIcs() {
  const inp = document.getElementById("icsQ");
  if (!inp) return;
  const term = inp.value;
  const mode = (document.getElementById("icsMode")||{}).value || "codigo";
  const out = document.getElementById("icsResults");
  const stat = document.getElementById("icsStat");
  const cc = document.getElementById("icsChangeCount");
  const Nterm = (function(s){ return (s||"").toString().toUpperCase().replace(/\s+/g," ").trim(); })(term);
  const esc = function(s){ const d=document.createElement("div"); d.textContent=s==null?"":s; return d.innerHTML; };

  if (cc) {
    const total = _icsCache.length;
    const unicos = new Set(_icsCache.map(x => x.codigo)).size;
    cc.textContent = unicos ? (unicos + " IC" + (unicos>1?"s":"") + " \u00B7 " + total + " ubic.") : "";
  }

  if (window.modal && ["addIc","editIc","mediciones","icInfo"].includes(window.modal.type)) { 
    if (window.modal.type === "mediciones") renderMediciones();
    else renderIcsModal();
    return; 
  }
  document.getElementById("placaModal").style.display = "none";

  if (!_icsCache.length) {
    out.innerHTML = '<div class="empty" style="text-align:center;padding:2rem;color:var(--muted)">Sin ICs cargados. Us\u00e1 <b>+ IC</b> para agregar.</div>';
    if (stat) stat.style.display = "none"; return;
  }

  let filtered = _icsCache;
  const infoMatched = new Set();
  if (Nterm) {
    if (mode === "todo") {
      filtered = _icsCache.filter(x => {
        const N = s => (s||"").toString().toUpperCase().replace(/\s+/g," ").trim();
        const byCodigo = N(x.codigo).includes(Nterm);
        const byDesc = N(x.descripcion||"").includes(Nterm);
        const byPlaca = N(x.placa).includes(Nterm);
        const byInfo = N(x.info_detallada||"").includes(Nterm);
        if (byInfo && !byCodigo && !byDesc && !byPlaca) infoMatched.add(x.codigo);
        return byCodigo || byDesc || byPlaca || byInfo;
      });
    } else if (mode === "codigo") {
      filtered = _icsCache.filter(x => {
        const N = s => (s||"").toString().toUpperCase().replace(/\s+/g," ").trim();
        return N(x.codigo).includes(Nterm);
      });
      if (!filtered.length) filtered = _icsCache.filter(x => {
        const N = s => (s||"").toString().toUpperCase().replace(/\s+/g," ").trim();
        return N(x.placa).includes(Nterm);
      });
    } else {
      filtered = _icsCache.filter(x => {
        const N = s => (s||"").toString().toUpperCase().replace(/\s+/g," ").trim();
        return N(x.descripcion||"").includes(Nterm);
      });
      if (!filtered.length) filtered = _icsCache.filter(x => {
        const N = s => (s||"").toString().toUpperCase().replace(/\s+/g," ").trim();
        return N(x.placa).includes(Nterm);
      });
    }
  }
  if (!filtered.length) {
    out.innerHTML = '<div class="empty" style="text-align:center;padding:2rem;color:var(--muted)">Nada coincide con <b>'+esc(term)+'</b></div>';
    if (stat) stat.style.display = "none"; return;
  }

  const map = new Map();
  filtered.forEach(r => {
    if (!map.has(r.codigo)) map.set(r.codigo, { codigo:r.codigo, desc:r.descripcion||"", items:[], info:r.info_detallada||"" });
    map.get(r.codigo).items.push({ placa:r.placa, qty:r.cantidad });
  });
  const groups = [...map.values()];

  if (stat) { stat.style.display = "block"; stat.textContent = groups.length + " IC"+(groups.length===1?"":"s"); }

  let html = "";
  groups.slice(0, 50).forEach(g => {
    let total = 0; g.items.forEach(x => total += x.qty);
    const rows = g.items.map(x => {
      const caja = getCajaForPlaca(x.placa);
      return '<tr><td class="caja">'+esc(x.placa)+'</td><td style="color:var(--text3);font-size:13px">'+esc(caja)+'</td><td style="text-align:right;font-weight:700">'+(x.qty)+'</td></tr>';
    }).join("");
    const infoBadge = infoMatched.has(g.codigo) ? '<span style="font-size:10px;margin-left:6px;padding:1px 6px;border-radius:4px;background:var(--accent);color:var(--card);vertical-align:middle">info</span>' : '';
    html += '<div class="card ics-card" style="margin-bottom:12px" data-codigo="'+g.codigo+'">' +
      '<div class="chead">' +
        '<div><div style="font-family:\'Courier New\',monospace;font-size:16px;font-weight:700;color:var(--accent)">'+(function hl(text, term){
          if (!term) return esc(text);
          const i = text.toUpperCase().indexOf(term.toUpperCase());
          if (i < 0) return esc(text);
          return esc(text.slice(0,i)) + "<mark>" + esc(text.slice(i,i+term.length)) + "</mark>" + esc(text.slice(i+term.length));
        })(g.codigo,Nterm)+infoBadge+
        '<button class="edit-placa" title="Editar IC" onclick="window.openEditIc(\''+g.codigo.replace(/'/g,"\\'")+'\')">\u270F\uFE0F</button>'+
        '<button class="edit-placa" style="color:var(--danger)" title="Eliminar IC" onclick="window.delIc(\''+g.codigo.replace(/'/g,"\\'")+'\')">\u2715</button></div>'+
        (g.desc?'<div style="font-size:12px;color:var(--muted);margin-top:3px">'+(function hl(text,term){if(!term)return esc(text);const i=text.toUpperCase().indexOf(term.toUpperCase());if(i<0)return esc(text);return esc(text.slice(0,i))+"<mark>"+esc(text.slice(i,i+term.length))+"</mark>"+esc(text.slice(i+term.length));})(g.desc,Nterm)+'</div>':'')+
        '</div>' +
        '<div style="display:flex;gap:6px">'+
          '<span style="font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px;background:var(--okbg);color:var(--success)">Stock: '+total+'</span>'+
          '<button class="tbtn" style="font-size:11px" onclick="window.openMediciones(\''+g.codigo.replace(/'/g,"\\'")+'\',\''+esc(g.desc)+'\')">\uD83D\uDCCF Medir</button>'+
          '<button class="tbtn" style="font-size:11px" onclick="window.openIcInfo(\''+g.codigo.replace(/'/g,"\\'")+'\')">\uD83D\uDCD6 M\u00E1s info</button>'+
        '</div>'+
      '</div>'+
      '<table><thead><tr><th>Placa</th><th>Caja</th><th style="text-align:right">Cant</th></tr></thead><tbody>'+rows+'</tbody></table>'+
    '</div>';
  });
  if (groups.length > 50) html += '<div class="empty" style="padding:16px">Mostrando 50 ICs. Afin\u00e1 la b\u00fasqueda.</div>';
  out.innerHTML = html;
}
window.renderIcs = renderIcs;

/** Renderiza el modal activo de ICs (addIc, editIc, icInfo). */
function renderIcsModal() {
  const m = window.modal; let h = "";
  const esc = function(s){ const d=document.createElement("div"); d.textContent=s==null?"":s; return d.innerHTML; };
  if (m.type === "addIc") {
    h = '<h2>Agregar IC</h2><div class="msub">Circuito integrado en una placa.</div>' +
      '<div class="fg">' +
        '<div class="field full"><label>C\u00f3digo IC *</label><input value="'+esc(m.code)+'" oninput="mset(\'code\',this.value)" placeholder="Ej: BQ24735"></div>' +
        '<div class="field full"><label>Descripci\u00f3n</label><input value="'+esc(m.desc)+'" oninput="mset(\'desc\',this.value)" placeholder="Ej: Cargador bater\u00eda"></div>' +
        '<div class="field full"><label>Placa donde est\u00e1 *</label><input list="ics-placas-list" value="'+esc(m.placa)+'" oninput="mset(\'placa\',this.value)" placeholder="Ej: NM-C121"></div>' +
        '<div class="field"><label>Cantidad</label><input type="number" min="1" value="'+esc(m.qty)+'" oninput="mset(\'qty\',this.value)"></div>' +
      '</div><datalist id="ics-placas-list">'+(typeof window.inventory==='function'?[...new Set(window.inventory().map(r=>r.placa).filter(Boolean))].map(p=>'<option value="'+esc(p)+'">').join(""):'')+'</datalist>' +
      '<div class="macts"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="submitAddIc()">Agregar</button></div>';
  } else if (m.type === "editIc") {
    const rows = (m.items||[]).map((x,i) =>
      '<tr><td>'+esc(x.placa)+'</td><td style="text-align:right;font-weight:700">'+(x.qty)+'</td>'+
      '<td><button class="mv" style="color:var(--danger)" onclick="window.removeIcPlaca('+i+')">\u2715</button></td></tr>'
    ).join("");
    h = '<h2>Editar IC</h2><div class="msub">C\u00f3digo <b style="color:var(--accent)">'+esc(m.code)+'</b></div>' +
      '<div class="fg"><div class="field full"><label>Descripci\u00f3n</label><input value="'+esc(m.desc)+'" oninput="mset(\'desc\',this.value)" placeholder="Ej: Cargador bater\u00eda"></div></div>' +
      '<div style="margin:12px 0"><div style="font-size:12px;font-weight:600;color:var(--text3);margin-bottom:6px">Placas donde aparece:</div>'+
      '<table><thead><tr><th>Placa</th><th>Cant</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div>'+
      '<div class="macts" style="justify-content:space-between">'+
        '<button class="tbtn" onclick="window.addIcPlaca()">+ Agregar placa</button>'+
        '<div style="display:flex;gap:10px"><button class="bcancel" onclick="closeModal()">Cancelar</button><button class="bok" onclick="submitEditIc()">Guardar</button></div>'+
      '</div>';
  } else if (m.type === "icInfo") {
    if (m.editing) {
      h = '<h2>📖 Info: ' + esc(m.codigo) + '</h2>' +
        '<div class="msub">Editando informaci\u00f3n detallada.</div>' +
        '<div class="field" style="margin:12px 0"><label>Contenido (Markdown)</label>' +
        '<textarea oninput="mset(\'info\',this.value)" style="width:100%;height:400px;font-family:monospace;font-size:13px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg2);color:var(--text);resize:vertical">'+esc(m.info)+'</textarea></div>' +
        '<div class="macts"><button class="bcancel" onclick="cancelEditIcInfo()">Cancelar</button>' +
        '<button class="bok" onclick="submitIcInfo()">Guardar</button></div>';
    } else {
      const hasInfo = m.info && m.info.trim();
      h = '<h2>📖 ' + esc(m.codigo) + '</h2>' +
        (m.desc ? '<div class="msub" style="margin-bottom:12px">' + esc(m.desc) + '</div>' : '') +
        (hasInfo ? '<div style="max-height:500px;overflow-y:auto;padding:12px;background:var(--bg2);border-radius:8px;font-size:13px;line-height:1.6">' + window.renderMd(m.info) + '</div>' :
          '<div class="empty" style="text-align:center;padding:2rem;color:var(--muted)">Sin informaci\u00f3n detallada.</div>') +
        '<div class="macts" style="margin-top:12px">' +
          '<button class="tbtn" onclick="editIcInfo()">\u270F\uFE0F Editar info</button>' +
          '<button class="bcancel" onclick="closeModal()">Cerrar</button></div>';
    }
  }
  document.getElementById("placaModal").style.display = "flex";
  const innerEl = document.getElementById("placaModalInner");
  if (m.type === "icInfo") innerEl.classList.add("modal-wide");
  else innerEl.classList.remove("modal-wide");
  innerEl.innerHTML = h;
}

// ── Mediciones de IC (modal específico) ────────────────────

/**
 * Carga mediciones para un IC+placa desde la API.
 * @param {string} codigo
 * @param {string} [placa]
 * @returns {Promise<Array>}
 */
async function fetchMediciones(codigo, placa) {
  let url = "/api/mediciones?";
  if (codigo && placa) url += "codigo="+encodeURIComponent(codigo)+"&placa="+encodeURIComponent(placa);
  else if (codigo) url += "q="+encodeURIComponent(codigo);
  else url += "q="+encodeURIComponent(codigo||"");
  try {
    const r = await apiFetch(url);
    const data = await r.json();
    _medCache = data.mediciones || [];
  } catch(e) { _medCache = []; }
  return _medCache;
}

/**
 * Abre el modal de mediciones para un IC específico.
 * @param {string} codigo
 * @param {string} desc
 */
window.openMediciones = async (codigo, desc) => {
  const items = _icsCache.filter(x => x.codigo === codigo);
  const placas = [...new Set(items.map(x => x.placa))];
  await fetchMediciones(codigo, placas[0]||"");
  window.modal = { type:"mediciones", codigo, desc, placas, placaActual: placas[0]||"", newPin:"", newNombre:"", newValor:"", newNotas:"" };
  renderMediciones();
};

/** Renderiza el modal de mediciones para un IC. */
async function renderMediciones() {
  const m = window.modal; if (!m) return;
  const meds = _medCache;
  const esc = function(s){ const d=document.createElement("div"); d.textContent=s==null?"":s; return d.innerHTML; };

  let h = '<h2>\uD83D\uDCCF Mediciones</h2><div class="msub">IC <b style="color:var(--accent)">'+esc(m.codigo)+'</b> · '+(m.desc||'sin desc')+'</div>';

  if (m.placas.length > 1) {
    h += '<div style="margin-bottom:12px"><select onchange="window.cambiarPlacaMed(this.value)" style="padding:8px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font-size:14px">';
    m.placas.forEach(p => {
      h += '<option value="'+esc(p)+'"'+(p===m.placaActual?' selected':'')+'>'+esc(p)+'</option>';
    });
    h += '</select></div>';
  }

  if (meds.length === 0) {
    h += '<div class="empty" style="padding:12px;color:var(--muted)">Sin mediciones registradas para '+esc(m.codigo)+' en '+esc(m.placaActual)+'.</div>';
  } else {
    h += '<table><thead><tr><th>Pin</th><th>Nombre</th><th>Valor esperado</th><th>Notas</th><th></th></tr></thead><tbody>';
    meds.forEach(x => {
      h += '<tr><td style="font-family:\'Courier New\',monospace;font-weight:700">'+esc(x.pin)+'</td>'+
        '<td>'+esc(x.nombre)+'</td>'+
        '<td style="font-family:\'Courier New\',monospace;color:var(--accent);font-weight:600">'+esc(x.valor_esperado)+'</td>'+
        '<td style="font-size:12px;color:var(--text3)">'+esc(x.notas)+'</td>'+
        '<td><button class="btn-delete" onclick="window.eliminarMedicion('+x.id+')">\u2715</button></td></tr>';
    });
    h += '</tbody></table>';
  }

  h += '<div style="margin-top:14px;border-top:1px solid var(--border);padding-top:14px">';
  h += '<div style="font-size:13px;font-weight:600;color:var(--text3);margin-bottom:8px">+ Agregar medici\u00F3n</div>';
  h += '<div class="fg" style="grid-template-columns:1fr 1fr 1fr 1fr auto">'+
    '<div class="field"><label>Pin</label><input value="'+esc(m.newPin)+'" oninput="mset(\'newPin\',this.value.toUpperCase())" placeholder="Ej: 1"></div>'+
    '<div class="field"><label>Nombre</label><input value="'+esc(m.newNombre)+'" oninput="mset(\'newNombre\',this.value)" placeholder="Ej: ACIN"></div>'+
    '<div class="field"><label>Valor esperado</label><input value="'+esc(m.newValor)+'" oninput="mset(\'newValor\',this.value)" placeholder="Ej: 19V"></div>'+
    '<div class="field"><label>Notas</label><input value="'+esc(m.newNotas)+'" oninput="mset(\'newNotas\',this.value)" placeholder="Ej: Medir con cargador"></div>'+
    '<button class="bok" style="align-self:end;padding:10px 14px" onclick="window.agregarMedicion()">+</button>'+
  '</div></div>';

  h += '<div class="macts" style="margin-top:14px"><button class="bcancel" onclick="closeModal()">Cerrar</button></div>';
  document.getElementById("placaModal").style.display = "flex";
  const inner = document.getElementById("placaModalInner");
  inner.classList.add("modal-wide");
  inner.innerHTML = h;
}

/**
 * Cambia la placa activa en el modal de mediciones y recarga.
 * @param {string} placa
 */
window.cambiarPlacaMed = async (placa) => {
  if (!window.modal) return;
  window.modal.placaActual = placa;
  await fetchMediciones(window.modal.codigo, placa);
  renderMediciones();
};

/** Agrega una medición desde el modal de IC. */
window.agregarMedicion = async () => {
  const m = window.modal; if (!m) return;
  const pin = (m.newPin||"").trim().toUpperCase();
  if (!pin) { alert("Falta el número de pin"); return; }
  const nombre = (m.newNombre||"").trim();
  const valor = (m.newValor||"").trim();
  const notas = (m.newNotas||"").trim();
  await apiFetch("/api/mediciones", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ codigo: m.codigo, placa: m.placaActual, pin, nombre, valor_esperado: valor, notas })
  });
  m.newPin = ""; m.newNombre = ""; m.newValor = ""; m.newNotas = "";
  await fetchMediciones(m.codigo, m.placaActual);
  renderMediciones();
};

/**
 * Elimina una medición desde el modal de IC o desde la vista general.
 * @param {number} id
 */
window.eliminarMedicion = async (id) => {
  if (!confirm("Eliminar esta medici\u00F3n?")) return;
  await apiFetch("/api/mediciones", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ _method: "DELETE", id })
  });
  if (window.modal && window.modal.type === "mediciones") {
    await fetchMediciones(window.modal.codigo, window.modal.placaActual);
    renderMediciones();
  } else {
    if (typeof window.cargarMediciones === 'function') window.cargarMediciones();
  }
};
