// ── JC-Sistema: Vista Diagramas (ex BoardDoctor) ──────────────

/**
 * @type {Object.<string, number>}
 * Almacena los timeouts de debounce para cada tipo de b├║squeda.
 */
const _bdDebounce = {};

/**
 * Ejecuta buscarBoardDoctor con debounce de 350ms.
 * Llamado desde oninput de los campos de b├║squeda en viewDiagramas.
 * @param {'diagramas'|'ic-marcas'|'ic-compatibles'|'datasheet'} tipo - Tipo de b├║squeda
 */
window.debounceBd = function(tipo) {
  if (_bdDebounce[tipo]) clearTimeout(_bdDebounce[tipo]);
  _bdDebounce[tipo] = setTimeout(() => window.buscarBoardDoctor(tipo), 350);
};

/**
 * Obtiene el input element para el tipo de b├║squeda dado.
 * @param {string} tipo
 * @returns {HTMLInputElement|null}
 */
function _bdInput(tipo) {
  const m = { diagramas:"bdDiagramaQ", "ic-marcas":"bdIcMarcaQ", "ic-compatibles":"bdIcCompatQ", datasheet:"bdDatasheetQ" };
  return document.getElementById(m[tipo] || "");
}

/**
 * Obtiene el contenedor de resultados para el tipo de b├║squeda dado.
 * @param {string} tipo
 * @returns {HTMLElement|null}
 */
function _bdResult(tipo) {
  const m = { diagramas:"bdResultadosDiagramas", "ic-marcas":"bdResultadosIcMarca", "ic-compatibles":"bdResultadosIcCompat", datasheet:"bdResultadosDatasheet" };
  return document.getElementById(m[tipo] || "");
}

/**
 * Construye la URL de la API para el tipo de b├║squeda y consulta.
 * @param {string} tipo
 * @param {string} q
 * @returns {string}
 */
function _bdUrl(tipo, q) {
  const enc = encodeURIComponent(q);
  if (tipo === "diagramas") return "/api/boarddoctor/diagramas?q=" + enc;
  if (tipo === "ic-marcas") return "/api/boarddoctor/ic-marcas?q=" + enc;
  if (tipo === "ic-compatibles") return "/api/boarddoctor/ic-compatibles?modelo=" + enc;
  if (tipo === "datasheet") return "/api/boarddoctor/datasheet?componente=" + enc;
  return "";
}

/**
 * Busca diagramas, ICs, compatibilidades o datasheets seg├║n el tipo.
 * Llamado desde onclick de los botones de b├║squeda y desde debounceBd.
 * @param {'diagramas'|'ic-marcas'|'ic-compatibles'|'datasheet'} tipo - Tipo de b├║squeda
 */
window.buscarBoardDoctor = async function(tipo) {
  try {
    const inp = _bdInput(tipo);
    const cont = _bdResult(tipo);
    if (!inp || !cont) { console.warn("BD: elementos no encontrados", tipo); return; }
    const q = inp.value.trim();

    if (!q || q.length < 2) {
      cont.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text3);font-size:12px">✏️ Escrib├ş al menos 2 caracteres</div>';
      return;
    }

    cont.innerHTML = '<div style="padding:16px;text-align:center;color:var(--muted);font-size:13px">⏳ Buscando…</div>';

    const r = await apiFetch(_bdUrl(tipo, q));
    const data = await r.json();
    _bdRender(tipo, data, cont);
  } catch (e) {
    console.error("BD error:", e);
    try { const cont = _bdResult(tipo); if (cont) cont.innerHTML = '<div class="msg err show" style="margin-top:0">❌ Error. ┐El servidor est├í corriendo?</div>'; } catch(_) {}
  }
};

/**
 * Renderiza los resultados de la b├║squeda en el contenedor.
 * @param {string} tipo - Tipo de b├║squeda
 * @param {object} data - Datos de la respuesta
 * @param {HTMLElement} cont - Contenedor de resultados
 */
function _bdRender(tipo, data, cont) {
  const items = tipo === "diagramas" ? (data.diagramas || []) : (data.resultados || []);

  if (!items.length) {
    cont.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text3);font-size:12px">— Sin resultados —</div>';
    return;
  }

  let html = '<div style="overflow-x:auto"><table class="tbl" style="font-size:12px"><thead><tr>';

  if (tipo === "diagramas") {
    html += '<th>Marca</th><th>Modelo</th><th>Tipo</th><th>Archivo</th><th>Tama├▒o</th><th></th>';
  } else if (tipo === "ic-marcas") {
    html += '<th>C├│digo</th><th>Modelo</th><th>Fabricante</th><th>Funci├│n</th><th></th>';
  } else if (tipo === "ic-compatibles") {
    html += '<th>Fabricante</th><th>Original</th><th>Compatibles</th>';
  } else if (tipo === "datasheet") {
    html += '<th>T├ştulo</th><th>Fuente</th><th></th>';
  }
  html += '</tr></thead><tbody>';

  items.forEach(item => {
    html += '<tr>';
    if (tipo === "diagramas") {
      const urlD = item.url_descarga || '';
      html += '<td>' + esc(item.marca || '') + '</td>'
        + '<td><strong>' + esc(item.modelo || '') + '</strong></td>'
        + '<td>' + esc(item.tipo || '') + '</td>'
        + '<td style="font-size:11px">' + esc(item.nombre_archivo || '') + '</td>'
        + '<td>' + (item.tama├▒o_mb || 0) + ' MB</td>'
        + '<td>' + (urlD ? '<a href="' + esc(urlD) + '" target="_blank" rel="noopener" style="font-weight:600">⬇</a>' : '—') + '</td>';
    } else if (tipo === "ic-marcas") {
      const modelo = esc(item.modelo || '');
      html += '<td><strong>' + esc(item.marking || '') + '</strong></td>'
        + '<td>' + modelo + '</td>'
        + '<td>' + esc(item.fabricante || '') + '</td>'
        + '<td style="font-size:11px;color:var(--text2)">' + esc(item.funcion || '') + '</td>'
        + '<td><a href="javascript:void(0)" onclick="buscarDatasheetDeModelo(\'' + modelo.replace(/'/g, "\\'") + '\')" title="Buscar datasheet" style="font-size:16px;text-decoration:none">📄</a></td>';
    } else if (tipo === "ic-compatibles") {
      html += '<td>' + esc(item.fabricante || '') + '</td>'
        + '<td><strong>' + esc(item.modelo_original || '') + '</strong></td>'
        + '<td>' + esc(item.compatibles || '') + '</td>';
    } else if (tipo === "datasheet") {
      html += '<td>' + esc(item.titulo || '') + '</td>'
        + '<td>' + esc(item.fuente || '') + '</td>'
        + '<td>' + (item.url ? '<a href="' + esc(item.url) + '" target="_blank" rel="noopener" style="font-weight:600">🔗</a>' : '—') + '</td>';
    }
    html += '</tr>';
  });

  html += '</tbody></table></div>'
    + '<div style="font-size:11px;color:var(--text3);margin-top:4px;text-align:right">' + items.length + ' resultado(s)</div>';

  cont.innerHTML = html;
}

/**
 * Busca el datasheet del modelo de IC encontrado desde el resultado de ic-marcas.
 * @param {string} modelo - Modelo del IC para buscar datasheet
 */
window.buscarDatasheetDeModelo = function(modelo) {
  const inp = document.getElementById("bdDatasheetQ");
  if (inp) { inp.value = modelo; }
  buscarBoardDoctor("datasheet");
  // Desplazar suavemente hacia la card de datasheets
  const card = document.getElementById("bdDatasheetQ")?.closest?.(".card");
  if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
};

/**
 * Re-importa datos de BoardDoctor desde los archivos CSV.
 * Llamado desde onclick del bot├│n de importaci├│n en viewDiagramas.
 */
window.importarBoardDoctor = async function() {
  const cont = document.getElementById("bdResultadosDiagramas");
  cont.innerHTML = '<div style="padding:16px;text-align:center;color:var(--muted)">⏳ Importando datos…</div>';
  try {
    const r = await apiFetch("/api/importar-boarddoctor", { method: "POST", headers: {"Content-Type":"application/json"}, body: "{}" });
    const data = await r.json();
    if (data.ok) {
      mostrarMsg("✅ Importados: " + data.diagramas + " diagramas, " + data.ic_marcas + " ICs, " + data.ic_compatibilidad + " compatibilidades", "ok");
    } else {
      mostrarMsg("❌ " + (data.error || "Error al importar"), "err");
    }
    buscarBoardDoctor("diagramas");
  } catch (e) {
    mostrarMsg("❌ Error al importar: " + e.message, "err");
  }
};
