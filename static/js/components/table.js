/**
 * Genera el HTML de una tabla completa con soporte para responsive y estado vacio.
 *
 * @param {string[]} headers - Nombres de las columnas
 * @param {Array<Array<string>>} rows - Datos por fila (cada fila es un array de strings)
 * @param {object} [opts] - Opciones adicionales
 * @param {string} [opts.className] - Clase CSS extra para la tabla
 * @param {boolean} [opts.responsive] - Si es true, envuelve la tabla en un div scrollable
 * @param {string} [opts.emptyMessage] - Mensaje personalizado cuando no hay filas
 * @returns {string} HTML de la tabla completa
 *
 * @example
 * // tabla basica
 * renderTable(['Nombre', 'Edad'], [['Juan', '30'], ['Ana', '25']]);
 * // → '<table><thead><tr><th>Nombre</th><th>Edad</th></tr></thead><tbody>...'
 *
 * @example
 * // tabla responsive con mensaje personalizado de vacio
 * renderTable(['ID', 'Valor'], [], { responsive: true, emptyMessage: 'Sin datos' });
 * // → '<div style="overflow-x:auto"><table>...<div class="empty">Sin datos</div>...'
 */
function renderTable(headers, rows, opts) {
  opts = opts || {};
  if (!rows || rows.length === 0) {
    var msg = opts.emptyMessage || 'Sin resultados';
    var emptyHtml = '<div class="empty">' + msg + '</div>';
    if (opts.responsive) return '<div style="overflow-x:auto">' + emptyHtml + '</div>';
    return emptyHtml;
  }

  var cls = 'tbl';
  if (opts.className) cls += ' ' + opts.className;

  var html = '<table class="' + cls + '">';
  if (headers && headers.length > 0) {
    html += '<thead><tr>';
    for (var i = 0; i < headers.length; i++) {
      html += '<th>' + headers[i] + '</th>';
    }
    html += '</tr></thead>';
  }
  html += '<tbody>';
  for (var r = 0; r < rows.length; r++) {
    html += '<tr>';
    var row = rows[r];
    for (var c = 0; c < row.length; c++) {
      html += '<td>' + row[c] + '</td>';
    }
    html += '</tr>';
  }
  html += '</tbody></table>';

  if (opts.responsive) {
    html = '<div style="overflow-x:auto">' + html + '</div>';
  }
  return html;
}

// Exponer en window para compatibilidad
window.renderTable = renderTable;
