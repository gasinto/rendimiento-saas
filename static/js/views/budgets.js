// ── Presupuestos ──────────────────────────────────────────────────
// Placeholder para la gestion de presupuestos.

/**
 * Renderiza la vista de presupuestos.
 * Mientras no este implementada, muestra un placeholder.
 *
 * @returns {void}
 */
window.cargarPresupuestos = function() {
  var container = document.getElementById('viewPresupuestos');
  if (!container) return;
  container.innerHTML =
    '<div class="placeholder-card">' +
      '<div class="placeholder-icon">💰</div>' +
      '<h2>Presupuestos</h2>' +
      '<p class="placeholder-desc">Presupuestos — próximamente disponible</p>' +
    '</div>';
};
