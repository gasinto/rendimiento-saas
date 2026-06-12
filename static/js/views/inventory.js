// ── Inventario ────────────────────────────────────────────────────
// Placeholder para la gestion de inventario.

/**
 * Renderiza la vista de inventario.
 * Mientras no este implementada, muestra un placeholder.
 *
 * @returns {void}
 */
window.cargarInventario = function() {
  var container = document.getElementById('viewInventario');
  if (!container) return;
  container.innerHTML =
    '<div class="placeholder-card">' +
      '<div class="placeholder-icon">📦</div>' +
      '<h2>Inventario</h2>' +
      '<p class="placeholder-desc">Inventario — próximamente disponible</p>' +
    '</div>';
};
