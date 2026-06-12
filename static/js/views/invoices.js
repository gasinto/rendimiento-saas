// ── Facturación ───────────────────────────────────────────────────
// Placeholder para la gestion de facturacion.

/**
 * Renderiza la vista de facturacion.
 * Mientras no este implementada, muestra un placeholder.
 *
 * @returns {void}
 */
window.cargarFacturacion = function() {
  var container = document.getElementById('viewFacturacion');
  if (!container) return;
  container.innerHTML =
    '<div class="placeholder-card">' +
      '<div class="placeholder-icon">🧾</div>' +
      '<h2>Facturación</h2>' +
      '<p class="placeholder-desc">Facturación — próximamente disponible</p>' +
    '</div>';
};
