// ── JC-Sistema: Vista Dashboard ─────────────────────────────────

/** @type {Object|null} Cache de datos del dashboard */
let _dashboardData = null;

/**
 * Carga todos los indicadores del dashboard desde la API.
 */
async function cargarDashboard() {
  try {
    const r = await apiFetch("/api/dashboard");
    const data = await r.json();
    _dashboardData = data;
    renderSummaryCards(data.mes_actual, data.resumen_anual, data.tasa_exito_anual);
    renderBarChart(data.tendencia);
    renderTablaMensual(data.tendencia);
    renderTopTipos(data.top_tipos);
    renderTasaExitoMensual(data.tasa_exito_mensual);
    renderTopMarcas(data.top_marcas);
    renderTopModelos(data.top_modelos);
    renderTopPlacas(data.top_placas);
  } catch (e) {
    document.getElementById("dashboardSummary").innerHTML = '<div class="msg err show">Error al cargar dashboard</div>';
  }
}
window.cargarDashboard = cargarDashboard;

/**
 * Renderiza las cards de resumen del dashboard.
 * @param {Object} mesActual - Datos del mes actual
 * @param {Object} resumenAnual - Resumen anual
 * @param {Object} tasaExitoAnual - Tasa de éxito anual
 */
function renderSummaryCards(mesActual, resumenAnual, tasaExitoAnual) {
  const c = document.getElementById("dashboardSummary");
  let extra = "";
  if (tasaExitoAnual && tasaExitoAnual.total > 0) {
    const pct = tasaExitoAnual.porcentaje_exito;
    const pctClass = pct >= 70 ? 'green' : (pct >= 40 ? 'blue' : '');
    extra = `
    <div class="card">
      <div class="label">✅ Tasa éxito anual</div>
      <div class="value ${pctClass}">${pct}%</div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px">${tasaExitoAnual.reparados} ok · ${tasaExitoAnual.no_reparados} fail · ${tasaExitoAnual.en_curso} en curso</div>
    </div>`;
  }
  c.innerHTML = `
    <div class="card">
      <div class="label">📆 Puntos del mes</div>
      <div class="value blue">${mesActual.puntos}</div>
    </div>
    <div class="card">
      <div class="label">💰 Ganancia del mes</div>
      <div class="value green">$${(mesActual.ganancia || 0).toLocaleString()}</div>
    </div>
    <div class="card">
      <div class="label">🔧 Equipos reparados</div>
      <div class="value">${mesActual.equipos}</div>
    </div>
    <div class="card">
      <div class="label">📊 Promedio pts/día</div>
      <div class="value">${mesActual.promedio_pts_dia}</div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px">${mesActual.promedio_equipos_dia || 0} equipos/día</div>
    </div>
    ${extra}
  `;
}

/**
 * Renderiza el gráfico de barras de tendencia mensual.
 * @param {Array} tendencia - Datos de tendencia mensual
 */
function renderBarChart(tendencia) {
  const c = document.getElementById("chartContainer");
  if (!tendencia || tendencia.length === 0) {
    c.innerHTML = '<div class="empty">Sin datos de rendimiento</div>';
    return;
  }
  const maxPts = Math.max(...tendencia.map(t => t.puntos), 1);
  const maxGan = Math.max(...tendencia.map(t => t.ganancia), 1);
  let html = "";
  tendencia.forEach(t => {
    const hPts = Math.max(2, (t.puntos / maxPts) * 180);
    const hGan = Math.max(2, (t.ganancia / maxGan) * 180);
    const shortMes = t.mes.slice(5, 7) + "/" + t.mes.slice(2, 4);
    html += '<div class="bar-wrapper">' +
      '<div class="bar-group">' +
        '<div class="bar pts" style="height:' + hPts + 'px">' +
          '<div class="bar-tooltip">' + t.puntos + ' pts</div>' +
        '</div>' +
        '<div class="bar gan" style="height:' + hGan + 'px">' +
          '<div class="bar-tooltip">$' + t.ganancia.toLocaleString() + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="bar-label">' + shortMes + '</div>' +
    '</div>';
  });
  html += '<div style="display:flex;gap:12px;font-size:10px;color:var(--muted);margin-top:4px;padding-left:4px">' +
    '<span><span style="display:inline-block;width:10px;height:10px;background:var(--accent);border-radius:2px;vertical-align:middle;margin-right:4px"></span>Puntos</span>' +
    '<span><span style="display:inline-block;width:10px;height:10px;background:var(--success);border-radius:2px;vertical-align:middle;margin-right:4px"></span>Ganancia</span>' +
  '</div>';
  c.innerHTML = html;
}

/**
 * Renderiza la tabla de rendimiento mensual.
 * @param {Array} tendencia - Datos de tendencia mensual
 */
function renderTablaMensual(tendencia) {
  const c = document.getElementById("tablaMensual");
  if (!tendencia || tendencia.length === 0) {
    c.innerHTML = '<div class="empty">Sin datos</div>';
    return;
  }
  const reversed = [...tendencia].reverse();
  let html = '<table><thead><tr><th>Mes</th><th>Equipos</th><th>Puntos</th><th>Ganancia</th></tr></thead><tbody>';
  reversed.forEach(t => {
    html += '<tr><td>' + t.mes + '</td><td>' + t.equipos + '</td><td>' + t.puntos + '</td>' +
      '<td>$' + (t.ganancia || 0).toLocaleString() + '</td></tr>';
  });
  html += '</tbody></table>';
  c.innerHTML = html;
}

/**
 * Renderiza el top de tipos de equipo más reparados.
 * @param {Array} topTipos
 */
function renderTopTipos(topTipos) {
  const c = document.getElementById("topTipos");
  if (!topTipos || topTipos.length === 0) {
    c.innerHTML = '<div class="empty">Sin datos de reparaciones</div>';
    return;
  }
  const total = topTipos.reduce((s, t) => s + t.total, 0);
  let html = '<table><thead><tr><th>Tipo</th><th>Cant</th><th>Pts</th><th>%</th></tr></thead><tbody>';
  topTipos.forEach(t => {
    const pct = total > 0 ? Math.round((t.total / total) * 100) : 0;
    html += '<tr><td style="font-weight:600">' + (t.tipo || "") + '</td><td>' + t.total + '</td><td>' + t.puntos + '</td><td>' + pct + '%</td></tr>';
  });
  html += '</tbody></table>';
  c.innerHTML = html;
}

/**
 * Renderiza la tabla de tasa de éxito mensual.
 * @param {Array} tasaExitoMensual
 */
function renderTasaExitoMensual(tasaExitoMensual) {
  const c = document.getElementById("tasaExitoMensual");
  if (!tasaExitoMensual || tasaExitoMensual.length === 0) {
    c.innerHTML = '<div class="empty">Sin datos de órdenes</div>';
    return;
  }
  let html = '<table><thead><tr><th>Mes</th><th>Total</th><th>✅ Reparados</th><th>❌ No reparados</th><th>🔄 En curso</th><th>% Éxito</th></tr></thead><tbody>';
  tasaExitoMensual.forEach(t => {
    html += '<tr><td>' + t.mes + '</td><td>' + t.total + '</td>' +
      '<td style="color:var(--success)">' + t.reparados + '</td>' +
      '<td style="color:var(--danger)">' + t.no_reparados + '</td>' +
      '<td>' + t.en_curso + '</td>' +
      '<td style="font-weight:700;color:' + (t.porcentaje_exito >= 70 ? 'var(--success)' : 'var(--danger)') + '">' + t.porcentaje_exito + '%</td></tr>';
  });
  html += '</tbody></table>';
  c.innerHTML = html;
}

/**
 * Renderiza el top de marcas más reparadas.
 * @param {Array} marcas
 */
function renderTopMarcas(marcas) {
  const c = document.getElementById("topMarcas");
  if (!marcas || marcas.length === 0) {
    c.innerHTML = '<div class="empty">Sin datos</div>';
    return;
  }
  let html = '<table><thead><tr><th>Marca</th><th>Reparaciones</th></tr></thead><tbody>';
  marcas.forEach(m => {
    html += '<tr><td style="font-weight:600">' + (m.marca || "—") + '</td><td>' + m.total + '</td></tr>';
  });
  html += '</tbody></table>';
  c.innerHTML = html;
}

/**
 * Renderiza el top de modelos más reparados.
 * @param {Array} modelos
 */
function renderTopModelos(modelos) {
  const c = document.getElementById("topModelos");
  if (!modelos || modelos.length === 0) {
    c.innerHTML = '<div class="empty">Sin datos</div>';
    return;
  }
  let html = '<table><thead><tr><th>Modelo</th><th>Reparaciones</th></tr></thead><tbody>';
  modelos.forEach(m => {
    html += '<tr><td style="font-weight:600">' + (m.modelo || "—") + '</td><td>' + m.total + '</td></tr>';
  });
  html += '</tbody></table>';
  c.innerHTML = html;
}

/**
 * Renderiza el top de placas más reparadas.
 * @param {Array} placas
 */
function renderTopPlacas(placas) {
  const c = document.getElementById("topPlacas");
  if (!placas || placas.length === 0) {
    c.innerHTML = '<div class="empty">Sin datos</div>';
    return;
  }
  let html = '<table><thead><tr><th>Placa</th><th>Reparaciones</th></tr></thead><tbody>';
  placas.forEach(p => {
    html += '<tr><td style="font-family:\'Courier New\',monospace;font-weight:600">' + (p.placa || "—") + '</td><td>' + p.total + '</td></tr>';
  });
  html += '</tbody></table>';
  c.innerHTML = html;
}
