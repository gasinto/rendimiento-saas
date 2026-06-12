// ── JC-Sistema: Vista Referencias ──────────────────────────────

/** @type {number|null} Timeout para debounce del buscador de referencias */
let _refTimeout = null;

/**
 * Carga y renderiza las referencias, filtradas por b├║squeda y categor├şa.
 * Llamado desde onchange del selector de categor├şa y desde cargarReferenciasConDelay().
 */
window.cargarReferencias = async () => {
  const q = (document.getElementById("refQ")?.value || "").trim();
  const cat = document.getElementById("refCategoria")?.value || "";
  const cont = document.getElementById("refResults");
  if (!cont) return;
  cont.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--muted)">⏳ Cargando…</div>';
  try {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (cat) params.set("cat", cat);
    const r = await apiFetch("/api/referencias" + (params.toString() ? "?" + params.toString() : ""));
    const data = await r.json();
    const items = data.referencias || [];

    // rebuild category filter options without losing current selection
    const cats = [...new Set(items.map(i => i.categoria).filter(Boolean))];
    const sel = document.getElementById("refCategoria");
    sel.innerHTML = '<option value="">📂 Todas las categor├şas</option>' +
      cats.sort().map(c => '<option value="' + escAttr(c) + '">' + esc(c) + '</option>').join("");

    if (!items.length) {
      cont.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--muted)">Sin referencias' +
        (q ? ' para "' + esc(q) + '"' : '') + '</div>';
      return;
    }

    let html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1rem">';
    items.forEach(i => {
      html += '<div class="ref-card" style="background:var(--card);border:1px solid var(--border);border-radius:0.75rem;padding:1rem;cursor:pointer" onclick="abrirReferencia(' + i.id + ')">' +
        '<div style="font-size:0.7rem;color:var(--muted);margin-bottom:0.25rem">' + esc(i.categoria || "General") + '</div>' +
        '<div>' + i.contenido_html + '</div>' +
        '</div>';
    });
    html += '</div>';
    cont.innerHTML = html;
  } catch (e) {
    cont.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--danger)">Error al cargar: ' + esc(e.message) + '</div>';
  }
};

/**
 * Carga referencias con debounce de 300ms (para el input de b├║squeda).
 * Llamado desde oninput del campo de b├║squeda.
 */
window.cargarReferenciasConDelay = () => {
  clearTimeout(_refTimeout);
  _refTimeout = setTimeout(cargarReferencias, 300);
};

/**
 * Abre el detalle de una referencia en el modal #refModal.
 * @param {number} id - ID de la referencia
 */
window.abrirReferencia = async (id) => {
  const inner = document.getElementById("refModalInner");
  document.getElementById("refModal").style.display = "flex";
  inner.innerHTML = '<div style="text-align:center;padding:2rem">⏳ Cargando…</div>';
  try {
    const r = await apiFetch("/api/referencias/detalle?id=" + id);
    const data = await r.json();
    const ref = data.referencia;
    if (!ref) { inner.innerHTML = '<div style="padding:2rem;color:var(--danger)">No encontrada</div>'; return; }
    inner.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem">' +
        '<div>' +
          '<span style="font-size:0.75rem;color:var(--muted)">' + esc(ref.categoria || "General") + '</span>' +
          '<h3 style="margin:0">' + esc(ref.titulo) + '</h3>' +
        '</div>' +
        '<button class="btn-delete" onclick="closeModal()" style="font-size:1.2rem">✕</button>' +
      '</div>' +
      '<div style="font-size:0.9rem;line-height:1.6;overflow-y:auto;max-height:60vh">' + ref.contenido_html + '</div>' +
      '<div style="display:flex;gap:0.5rem;margin-top:1rem">' +
        '<button class="tbtn" onclick="abrirEditarReferencia(' + ref.id + ')">✏️ Editar</button>' +
        '<button class="tbtn" style="color:var(--danger)" onclick="eliminarReferencia(' + ref.id + ')">🗑️ Eliminar</button>' +
        '<button class="bcancel" onclick="closeModal()">Cerrar</button>' +
      '</div>';
  } catch (e) {
    inner.innerHTML = '<div style="padding:2rem;color:var(--danger)">Error: ' + esc(e.message) + '</div>';
  }
};

/**
 * Abre el formulario para agregar una nueva referencia en el modal #refModal.
 * Llamado desde onclick en viewReferencia.
 */
window.abrirAgregarReferencia = () => {
  const inner = document.getElementById("refModalInner");
  document.getElementById("refModal").style.display = "flex";
  inner.innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem">' +
      '<h3 style="margin:0">➕ Nueva referencia</h3>' +
      '<button class="btn-delete" onclick="closeModal()" style="font-size:1.2rem">✕</button>' +
    '</div>' +
    '<div style="display:flex;flex-direction:column;gap:0.5rem">' +
      '<input id="refEditId" type="hidden" value="">' +
      '<label style="font-size:0.85rem;font-weight:600">T├ştulo</label>' +
      '<input id="refEditTitulo" placeholder="Ej: MOSFET Canal N" style="padding:0.5rem;border:1px solid var(--border);border-radius:0.5rem;font-size:0.9rem">' +
      '<label style="font-size:0.85rem;font-weight:600">Categor├şa</label>' +
      '<input id="refEditCategoria" placeholder="Ej: Electr├│nica en Notebooks" style="padding:0.5rem;border:1px solid var(--border);border-radius:0.5rem;font-size:0.9rem">' +
      '<label style="font-size:0.85rem;font-weight:600">Contenido (HTML)</label>' +
      '<textarea id="refEditHtml" rows="12" style="padding:0.5rem;border:1px solid var(--border);border-radius:0.5rem;font-size:0.85rem;font-family:monospace;resize:vertical" placeholder="&lt;ul&gt;&lt;li&gt;...&lt;/li&gt;&lt;/ul&gt;"></textarea>' +
      '<div style="display:flex;gap:0.5rem;justify-content:flex-end;margin-top:0.5rem">' +
        '<button class="bcancel" onclick="closeModal()">Cancelar</button>' +
        '<button class="bok" onclick="guardarReferencia()">💾 Guardar</button>' +
      '</div>' +
    '</div>';
};

/**
 * Abre el formulario para editar una referencia existente.
 * @param {number} id - ID de la referencia
 */
window.abrirEditarReferencia = (id) => {
  const inner = document.getElementById("refModalInner");
  document.getElementById("refModal").style.display = "flex";
  inner.innerHTML = '<div style="text-align:center;padding:2rem">⏳ Cargando…</div>';
  apiFetch("/api/referencias/detalle?id=" + id).then(r => r.json()).then(data => {
    const ref = data.referencia || {};
    inner.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem">' +
        '<h3 style="margin:0">✏️ Editar referencia</h3>' +
        '<button class="btn-delete" onclick="closeModal()" style="font-size:1.2rem">✕</button>' +
      '</div>' +
      '<div style="display:flex;flex-direction:column;gap:0.5rem">' +
        '<input id="refEditId" type="hidden" value="' + id + '">' +
        '<label style="font-size:0.85rem;font-weight:600">T├ştulo</label>' +
        '<input id="refEditTitulo" value="' + escAttr(ref.titulo || "") + '" style="padding:0.5rem;border:1px solid var(--border);border-radius:0.5rem;font-size:0.9rem">' +
        '<label style="font-size:0.85rem;font-weight:600">Categor├şa</label>' +
        '<input id="refEditCategoria" value="' + escAttr(ref.categoria || "") + '" style="padding:0.5rem;border:1px solid var(--border);border-radius:0.5rem;font-size:0.9rem">' +
        '<label style="font-size:0.85rem;font-weight:600">Contenido (HTML)</label>' +
        '<textarea id="refEditHtml" rows="12" style="padding:0.5rem;border:1px solid var(--border);border-radius:0.5rem;font-size:0.85rem;font-family:monospace;resize:vertical">' + esc(ref.contenido_html || "") + '</textarea>' +
        '<div style="display:flex;gap:0.5rem;justify-content:flex-end;margin-top:0.5rem">' +
          '<button class="bcancel" onclick="closeModal()">Cancelar</button>' +
          '<button class="bok" onclick="guardarReferencia()">💾 Guardar</button>' +
        '</div>' +
      '</div>';
  }).catch(() => {
    inner.innerHTML = '<div style="padding:2rem;color:var(--danger)">Error al cargar datos</div>';
  });
};

/**
 * Guarda (crea o actualiza) una referencia.
 * Llamado desde onclick en el modal de referencia.
 */
window.guardarReferencia = async () => {
  const id = document.getElementById("refEditId")?.value || "";
  const titulo = document.getElementById("refEditTitulo")?.value?.trim();
  const categoria = document.getElementById("refEditCategoria")?.value?.trim();
  const html = document.getElementById("refEditHtml")?.value?.trim();
  if (!titulo || !html) { alert("Faltan t├ştulo o contenido"); return; }
  const body = { titulo, categoria: categoria || "General", contenido_html: html };
  if (id) body.id = parseInt(id);
  try {
    const r = await apiFetch("/api/referencias", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await r.json();
    if (!data.ok) { alert("Error: " + (data.error || "desconocido")); return; }
    closeModal();
    cargarReferencias();
  } catch (e) {
    alert("Error al guardar: " + e.message);
  }
};

/**
 * Elimina una referencia por ID.
 * @param {number} id - ID de la referencia a eliminar
 */
window.eliminarReferencia = async (id) => {
  if (!confirm("┐Eliminar esta referencia definitivamente?")) return;
  try {
    const r = await apiFetch("/api/referencias", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ _method: "DELETE", id })
    });
    const data = await r.json();
    if (!data.ok) { alert("Error: " + (data.error || "desconocido")); return; }
    closeModal();
    cargarReferencias();
  } catch (e) {
    alert("Error al eliminar: " + e.message);
  }
};
