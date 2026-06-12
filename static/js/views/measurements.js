// ── JC-Sistema: Vista Mediciones (general) ─────────────────────

/**
 * Carga y renderiza la vista general de mediciones.
 * Llamado desde cambiarVista('mediciones') y desde oninput de medicionesQ.
 */
window.cargarMediciones = async function() {
  const q = (document.getElementById("medicionesQ")?.value || "").trim();
  let url = "/api/mediciones?";
  if (q) url += "q=" + encodeURIComponent(q);
  const out = document.getElementById("medicionesResults");
  const stat = document.getElementById("medicionesStat");
  try {
    const r = await apiFetch(url);
    const data = await r.json();
    const meds = data.mediciones || [];
    stat.textContent = meds.length + " medici" + (meds.length===1?"ón":"ones");
    if (!meds.length) {
      out.innerHTML = '<div class="empty" style="padding:2rem;color:var(--muted)">'+(q?'Sin resultados para <b>'+esc(q)+'</b>':'Sin mediciones registradas aún.')+'</div>';
      return;
    }
    const map = new Map();
    meds.forEach(m => {
      const key = m.codigo + "@" + (m.placa||"");
      if (!map.has(key)) map.set(key, { codigo: m.codigo, placa: m.placa||"", items: [] });
      map.get(key).items.push(m);
    });
    let html = "";
    for (const [key, g] of map) {
      html += '<div class="card ics-card" style="margin-bottom:12px">' +
        '<div class="chead"><div><div style="font-family:\'Courier New\',monospace;font-size:14px;font-weight:700;color:var(--accent)">'+esc(g.codigo)+
        ' <span style="font-size:12px;font-weight:400;color:var(--text3)">en '+esc(g.placa)+'</span></div></div>'+
        '<div><span style="font-size:11px;padding:3px 10px;border-radius:999px;background:var(--okbg);color:var(--success)">'+g.items.length+' mediciones</span></div></div>'+
        '<table><thead><tr><th>Pin</th><th>Nombre</th><th>Valor esperado</th><th>Notas</th><th></th></tr></thead><tbody>';
      g.items.forEach(x => {
        html += '<tr><td style="font-family:\'Courier New\',monospace;font-weight:700">'+esc(x.pin)+'</td>'+
          '<td>'+esc(x.nombre)+'</td>'+
          '<td style="font-family:\'Courier New\',monospace;color:var(--accent);font-weight:600">'+esc(x.valor_esperado)+'</td>'+
          '<td style="font-size:12px;color:var(--text3)">'+esc(x.notas)+'</td>'+
          '<td><button class="btn-delete" onclick="eliminarMedicionGeneral('+x.id+')">✕</button></td></tr>';
      });
      html += '</tbody></table></div>';
    }
    out.innerHTML = html;
  } catch(e) {
    out.innerHTML = '<div class="msg err show">Error al cargar mediciones</div>';
  }
};

/**
 * Elimina una medición desde la vista general.
 */
window.eliminarMedicionGeneral = async function(id) {
  if (!confirm("Eliminar esta medición?")) return;
  await apiFetch("/api/mediciones", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ _method: "DELETE", id })
  });
  window.cargarMediciones();
};
