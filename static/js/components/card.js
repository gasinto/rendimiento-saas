/**
 * Genera el HTML de una card con titulo, contenido y opciones de personalizacion.
 *
 * @param {object} config - Configuracion de la card
 * @param {string} config.title - Titulo visible de la card
 * @param {string} config.content - HTML del cuerpo de la card
 * @param {string} [config.className] - Clase CSS extra para la card
 * @param {string} [config.icon] - Emoji o icono antes del titulo
 * @param {'sm'|'md'|'lg'} [config.size] - Tamaño de padding interno
 * @returns {string} HTML de la card
 *
 * @example
 * // card basica
 * renderCard({
 *   title: 'Resumen',
 *   content: '<div class="value">42</div>'
 * });
 * // → '<div class="card"><div class="label">Resumen</div><div class="value">42</div></div>'
 *
 * @example
 * // card con icono y tamaño compacto
 * renderCard({
 *   title: 'Usuarios',
 *   content: '<span>5 activos</span>',
 *   icon: '\uD83D\uDC65',
 *   size: 'sm'
 * });
 */
function renderCard(config) {
  if (!config || !config.title) return '';

  var sizeMap = { sm: '0.75rem', md: '1rem', lg: '1.5rem' };
  var padding = sizeMap[config.size] || sizeMap.md;

  var cls = 'card';
  if (config.className) cls += ' ' + config.className;

  var html = '<div class="' + cls + '"';
  if (padding !== '1rem') {
    html += ' style="padding:' + padding + '"';
  }
  html += '>';
  html += '<div class="label">';
  if (config.icon) html += config.icon + ' ';
  html += config.title;
  html += '</div>';
  if (config.content) {
    html += '<div class="card-body">' + config.content + '</div>';
  }
  html += '</div>';
  return html;
}

// Exponer en window para compatibilidad
window.renderCard = renderCard;
