/**
 * Genera el HTML de un badge con color semantico.
 *
 * @param {string} text - Texto visible del badge
 * @param {'success'|'warning'|'danger'|'info'|'default'} variant - Color del badge
 * @returns {string} HTML del badge
 *
 * @example
 * renderBadge('Activo', 'success');
 * // → '<span class="badge badge--success" style="...">Activo</span>'
 *
 * @example
 * renderBadge('Pendiente', 'warning');
 *
 * @example
 * renderBadge('Error', 'danger');
 */
function renderBadge(text, variant) {
  if (text == null) text = '';
  var v = variant || 'default';

  var colorMap = {
    success: { bg: 'rgba(77,182,172,.15)', fg: 'var(--success)', border: 'rgba(77,182,172,.3)' },
    warning: { bg: 'rgba(240,180,41,.15)', fg: 'var(--accent)', border: 'rgba(240,180,41,.3)' },
    danger: { bg: 'rgba(239,83,80,.12)', fg: 'var(--danger)', border: 'rgba(239,83,80,.3)' },
    info: { bg: 'rgba(100,181,246,.15)', fg: '#64b5f6', border: 'rgba(100,181,246,.3)' },
    default: { bg: 'var(--surface)', fg: 'var(--muted)', border: 'var(--border)' }
  };

  var colors = colorMap[v] || colorMap.default;

  return '<span class="badge badge--' + v + '" style="' +
    'font-size:11px;padding:2px 8px;border-radius:999px;font-weight:600;display:inline-block;' +
    'background:' + colors.bg + ';' +
    'color:' + colors.fg + ';' +
    'border:1px solid ' + colors.border +
  '">' + text + '</span>';
}

// Exponer en window
window.renderBadge = renderBadge;
