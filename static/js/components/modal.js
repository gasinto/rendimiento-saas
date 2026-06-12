/**
 * Abre un modal con titulo, contenido y botones configurables.
 * Reutiliza el contenedor #placaModal existente en el DOM.
 *
 * @param {object} config - Configuracion del modal
 * @param {string} config.title - Titulo del modal
 * @param {string} config.content - HTML del cuerpo del modal
 * @param {string} [config.subtitle] - Subtítulo debajo del titulo
 * @param {Array<{label:string, onClick:Function, variant?:string, className?:string}>} [config.buttons] - Botones del footer
 * @param {Function} [config.onClose] - Callback al cerrar el modal
 * @param {boolean} [config.wide] - Si es true, agrega clase modal-wide
 * @returns {void}
 *
 * @example
 * // modal simple con boton de cerrar
 * openModal({
 *   title: 'Confirmar',
 *   content: '<p>\u00BFEstas seguro?</p>'
 * });
 *
 * @example
 * // modal con botones personalizados
 * openModal({
 *   title: 'Editar',
 *   content: '<input id="editNombre" value="Juan">',
 *   subtitle: 'Modificá los datos',
 *   wide: true,
 *   buttons: [
 *     { label: 'Guardar', onClick: guardar, variant: 'primary' },
 *     { label: 'Cancelar', onClick: closeModal, variant: 'cancel' }
 *   ]
 * });
 */
function openModal(config) {
  if (!config) return;

  var inner = document.getElementById('placaModalInner');
  var modal = document.getElementById('placaModal');
  if (!inner || !modal) return;

  var title = config.title || '';
  var subtitle = config.subtitle || '';
  var content = config.content || '';

  var html = '';
  if (title) html += '<h2>' + title + '</h2>';
  if (subtitle) html += '<div class="msub">' + subtitle + '</div>';
  html += content;

  // Botones
  var buttons = config.buttons;
  if (buttons && buttons.length > 0) {
    html += '<div class="macts">';
    for (var i = 0; i < buttons.length; i++) {
      var btn = buttons[i];
      var btnCls = 'bok';
      if (btn.variant === 'cancel' || btn.variant === 'danger') btnCls = 'bcancel';
      if (btn.className) btnCls += ' ' + btn.className;
      var btnId = '_modalBtn_' + i;
      html += '<button id="' + btnId + '" class="' + btnCls + '">' + (btn.label || '') + '</button>';
    }
    html += '</div>';
  }

  inner.innerHTML = html;

  // Quitar/agregar modal-wide
  if (config.wide) {
    inner.classList.add('modal-wide');
  } else {
    inner.classList.remove('modal-wide');
  }

  // Mostrar modal
  modal.style.display = 'flex';

  // Guardar onClose para usarlo despues
  if (config.onClose) {
    modal._onClose = config.onClose;
  } else {
    delete modal._onClose;
  }

  // Asignar event listeners a los botones
  if (buttons) {
    for (var j = 0; j < buttons.length; j++) {
      (function(idx) {
        var btnEl = document.getElementById('_modalBtn_' + idx);
        if (btnEl && buttons[idx].onClick) {
          btnEl.addEventListener('click', buttons[idx].onClick);
        }
      })(j);
    }
  }
}

/**
 * Cierra el modal activo (#placaModal) y ejecuta onClose si existe.
 *
 * @returns {void}
 *
 * @example
 * closeModal();
 */
function closeModal() {
  var modal = document.getElementById('placaModal');
  if (!modal) return;

  // Ejecutar callback onClose si existe
  if (typeof modal._onClose === 'function') {
    try { modal._onClose(); } catch (e) { console.error('onClose error:', e); }
    delete modal._onClose;
  }

  modal.style.display = 'none';
}

// Exponer en window para compatibilidad onclick
window.openModal = openModal;
window.closeModal = closeModal;
