/**
 * Genera el HTML de un campo de formulario (input, select, textarea, checkbox).
 *
 * @param {object} config - Configuracion del campo
 * @param {string} config.label - Texto de la etiqueta
 * @param {string} config.id - ID unico para el input
 * @param {'text'|'date'|'number'|'select'|'checkbox'|'textarea'|'email'|'password'} config.type - Tipo de campo
 * @param {string} [config.value] - Valor por defecto
 * @param {Array<{value:string, label:string}>} [config.options] - Opciones para type='select'
 * @param {string} [config.placeholder] - Placeholder del input
 * @param {boolean} [config.required] - Si es true, marca el campo como requerido
 * @param {string} [config.helpText] - Texto de ayuda debajo del campo
 * @returns {string} HTML del campo completo (label + input + ayuda)
 *
 * @example
 * // campo de texto simple
 * renderField({ label: 'Nombre', id: 'nombre', type: 'text', required: true });
 * // → '<div class="field"><label for="nombre">Nombre *</label><input id="nombre" type="text" required>...</div>'
 *
 * @example
 * // campo select
 * renderField({
 *   label: 'Tipo',
 *   id: 'tipo',
 *   type: 'select',
 *   options: [{ value: 'a', label: 'Tipo A' }, { value: 'b', label: 'Tipo B' }]
 * });
 *
 * @example
 * // textarea con ayuda
 * renderField({
 *   label: 'Descripcion',
 *   id: 'desc',
 *   type: 'textarea',
 *   placeholder: 'Escribí aca...',
 *   helpText: 'Max 500 caracteres'
 * });
 */
function renderField(config) {
  if (!config || !config.id) return '';

  var label = config.label || '';
  var id = config.id;
  var type = config.type || 'text';
  var value = config.value != null ? config.value : '';
  var placeholder = config.placeholder || '';
  var required = !!config.required;
  var helpText = config.helpText || '';

  // Escapar valores para HTML
  var escId = escAttr(id);
  var escVal = escAttr(value);
  var escPlaceholder = escAttr(placeholder);

  var html = '<div class="field">';
  if (label) {
    html += '<label for="' + escId + '">' + label;
    if (required) html += ' <span style="color:var(--danger)">*</span>';
    html += '</label>';
  }

  if (type === 'select') {
    html += '<select id="' + escId + '" name="' + escId + '"';
    if (required) html += ' required';
    html += '>';
    var options = config.options || [];
    if (options.length === 0) {
      html += '<option value="">Sin opciones</option>';
    } else {
      html += '<option value="">Seleccionar\u2026</option>';
      for (var i = 0; i < options.length; i++) {
        var opt = options[i];
        var selected = (String(opt.value) === String(value)) ? ' selected' : '';
        html += '<option value="' + escAttr(opt.value) + '"' + selected + '>' + esc(opt.label) + '</option>';
      }
    }
    html += '</select>';

  } else if (type === 'checkbox') {
    var checked = value ? ' checked' : '';
    html += '<label class="checkbox-label" style="display:flex;align-items:center;gap:0.5rem;cursor:pointer">';
    html += '<input type="checkbox" id="' + escId + '" name="' + escId + '"' + checked + '>';
    html += '<span>' + (config.checkboxLabel || '') + '</span>';
    html += '</label>';

  } else if (type === 'textarea') {
    html += '<textarea id="' + escId + '" name="' + escId + '"';
    html += ' rows="3"';
    if (escPlaceholder) html += ' placeholder="' + escPlaceholder + '"';
    if (required) html += ' required';
    html += '>' + esc(value) + '</textarea>';

  } else {
    // input normal (text, date, number, email, password, etc.)
    html += '<input type="' + type + '" id="' + escId + '" name="' + escId + '"';
    html += ' value="' + escVal + '"';
    if (escPlaceholder) html += ' placeholder="' + escPlaceholder + '"';
    if (required) html += ' required';
    html += '>';
  }

  if (helpText) {
    html += '<small class="field-help" style="font-size:11px;color:var(--text3);margin-top:2px">' + helpText + '</small>';
  }

  html += '</div>';
  return html;
}

// Exponer en window
window.renderField = renderField;
