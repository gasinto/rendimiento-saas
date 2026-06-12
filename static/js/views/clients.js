// ── Clientes ──────────────────────────────────────────────────────
// Placeholder para la gestion de clientes.

/**
 * Renderiza la vista de clientes.
 * Mientras no este implementada, muestra un placeholder.
 *
 * @returns {void}
 */
window.cargarClientes = function() {
  var container = document.getElementById('viewClientes');
  if (!container) return;
  container.innerHTML =
    '<div class="placeholder-card">' +
      '<div class="placeholder-icon">👤</div>' +
      '<h2>Clientes</h2>' +
      '<p class="placeholder-desc">Gestión de clientes — próximamente disponible</p>' +
    '</div>';
};
