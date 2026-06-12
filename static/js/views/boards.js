// ── JC-Sistema: Vista Placas / Boards (Firebase) ──────────────
// ES Module — importa Firebase vía CDN

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import { getFirestore, doc, setDoc, onSnapshot, serverTimestamp, deleteField, collection, getDocs }
  from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

// ── Firebase ──────────────────────────────────────────────
const firebaseConfig = {
  apiKey: "AIzaSyCBc9neFG4zvt2GwgEzDqug6NMZhLjSNAo",
  authDomain: "repuestos-c3ee7.firebaseapp.com",
  projectId: "repuestos-c3ee7",
  storageBucket: "repuestos-c3ee7.firebasestorage.app",
  messagingSenderId: "996451458607",
  appId: "1:996451458607:web:6b1ce596397c7ef95eb0da"
};
const fbApp = initializeApp(firebaseConfig);
const fdb = getFirestore(fbApp);
const ovDoc = doc(fdb, "placas_stock", "overrides");
const colRef = collection(fdb, "placas_stock");

// ── Datos base (de PLACAS_DATA, cargado vía placas-data.js) ─
const recs = PLACAS_DATA.records;
const N = s => (s||"").toString().toUpperCase().replace(/\s+/g," ").trim();
const L = s => N(s).replace(/[\s\-]/g,"");
recs.forEach(r => { r._p = N(r.placa); r._pl = L(r.placa); r._m = N(r.modelo); });
const byKey = Object.fromEntries(recs.map(r => [r.key, r]));

// ── Estado (expuesto en window para que ics.js etc. lo compartan) ─
window._S = { items:{}, added:{}, cajas:[] };
window._fbReady = false;
window.modal = null;

// Escaping local (copia de window.esc por consistencia)
const esc = s => { const d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; };
const todayStr = () => new Date().toISOString().slice(0,10);

// ── Inventario combinado ──────────────────────────────────
function effCant(r){ const o=window._S.items[r.key]; return (o&&o.cant!=null)?o.cant:r.cant; }
function effScrap(r){ const o=window._S.items[r.key]; return (o&&o.scrap!=null)?o.scrap:r.scrap; }
function effNote(r){ const o=window._S.items[r.key]; return (o&&o.note!=null)?o.note:''; }
function editedBase(r){ const o=window._S.items[r.key]; return (o&&(o.cant!=null||o.scrap!=null||o.note!=null)); }

/**
 * Devuelve el inventario completo combinando datos base + overrides + agregados.
 * @returns {Array}
 */
window.inventory = function() {
  const list = recs.map(r => ({
    key: r.key, placa: r.placa, caja: r.caja, marca: r.marca, modelo: r.modelo,
    cant: effCant(r), scrap: effScrap(r), note: effNote(r), base: true, edited: editedBase(r)
  }));
  for (const [k, v] of Object.entries(window._S.added||{})) {
    if (!v) continue;
    list.push({ key:k, placa:v.placa||"", caja:v.caja||"", marca:v.marca||"", modelo:v.modelo||"",
      cant:v.cant||0, scrap:!!v.scrap, note:v.note||"", base:false, edited:true });
  }
  return list;
};

/**
 * Devuelve lista ordenada de todas las cajas disponibles.
 * @returns {string[]}
 */
window.allCajas = function() {
  const set = new Set(PLACAS_DATA.cajas);
  (window._S.cajas||[]).forEach(c => set.add(c));
  Object.values(window._S.added||{}).forEach(v => { if(v&&v.caja) set.add(v.caja); });
  return [...set].sort((a,b)=>a.localeCompare(b,'es',{numeric:true}));
};

/**
 * Cantidad de cambios pendientes (items editados + agregados + edits de marca/modelo).
 * @returns {number}
 */
window.changeCount = function() {
  let n = Object.keys(window._S.items||{}).filter(k => byKey[k] && editedBase(byKey[k])).length;
  n += Object.keys(window._S.added||{}).length;
  n += Object.keys(window._S.edits||{}).length;
  return n;
};

// ── Persistencia Firebase ─────────────────────────────────
async function fbSet(partial) {
  try { await setDoc(ovDoc, Object.assign({updatedAt:serverTimestamp()}, partial), {merge:true}); }
  catch(e) { console.error(e); }
}

function setBase(key, patch) {
  window._S.items[key] = Object.assign({}, window._S.items[key], patch);
  fbSet({items:{[key]:window._S.items[key]}});
}

function setAdded(key, patch) {
  window._S.added[key] = Object.assign({}, window._S.added[key], patch);
  fbSet({added:{[key]:window._S.added[key]}});
}

function setCant(key, nv) {
  nv = Math.max(0, parseInt(nv)||0);
  byKey[key] ? setBase(key, {cant:nv}) : setAdded(key, {cant:nv});
}

function setScrap(key, v) {
  byKey[key] ? setBase(key, {scrap:v}) : setAdded(key, {scrap:v});
}

function setNote(key, txt) {
  txt = (txt||"").trim();
  byKey[key] ? setBase(key, {note:txt}) : setAdded(key, {note:txt});
}

function ensureCaja(name) {
  name = name.trim(); if (!name) return;
  if (!window.allCajas().includes(name)) { window._S.cajas = [...(window._S.cajas||[]), name]; fbSet({cajas:window._S.cajas}); }
}

// ── Editar marca/modelo ────────────────────────────────
function getEdit(placa) {
  return (window._S.edits||{})[N(placa)] || {};
}

function setEdit(placa, data) {
  const key = N(placa);
  if (!window._S.edits) window._S.edits = {};
  window._S.edits[key] = data;
  fbSet({edits:{[key]:data}});
}

// ── Acciones (expuestas en window para onclick) ───────────

/**
 * Ajusta stock de una placa (suma/resta o valor directo).
 * @param {string} key
 * @param {number} delta
 * @param {number|string} [val]
 */
window.adj = (key, delta, val) => {
  const inv = window.inventory(); const r = inv.find(x => x.key === key);
  let cur = r ? r.cant : 0;
  let nv = (val !== undefined && val !== "") ? parseInt(val) : cur + delta;
  setCant(key, nv);
  renderPlacas();
};

/**
 * Toggle scrap en una placa.
 * @param {string} key
 */
window.togScrap = (key) => {
  const inv = window.inventory(); const r = inv.find(x => x.key === key);
  setScrap(key, !r.scrap);
  renderPlacas();
};

/**
 * Elimina un registro agregado.
 * @param {string} key
 */
window.delAdded = (key) => {
  if (!confirm("Eliminar este registro agregado?")) return;
  delete window._S.added[key];
  fbSet({added:{[key]:deleteField()}});
  renderPlacas();
};

/**
 * Abre modal de editar marca/modelo para una placa.
 * @param {string} placa
 */
window.openEdit = (placa) => {
  const e = getEdit(placa);
  const inv = window.inventory();
  const items = inv.filter(r => N(r.placa) === N(placa));
  const first = items[0];
  window.modal = {
    type: "edit",
    placa: first ? first.placa : placa,
    marca: e.marca || (first ? first.marca : ""),
    modelo: e.modelo || "",
  };
  renderPlacas();
};

/** Guarda la edición de marca/modelo. */
window.submitEdit = () => {
  const m = window.modal; if (!m) return;
  const placa = (m.placa||"").trim();
  if (!placa) { alert("Falta la placa"); return; }
  const data = {};
  if (m.marca && m.marca.trim()) data.marca = m.marca.trim();
  if (m.modelo && m.modelo.trim()) data.modelo = m.modelo.trim();
  setEdit(placa, data);
  window.modal = null;
  renderPlacas();
};

// ── Modales (expuestos en window) ─────────────────────────

/** Abre modal para agregar placa nueva. */
window.openAddPlaca = () => { window.modal={type:"placa",placa:"",marca:"",modelo:"",caja:"",cant:"1",scrap:false}; renderPlacas(); };

/** Abre modal para crear caja nueva. */
window.openAddCaja = () => { window.modal={type:"caja",nombre:""}; renderPlacas(); };

/**
 * Abre modal para mover stock entre cajas.
 * @param {string} key
 */
window.openMove = (key) => {
  const r = window.inventory().find(x => x.key === key);
  window.modal={type:"move",srcKey:key,placa:r.placa,srcCaja:r.caja,max:r.cant,dest:"",qty:String(Math.min(1,r.cant)||1)};
  renderPlacas();
};

/**
 * Abre modal para editar nota de una placa.
 * @param {string} key
 */
window.openNote = (key) => {
  const r = window.inventory().find(x => x.key === key);
  window.modal={type:"note",key,placa:r.placa,caja:r.caja,note:r.note||""};
  renderPlacas();
};

/** Cierra el modal activo y refresca la vista de placas. */
window.closeModal = () => {
  window.modal = null;
  document.getElementById("placaModal").style.display = "none";
  document.getElementById("refModal").style.display = "none";
  renderPlacas();
};

/**
 * Setter genérico para propiedad del modal activo.
 * @param {string} k
 * @param {*} v
 */
window.mset = (k,v) => { if(window.modal) window.modal[k]=v; };

/** Guarda una placa nueva (modal type:"placa"). */
window.submitAddPlaca = () => {
  const m = window.modal; const placa = (m.placa||"").trim();
  if (!placa) { alert("Falta el n\u00famero de placa"); return; }
  if (!(m.caja||"").trim()) { alert("Eleg\u00ed o escrib\u00ed una caja"); return; }
  ensureCaja(m.caja.trim());
  const k = "ADD_"+Date.now().toString(36)+Math.random().toString(36).slice(2,7);
  window._S.added[k] = { placa, marca:(m.marca||"").trim(), modelo:(m.modelo||"").trim(), caja:m.caja.trim(),
    cant:Math.max(0,parseInt(m.cant)||0), scrap:!!m.scrap };
  fbSet({added:{[k]:window._S.added[k]}});
  window.modal = null;
  document.getElementById("placaQ").value = placa;
  renderPlacas();
};

/** Guarda una caja nueva (modal type:"caja"). */
window.submitAddCaja = () => {
  const name = (window.modal.nombre||"").trim();
  if (!name) { alert("Escrib\u00ed un nombre"); return; }
  if (window.allCajas().includes(name)) { alert("Esa caja ya existe"); return; }
  ensureCaja(name); window.modal = null; renderPlacas();
};

/** Ejecuta el movimiento de stock entre cajas (modal type:"move"). */
window.submitMove = () => {
  const m = window.modal; let qty = parseInt(m.qty)||0; const dest = (m.dest||"").trim();
  const src = window.inventory().find(x => x.key === m.srcKey);
  if (!dest) { alert("Eleg\u00ed la caja destino"); return; }
  if (dest === src.caja) { alert("La caja destino debe ser distinta"); return; }
  if (qty <= 0) { alert("Cantidad inv\u00e1lida"); return; }
  if (qty > src.cant) qty = src.cant;
  ensureCaja(dest);
  setCant(m.srcKey, src.cant - qty);
  const destRec = window.inventory().find(x => x.placa===src.placa && x.caja===dest);
  if (destRec) setCant(destRec.key, destRec.cant + qty);
  else { const k="ADD_"+Date.now().toString(36)+Math.random().toString(36).slice(2,7);
    window._S.added[k]={placa:src.placa,marca:src.marca,modelo:src.modelo,caja:dest,cant:qty,scrap:false};
    fbSet({added:{[k]:window._S.added[k]}}); }
  window.modal=null; renderPlacas();
};

/** Guarda la nota de una placa (modal type:"note"). */
window.submitNote = () => { const m=window.modal; setNote(m.key, m.note); window.modal=null; renderPlacas(); };

// ── Respaldos ─────────────────────────────────────────────

/** Descarga un archivo JSON con el estado actual del inventario. */
window.backupDownload = () => {
  const payload = { tipo:"respaldo_placas", fecha:new Date().toISOString(), estado:{ items:window._S.items, added:window._S.added, cajas:window._S.cajas } };
  const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"text/plain;charset=utf-8"})); a.download="respaldo_placas_"+todayStr()+".json"; a.click(); URL.revokeObjectURL(a.href);
};

/** Restaura inventario desde un archivo JSON seleccionado por el usuario. */
window.restoreFile = () => {
  const inp=document.createElement("input"); inp.type="file"; inp.accept="application/json,.json";
  inp.onchange=()=>{ const f=inp.files[0]; if(!f) return; const rd=new FileReader();
    rd.onload=async()=>{ try {
      const data=JSON.parse(rd.result); const e=data.estado||data;
      if(!e||typeof e!=="object"||(!e.items&&!e.added&&!e.cajas)) { alert("Archivo no v\u00e1lido"); return; }
      if(!confirm("Restaurar este respaldo? Reemplaza el inventario actual.")) return;
      window._S={items:e.items||{},added:e.added||{},cajas:e.cajas||[],edits:e.edits||{}};
      await setDoc(ovDoc,{items:window._S.items,added:window._S.added,cajas:window._S.cajas,edits:window._S.edits,updatedAt:serverTimestamp()});
      renderPlacas(); if (typeof window.fetchIcs === 'function') window.fetchIcs();
    } catch(err) { alert("No se pudo leer el archivo"); } };
    rd.readAsText(f); };
  inp.click();
};

/** Lista los snapshots diarios desde Firebase. @returns {Promise<Array>} */
async function listSnapshots() {
  const qs=await getDocs(colRef); const out=[];
  qs.forEach(d=>{ if(d.id.startsWith("snap_")) out.push({id:d.id, fecha:d.id.slice(5), data:d.data()}); });
  out.sort((a,b)=>b.fecha.localeCompare(a.fecha));
  return out;
}

/** Abre el modal de respaldos con la lista de snapshots. */
window.openBackups = async () => {
  window.modal={type:"backups",loading:true,list:[]}; renderPlacas();
  try { window.modal.list=await listSnapshots(); } catch(e){ window.modal.error=e.code||e.message; }
  if (window.modal && window.modal.type==="backups") window.modal.loading=false; renderPlacas();
};

/**
 * Restaura un snapshot específico por ID.
 * @param {string} id
 */
window.restoreSnapshot = async (id) => {
  const snaps=window.modal.list||[]; const s=snaps.find(x=>x.id===id); if (!s) return;
  if (!confirm("Restaurar respaldo del "+s.fecha+"?")) return;
  window._S={items:s.data.items||{},added:s.data.added||{},cajas:s.data.cajas||[],edits:s.data.edits||{}};
  try { await setDoc(ovDoc,{items:window._S.items,added:window._S.added,cajas:window._S.cajas,edits:window._S.edits,updatedAt:serverTimestamp()}); } catch(e){console.error(e);}
  window.modal=null; renderPlacas(); if (typeof window.fetchIcs === 'function') window.fetchIcs();
};

/** Exporta el inventario como CSV y lo descarga. */
window.exportCSV = () => {
  let c="Placa,Caja,Marca,Modelo,Stock,Scrap,Nuevo\n";
  window.inventory().forEach(r=>{
    const f=s=>"\""+(s||"").toString().replace(/"/g,'""')+"\"";
    c+=[f(r.placa),f(r.caja),f(r.marca),f(r.modelo),r.cant||0,r.scrap?"SI":"NO",r.base?"":"SI"].join(",")+"\n";
  });
  const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([c],{type:"text/csv;charset=utf-8"})); a.download="inventario_placas.csv"; a.click(); URL.revokeObjectURL(a.href);
};

// ── Búsqueda (helper interno) ─────────────────────────────
function hl(text, term) {
  if (!term) return esc(text);
  const i = text.toUpperCase().indexOf(term.toUpperCase());
  if (i < 0) return esc(text);
  return esc(text.slice(0,i)) + "<mark>" + esc(text.slice(i,i+term.length)) + "</mark>" + esc(text.slice(i+term.length));
}

// ── Render ────────────────────────────────────────────────

/** Renderiza la vista de placas (listado o modal según estado). */
function renderPlacas() {
  const inp = document.getElementById("placaQ");
  const modeSel = document.getElementById("placaMode");
  if (!inp) return;
  const term = inp.value;
  const mode = modeSel ? modeSel.value : "todo";
  const out = document.getElementById("placaResults");
  const stat = document.getElementById("placaStat");
  const cc = document.getElementById("placaChangeCount");
  const Nterm = N(term);

  // Change count
  if (cc) cc.textContent = window.changeCount() ? ("\u270E "+window.changeCount()+" cambio"+(window.changeCount()>1?"s":"")) : "";

  // Modal (solo para tipos de placas)
  if (window.modal && ["placa","caja","move","note","backups","edit"].includes(window.modal.type)) { renderModal(); return; }
  document.getElementById("placaModal").style.display = "none";

  if (!window._fbReady) {
    out.innerHTML = '<div class="empty" style="text-align:center;padding:2rem;color:var(--muted)">⏳ Cargando inventario desde Firebase…</div>';
    if (stat) stat.style.display = "none";
    return;
  }

  if (!Nterm) {
    out.innerHTML = '<div class="empty" style="text-align:center;padding:2rem;color:var(--muted)">Escrib\u00ed para buscar placas…</div>';
    if (stat) stat.style.display = "none";
    return;
  }

  const inv = window.inventory();
  // Normalize for search
  inv.forEach(r => { r._p = N(r.placa); r._pl = L(r.placa); r._m = N(r.modelo); });

  const mP = r => r._p.includes(Nterm) || r._pl.includes(L(term));
  const mM = r => r._m.includes(Nterm);
  const f = mode === "placa" ? mP : mode === "modelo" ? mM : (r => mP(r) || mM(r));
  let hit = inv.filter(f);
  hit.sort((a,b) => {
    const tl = L(term);
    const ax = a._p === tl ? 0 : a._p.startsWith(tl) ? 1 : 2;
    const bx = b._p === tl ? 0 : b._p.startsWith(tl) ? 1 : 2;
    return ax - bx;
  });

  if (!hit.length) {
    out.innerHTML = '<div class="empty" style="text-align:center;padding:2rem;color:var(--muted)">Nada coincide con <b>' + esc(term) + '</b></div>';
    if (stat) stat.style.display = "none";
    return;
  }

  // Group by placa
  const map = new Map();
  hit.forEach(r => {
    const k = N(r.placa);
    if (!map.has(k)) map.set(k, { placa: r.placa, marca: r.marca, items: [] });
    const g = map.get(k); g.items.push(r);
    if (!g.marca && r.marca) g.marca = r.marca;
  });
  const groups = [...map.values()];

  if (stat) {
    stat.style.display = "block";
    stat.textContent = groups.length + " placa" + (groups.length === 1 ? "" : "s") + " · " + hit.length + " ubicaci\u00F3n" + (hit.length === 1 ? "" : "es");
  }

  let html = "";
  groups.slice(0, 30).forEach(g => {
    let ok = 0, sc = 0, anyScrap = false;
    g.items.forEach(r => { const c = r.cant||0; if (r.scrap) { sc += c; anyScrap = true; } else ok += c; });
    const edit = getEdit(g.placa);
    const models = edit.modelo ? [edit.modelo] : [...new Set(g.items.map(r => r.modelo).filter(Boolean))];
    const chips = models.length
      ? models.map(m => '<span class="chip' + (Nterm && m.toUpperCase().includes(Nterm) ? ' hit' : '') + '">' + hl(m, Nterm) + '</span>').join("")
      : '<span class="chip">Sin modelo</span>';

    const rows = g.items.map(r => {
      const ed = r.edited ? ' ed' : '';
      return '<tr class="' + (r.scrap ? 'rscrap' : '') + '">' +
        '<td class="caja">' + esc(r.caja) + (r.scrap ? ' <span class="tag scrap">scrap</span>' : '') + (!r.base ? ' <span class="tag new">nueva</span>' : '') +
        (r.note ? '<div class="note-line">📝 ' + esc(r.note) + '</div>' : '') +
        '</td>' +
        '<td class="mdl" style="font-size:12.5px;color:var(--text3)">' + esc(r.modelo||'—') + '</td>' +
        '<td><div class="ctl">' +
          '<button class="step" onclick="window.adj(\'' + r.key + '\',-1)">−</button>' +
          '<input class="stk' + ed + '" type="number" min="0" value="' + (r.cant||0) + '" onchange="window.adj(\'' + r.key + '\',0,this.value)">' +
          '<button class="step" onclick="window.adj(\'' + r.key + '\',1)">+</button>' +
          '<button class="mv" title="Mover stock a otra caja" onclick="window.openMove(\'' + r.key + '\')">⇄</button>' +
          '<button class="mv nt' + (r.note ? ' has' : '') + '" title="' + (r.note ? 'Editar nota' : 'Agregar nota') + '" onclick="window.openNote(\'' + r.key + '\')">📝</button>' +
          '<span class="sc-tg' + (r.scrap ? ' on' : '') + '" onclick="window.togScrap(\'' + r.key + '\')" title="Marcar/desmarcar scrap">scrap</span>' +
          (!r.base ? '<button class="mv" style="color:var(--danger)" title="Eliminar registro" onclick="window.delAdded(\'' + r.key + '\')">✕</button>' : '') +
        '</div></td></tr>';
    }).join("");

    html += '<div class="card' + (anyScrap && ok === 0 ? ' only-scrap' : '') + '" style="margin-bottom:12px">' +
      '<div class="chead">' +
        '<div><div style="font-family:\'Courier New\',monospace;font-size:16px;font-weight:700;color:var(--accent)">' + hl(g.placa, Nterm) + '<button class="edit-placa" title="Editar marca / modelo" onclick="window.openEdit(\'' + g.placa.replace(/'/g,"\\'") + '\')">✏️</button></div>' +
        '<div style="font-size:12px;color:var(--muted);margin-top:3px">' + ((edit.marca || g.marca) ? '<b>' + esc(edit.marca || g.marca) + '</b> · ' : '') + g.items.length + ' caja' + (g.items.length > 1 ? 's' : '') + '</div></div>' +
        '<div style="display:flex;gap:6px">' +
          '<span style="font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px;background:var(--okbg);color:var(--success)">Stock: ' + ok + '</span>' +
          (anyScrap ? '<span style="font-size:12px;font-weight:700;padding:4px 10px;border-radius:999px;background:var(--redbg);color:var(--danger)">Scrap: ' + sc + '</span>' : '') +
        '</div>' +
      '</div>' +
      (chips ? '<div style="padding:10px 14px;border-bottom:1px solid var(--border);background:rgba(77,182,172,.05)"><div style="font-size:10px;text-transform:uppercase;letter-spacing:0.7px;color:var(--muted);margin-bottom:6px;font-weight:600">Modelos compatibles</div><div style="display:flex;flex-wrap:wrap;gap:5px">' + chips + '</div></div>' : '') +
      '<table><thead><tr><th>Caja</th><th class="cm" style="font-size:10.5px;color:var(--text3)">Modelo</th><th style="text-align:right">Stock · Mover · Scrap</th></tr></thead><tbody>' + rows + '</tbody></table>' +
    '</div>';
  });
  if (groups.length > 30) html += '<div class="empty" style="padding:16px">Mostrando 30 placas. Afin\u00e1 la b\u00fasqueda.</div>';
  out.innerHTML = html;
}
// Exponer para event listeners y otros modulos
window.renderPlacas = renderPlacas;

/** Renderiza el modal activo de placas (placa, caja, move, note, backups, edit). */
function renderModal() {
  const m = window.modal; let h = "";
  if (m.type === "placa") {
    h = '<h2>Agregar placa nueva</h2><div class="msub">Se guarda en Firebase para todos.</div>' +
      '<div class="fg">' +
        '<div class="field full"><label>N° de placa *</label><input value="' + esc(m.placa) + '" oninput="mset(\'placa\',this.value)" placeholder="Ej: NM-X999"></div>' +
        '<div class="field"><label>Marca</label><input value="' + esc(m.marca) + '" oninput="mset(\'marca\',this.value)" placeholder="HP, Lenovo…"></div>' +
        '<div class="field"><label>Cantidad</label><input type="number" min="0" value="' + esc(m.cant) + '" oninput="mset(\'cant\',this.value)"></div>' +
        '<div class="field full"><label>Modelo / notebooks compatibles</label><input value="' + esc(m.modelo) + '" oninput="mset(\'modelo\',this.value)" placeholder="Ej: Ideapad 320-15IKB"></div>' +
        '<div class="field full"><label>Caja *</label><input list="cajas-list" value="' + esc(m.caja) + '" oninput="mset(\'caja\',this.value)" placeholder="CAJA N° …"></div>' +
        '<div class="field full" style="flex-direction:row;align-items:center;gap:8px"><input type="checkbox" style="width:auto" ' + (m.scrap?'checked':'') + ' onchange="mset(\'scrap\',this.checked)"><label style="text-transform:none">Marcar como scrap</label></div>' +
      '</div><datalist id="cajas-list">' + window.allCajas().map(c => '<option value="' + esc(c) + '">').join("") + '</datalist>' +
      '<div class="macts"><button class="bcancel" onclick="window.closeModal()">Cancelar</button><button class="bok" onclick="window.submitAddPlaca()">Agregar</button></div>';
  } else if (m.type === "caja") {
    h = '<h2>Agregar caja nueva</h2><div class="msub">Quedar\u00e1 disponible para mover y cargar placas.</div>' +
      '<div class="field full"><label>Nombre de la caja</label><input value="' + esc(m.nombre) + '" oninput="mset(\'nombre\',this.value)" placeholder="Ej: CAJA N° 65" onkeydown="if(event.key===\'Enter\')window.submitAddCaja()"></div>' +
      '<div class="macts"><button class="bcancel" onclick="window.closeModal()">Cancelar</button><button class="bok" onclick="window.submitAddCaja()">Crear caja</button></div>';
  } else if (m.type === "move") {
    h = '<h2>Mover stock entre cajas</h2><div class="msub">Resta de una caja y suma en otra.</div>' +
      '<div class="movebox">Placa <b>' + esc(m.placa) + '</b><br>Desde <b>' + esc(m.srcCaja) + '</b> · disponible: <b>' + m.max + '</b></div>' +
      '<div class="fg">' +
        '<div class="field full"><label>Caja destino</label><input list="cajas-list" value="' + esc(m.dest) + '" oninput="mset(\'dest\',this.value)" placeholder="CAJA N° …"></div>' +
        '<div class="field"><label>Cantidad a mover</label><input type="number" min="1" max="' + m.max + '" value="' + esc(m.qty) + '" oninput="mset(\'qty\',this.value)"></div>' +
      '</div><datalist id="cajas-list">' + window.allCajas().map(c => '<option value="' + esc(c) + '">').join("") + '</datalist>' +
      '<div class="macts"><button class="bcancel" onclick="window.closeModal()">Cancelar</button><button class="bok blue" onclick="window.submitMove()">Mover</button></div>';
  } else if (m.type === "note") {
    h = '<h2>Nota</h2><div class="msub">Placa <b style="color:var(--accent)">' + esc(m.placa) + '</b> · ' + esc(m.caja) + '</div>' +
      '<div class="field full"><label>Texto de la nota</label>' +
      '<textarea oninput="mset(\'note\',this.value)" placeholder="Ej: revisar BIOS, pedido a proveedor…" style="background:var(--bg);border:1px solid var(--border2);border-radius:8px;padding:10px 12px;color:var(--text);font-size:14px;width:100%;min-height:90px;resize:vertical;font-family:inherit">' + esc(m.note) + '</textarea></div>' +
      '<div class="macts"><button class="bcancel" onclick="window.closeModal()">Cancelar</button><button class="bok" onclick="window.submitNote()">Guardar nota</button></div>';
  } else if (m.type === "backups") {
    let body;
    if (m.loading) body = '<div style="text-align:center;color:var(--text3);padding:24px">Cargando respaldos…</div>';
    else if (m.error) body = '<div style="color:var(--danger);font-size:13px">No se pudieron cargar (' + esc(m.error) + ').</div>';
    else if (!m.list||!m.list.length) body = '<div style="color:var(--text3);font-size:13.5px;padding:8px 0">Todav\u00eda no hay respaldos.</div>';
    else body = '<div class="snap-list">' + m.list.map(s => '<div class="snap-row"><span>📅 ' + esc(s.fecha) + '</span><button class="bok" style="padding:7px 14px" onclick="window.restoreSnapshot(\'' + esc(s.id) + '\')">Restaurar</button></div>').join("") + '</div>';
    h = '<h2>Respaldos diarios</h2><div class="msub">Copias autom\u00e1ticas (ultimos 30 d\u00EDas).</div>' + body +
      '<div class="macts" style="justify-content:space-between"><button class="bcancel" onclick="window.restoreFile()">📂 Restaurar archivo...</button><button class="bcancel" onclick="window.closeModal()">Cerrar</button></div>';
  } else if (m.type === "edit") {
    h = '<h2>Editar placa</h2><div class="msub">Placa <b style="color:var(--accent)">' + esc(m.placa) + '</b></div>' +
      '<div class="fg">' +
        '<div class="field full"><label>Marca</label><input value="' + esc(m.marca) + '" oninput="mset(\'marca\',this.value)" placeholder="HP, Lenovo…"></div>' +
        '<div class="field full"><label>Modelo / notebooks compatibles</label><input value="' + esc(m.modelo) + '" oninput="mset(\'modelo\',this.value)" placeholder="Ej: Ideapad 320-15IKB"></div>' +
      '</div>' +
      '<div class="macts"><button class="bcancel" onclick="window.closeModal()">Cancelar</button><button class="bok" onclick="window.submitEdit()">Guardar</button></div>';
  }
  document.getElementById("placaModal").style.display = "flex";
  document.getElementById("placaModalInner").innerHTML = h;
}

// ── Firebase sync (onSnapshot) ─────────────────────────────
onSnapshot(ovDoc, snap => {
  const d = snap.exists() ? snap.data() : {};
  window._S = { items:d.items||{}, added:d.added||{}, cajas:d.cajas||[], edits:d.edits||{} };
  window._fbReady = true;
  renderPlacas();
}, err => {
  console.error("Firebase:", err);
  document.getElementById("placaResults").innerHTML = '<div class="msg err show">⚠️ Sin conexi\u00F3n a Firebase</div>';
});
