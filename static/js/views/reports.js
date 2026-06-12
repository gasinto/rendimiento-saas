// ── JC-Sistema: Vista Reportes ─────────────────────────────────

/** @type {Object|null} Cache de datos del informe generado */
let _informeData = null;

/**
 * Renderiza el formulario de informe de puntos en viewReportes.
 * Llamado desde cambiarVista('reportes') via loader map.
 */
function cargarReportes() {
  const container = document.getElementById("viewReportes");
  if (!container) return;
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  container.innerHTML = `
    <h2 style="margin:0 0 4px 0">📄 Generar informe de puntos</h2>
    <div style="font-size:13px;color:var(--text3);margin-bottom:16px">Seleccioná período y generá la vista previa</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:500px">
      <div class="field">
        <label>Tipo</label>
        <select id="informeTipo" onchange="cambiarTipoInforme()">
          <option value="mes">Mensual</option>
          <option value="anio">Anual</option>
        </select>
      </div>
      <div class="field">
        <label>Período</label>
        <select id="informePeriodo"></select>
      </div>
    </div>
    <div style="display:flex;gap:10px;margin:16px 0">
      <button class="tbtn prim" onclick="generarInforme()">Generar vista previa</button>
    </div>
    <div id="informePreview" style="display:none"></div>
    <div id="informeActions" style="display:none;margin-top:12px;display:flex;gap:10px">
      <button class="tbtn prim" onclick="descargarPDF()">⬇ Descargar PDF</button>
      <button class="tbtn" onclick="descargarTXT()" style="font-size:12px">Descargar TXT (fallback)</button>
    </div>
  `;
  cargarPeriodosInforme();
}
window.cargarReportes = cargarReportes;

/**
 * Carga los períodos disponibles en el selector de informe.
 */
async function cargarPeriodosInforme() {
  const sel = document.getElementById("informePeriodo");
  if (!sel) return;
  try {
    const r = await apiFetch("/api/meses");
    const data = await r.json();
    const meses = data.meses || [];
    if (meses.length === 0) {
      sel.innerHTML = '<option value="">Sin datos disponibles</option>';
      return;
    }
    const tipo = document.getElementById("informeTipo").value;
    if (tipo === "mes") {
      sel.innerHTML = "";
      meses.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.mes;
        opt.textContent = m.mes + " — " + m.equipos + " eq";
        sel.appendChild(opt);
      });
    } else {
      const anios = new Set();
      meses.forEach(m => anios.add(m.mes.slice(0, 4)));
      sel.innerHTML = "";
      [...anios].sort().reverse().forEach(a => {
        const opt = document.createElement("option");
        opt.value = a;
        opt.textContent = a;
        sel.appendChild(opt);
      });
    }
  } catch {
    sel.innerHTML = '<option value="">Error al cargar</option>';
  }
}
window.cargarPeriodosInforme = cargarPeriodosInforme;

/**
 * Cambia el tipo de informe (mensual/anual) y recarga períodos.
 */
function cambiarTipoInforme() {
  cargarPeriodosInforme();
  const preview = document.getElementById("informePreview");
  if (preview) preview.style.display = "none";
  const actions = document.getElementById("informeActions");
  if (actions) actions.style.display = "none";
}
window.cambiarTipoInforme = cambiarTipoInforme;

/**
 * Genera el informe de puntos llamando a la API.
 */
async function generarInforme() {
  const tipo = document.getElementById("informeTipo").value;
  const periodo = document.getElementById("informePeriodo").value;
  if (!periodo) { alert("Seleccioná un período"); return; }
  const preview = document.getElementById("informePreview");
  const actions = document.getElementById("informeActions");
  preview.style.display = "block";
  preview.innerHTML = '<div style="text-align:center;color:var(--text3);padding:12px">Generando informe…</div>';
  actions.style.display = "none";
  try {
    const r = await apiFetch("/api/informe-puntos?tipo=" + tipo + "&periodo=" + encodeURIComponent(periodo));
    const data = await r.json();
    if (data.error) {
      preview.innerHTML = '<div class="msg err show">' + (data.error || "") + '</div>';
      return;
    }
    _informeData = data;
    renderPreview(data);
    actions.style.display = "flex";
  } catch (e) {
    preview.innerHTML = '<div class="msg err show">Error al generar informe</div>';
  }
}
window.generarInforme = generarInforme;

/**
 * Renderiza la vista previa del informe.
 * @param {Object} data - Datos del informe
 */
function renderPreview(data) {
  const preview = document.getElementById("informePreview");
  let html = '<div style="background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:16px;font-size:13px;line-height:1.6;max-height:400px;overflow-y:auto">';
  html += '<div style="font-weight:700;font-size:15px;margin-bottom:8px;color:var(--accent)">📄 INFORME DE PUNTOS</div>';
  html += '<div><b>Período:</b> ' + (data.tipo === "mes" ? "Mes: " + data.periodo : "Año: " + data.periodo) + '</div>';
  html += '<div><b>Valor punto:</b> $' + Number(data.valor_punto).toLocaleString() + '</div>';
  html += '<div><b>Total equipos:</b> ' + data.total_equipos + '</div>';
  html += '<div><b>Total puntos:</b> ' + data.total_puntos + '</div>';
  html += '<div><b>Ganancia total:</b> $' + Number(data.total_ganancia).toLocaleString() + '</div>';

  if (data.detalle_equipos && data.detalle_equipos.length > 0) {
    html += '<div style="margin-top:12px;font-weight:700;color:var(--accent)">🔧 Detalle de equipos</div>';
    html += '<table style="margin-top:6px;font-size:11px"><thead><tr>' +
      '<th>#</th><th>Fecha</th><th>N° Orden</th><th>Tipo</th><th>Pts</th><th>Equipo</th>' +
      '</tr></thead><tbody>';
    data.detalle_equipos.forEach((d, i) => {
      const equipo = [d.marca, d.modelo].filter(Boolean).join(" / ") || "—";
      html += '<tr><td>' + (i+1) + '</td><td>' + d.fecha + '</td><td><strong>' + d.orden + '</strong></td>' +
        '<td>' + d.tipo + '</td><td>' + d.puntaje + '</td><td>' + equipo + '</td></tr>';
    });
    html += '</tbody></table>';
  }

  if (data.desglose && data.desglose.length > 0) {
    html += '<div style="margin-top:12px;font-weight:700;color:var(--accent)">📊 Desglose por tipo</div>';
    html += '<table style="margin-top:6px;font-size:12px"><thead><tr><th>Tipo</th><th>Cant</th><th>Pts</th><th>Ganancia</th></tr></thead><tbody>';
    data.desglose.forEach(d => {
      const g = d.puntos * data.valor_punto;
      html += '<tr><td>' + (d.tipo || "") + '</td><td>' + d.total + '</td><td>' + d.puntos + '</td><td>$' + g.toLocaleString() + '</td></tr>';
    });
    html += '</tbody></table>';
  }

  if (data.comparativa) {
    html += '<div style="margin-top:12px;font-weight:700;color:var(--accent)">📈 Comparativa con período anterior</div>';
    html += '<div><b>Período anterior:</b> ' + data.comparativa.periodo_anterior + '</div>';
    html += '<div><b>Equipos:</b> ' + data.comparativa.equipos + '</div>';
    html += '<div><b>Puntos:</b> ' + data.comparativa.puntos + '</div>';
    html += '<div><b>Ganancia:</b> $' + Number(data.comparativa.ganancia).toLocaleString() + '</div>';
  }

  html += '</div>';
  preview.innerHTML = html;
}

/**
 * Descarga el informe como PDF.
 */
function descargarPDF() {
  if (!_informeData) return;
  const tipo = document.getElementById("informeTipo").value;
  const periodo = document.getElementById("informePeriodo").value;
  if (!periodo) return;
  const url = "/api/reports/puntos/pdf?tipo=" + tipo + "&periodo=" + encodeURIComponent(periodo);
  apiFetch(url).then(async r => {
    if (!r.ok) { mostrarMsg("❌ Error al descargar PDF","err"); return; }
    const blob = await r.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = "informe-puntos_" + periodo + ".pdf";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
  }).catch(() => mostrarMsg("❌ Error al descargar PDF","err"));
}
window.descargarPDF = descargarPDF;

/**
 * Descarga el informe como TXT.
 */
function descargarTXT() {
  if (!_informeData || !_informeData.contenido_txt) return;
  const periodo = _informeData.periodo;
  const blob = new Blob([_informeData.contenido_txt], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "informe-puntos_" + periodo + ".txt";
  a.click();
  URL.revokeObjectURL(url);
}
window.descargarTXT = descargarTXT;
