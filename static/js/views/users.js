// ── Usuarios ──────────────────────────────────────────────────────
// Placeholder para la gestion de usuarios del sistema.

/**
 * Renderiza la vista de usuarios.
 * Mientras no este implementada, muestra un placeholder.
 *
 * @returns {void}
 */
window.cargarUsuarios = function() {
  var container = document.getElementById('viewUsuarios');
  if (!container) return;
  container.innerHTML =
    '<div class="placeholder-card">' +
      '<div class="placeholder-icon">👥</div>' +
      '<h2>Usuarios</h2>' +
      '<p class="placeholder-desc">Gestión de usuarios del taller — próximamente disponible</p>' +
    '</div>';
};
