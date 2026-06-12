// ── NAV_CONFIG ─────────────────────────────────────────────────
// Unica fuente de verdad para la navegacion lateral.

/**
 * @typedef {object} NavItem
 * @property {string} id - Identificador unico de la vista
 * @property {string} icon - Emoji o icono visual
 * @property {string} label - Texto visible en la sidebar
 * @property {boolean} [placeholder] - true si es una vista pendiente
 */

/**
 * @typedef {object} NavSection
 * @property {string} section - Nombre de la seccion
 * @property {NavItem[]} items - Items de navegacion en esta seccion
 */

/**
 * Configuracion completa de la barra de navegacion lateral.
 * @type {NavSection[]}
 *
 * @example
 * NAV_CONFIG[0].section // → 'TALLER'
 * NAV_CONFIG[0].items[0].id // → 'dashboard'
 */
var NAV_CONFIG = [
  {
    section: 'TALLER',
    items: [
      { id: 'dashboard',    icon: '\uD83C\uDFE0', label: 'Dashboard' },
      { id: 'ordenes',      icon: '\uD83D\uDCCB', label: '\u00D3rdenes' },
      { id: 'reparaciones', icon: '\uD83D\uDD27', label: 'Reparaciones' },
      { id: 'clientes',     icon: '\uD83D\uDC64', label: 'Clientes', placeholder: true },
      { id: 'presupuestos', icon: '\uD83D\uDCB0', label: 'Presupuestos', placeholder: true },
      { id: 'facturacion',  icon: '\uD83E\uDDFE', label: 'Facturaci\u00F3n', placeholder: true },
      { id: 'inventario',   icon: '\uD83D\uDCE6', label: 'Inventario', placeholder: true },
    ],
  },
  {
    section: 'CONOCIMIENTO',
    items: [
      { id: 'placas',        icon: '\uD83D\uDD29', label: 'Placas' },
      { id: 'ics',           icon: '\uD83D\uDD0C', label: 'ICs' },
      { id: 'mediciones',    icon: '\uD83D\uDCCF', label: 'Mediciones' },
      { id: 'puntos-placa',  icon: '\uD83D\uDCD0', label: 'Puntos placa' },
      { id: 'soluciones',    icon: '\uD83D\uDCA1', label: 'Soluciones' },
      { id: 'referencias',   icon: '\uD83D\uDCD6', label: 'Referencias' },
      { id: 'diagramas',     icon: '\uD83D\uDD0D', label: 'Diagramas' },
    ],
  },
  {
    section: 'ADMIN',
    items: [
      { id: 'config',   icon: '\u2699\uFE0F', label: 'Config' },
      { id: 'reportes', icon: '\uD83D\uDCCA', label: 'Reportes' },
      { id: 'usuarios', icon: '\uD83D\uDC65', label: 'Usuarios', placeholder: true },
    ],
  },
];

// ── VIEW_ALIASES ───────────────────────────────────────────────
// Mapea IDs de vistas legacy a los nuevos IDs del NAV_CONFIG.

/**
 * Mapeo de IDs de vistas viejas a nuevas.
 * Permite que cambiarVista() acepte tanto 'estadisticas' como 'dashboard'.
 *
 * @type {Object.<string, string>}
 */
var VIEW_ALIASES = {
  'estadisticas': 'dashboard',
  'referencia': 'referencias',
  'mediciones-placa': 'puntos-placa',
  'mes': 'ordenes',
  'general': 'ordenes',
};

// ── renderSidebar ──────────────────────────────────────────────

/**
 * Renderiza la barra de navegacion lateral completa a partir de NAV_CONFIG.
 * Inserta el HTML en el elemento #sidebar del DOM.
 * Incluye header, secciones con items, y footer con usuario + logout.
 *
 * @returns {void}
 *
 * @example
 * renderSidebar();
 * // Genera: <nav id="sidebar">...</nav>
 */
function renderSidebar() {
  var sidebar = document.getElementById('sidebar');
  if (!sidebar) return;

  var html = '';
  // Header
  html += '<div class="sidebar-header">\uD83D\uDCCA Rendimiento</div>';

  // Secciones
  for (var s = 0; s < NAV_CONFIG.length; s++) {
    var section = NAV_CONFIG[s];
    html += '<div class="sidebar-section-label">' + section.section + '</div>';
    html += '<div class="sidebar-section">';
    for (var i = 0; i < section.items.length; i++) {
      var item = section.items[i];
      var icon = item.placeholder ? '\uD83D\uDD12' : item.icon;
      html += '<a class="sidebar-item" data-vista="' + item.id + '" onclick="cambiarVista(\'' + item.id + '\')">' +
        '<span class="sidebar-icon">' + icon + '</span>' +
        '<span class="sidebar-label">' + item.label + '</span>' +
        '</a>';
    }
    html += '</div>';
  }

  // Footer
  html += '<div class="sidebar-footer">' +
    '<span id="sidebarUser">\uD83D\uDC64 <span id="sidebarUserName"></span></span>' +
    '<button onclick="logout()" class="sidebar-logout" style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:0.75rem;padding:0.25rem 0.5rem">Salir</button>' +
    '</div>';

  sidebar.innerHTML = html;

  // Sincronizar nombre de usuario
  var userName = document.getElementById('userName');
  var sidebarUserName = document.getElementById('sidebarUserName');
  if (sidebarUserName && userName) {
    sidebarUserName.textContent = userName.textContent.replace('\uD83D\uDC64 ', '');
  }
}

// ── cambiarVista ───────────────────────────────────────────────

/**
 * Cambia la vista activa: oculta todos los contenedores, muestra el
 * correspondiente, marca el item de sidebar como activo, y ejecuta
 * el loader asociado si existe.
 *
 * Soporta VIEW_ALIASES para IDs legacy.
 *
 * @param {string} vistaId - ID de la vista a mostrar
 * @returns {void}
 *
 * @example
 * cambiarVista('dashboard');
 * cambiarVista('estadisticas'); // via alias → 'dashboard'
 */
function cambiarVista(vistaId) {
  // 1. Resolver alias
  var resolvedId = VIEW_ALIASES[vistaId] || vistaId;

  // 2. Ocultar todos los view containers
  var allViews = document.querySelectorAll('[id^="view"]');
  for (var v = 0; v < allViews.length; v++) {
    allViews[v].style.display = 'none';
  }

  // 3. Mostrar el view container target
  // Construir ID: primer letra mayuscula + resto
  var viewId = 'view' + resolvedId.charAt(0).toUpperCase() + resolvedId.slice(1);
  var container = document.getElementById(viewId);
  if (container) {
    container.style.display = 'block';
  } else {
    // Fallback: buscar el alias original como view ID
    var fallbackId = 'view' + vistaId.charAt(0).toUpperCase() + vistaId.slice(1);
    var fallback = document.getElementById(fallbackId);
    if (fallback) fallback.style.display = 'block';
  }

  // 4. Marcar item activo en la sidebar
  var items = document.querySelectorAll('.sidebar-item');
  for (var si = 0; si < items.length; si++) {
    items[si].classList.remove('active');
  }
  var activeItem = document.querySelector('.sidebar-item[data-vista="' + resolvedId + '"]');
  if (!activeItem) {
    // Intentar con el alias original
    activeItem = document.querySelector('.sidebar-item[data-vista="' + vistaId + '"]');
  }
  if (activeItem) activeItem.classList.add('active');

  // 5. Ejecutar loader asociado
  var loaders = {
    dashboard: function() {
      if (typeof cargarDashboard === 'function') cargarDashboard();
    },
    ordenes: function() {
      if (typeof cargarMes === 'function') cargarMes();
      if (typeof cargarTodas === 'function') cargarTodas();
    },
    placas: function() {
      setTimeout(function() {
        var inp = document.getElementById('placaQ');
        if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
      }, 100);
    },
    ics: function() {
      if (typeof fetchIcs === 'function') fetchIcs();
      setTimeout(function() {
        var inp = document.getElementById('icsQ');
        if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
      }, 100);
    },
    mediciones: function() {
      if (typeof cargarMediciones === 'function') cargarMediciones();
    },
    'puntos-placa': function() {
      if (typeof cargarMedicionesPlaca === 'function') cargarMedicionesPlaca();
    },
    soluciones: function() {
      if (typeof cargarSoluciones === 'function') cargarSoluciones();
    },
    referencias: function() {
      if (typeof cargarReferencias === 'function') cargarReferencias();
    },
    config: function() {
      if (typeof cargarConfiguracion === 'function') cargarConfiguracion();
    },
    diagramas: function() {
      setTimeout(function() {
        var inp = document.getElementById('bdDiagramaQ');
        if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
      }, 100);
    },
    reparaciones: function() {
      if (typeof window.cargarReparaciones === 'function') window.cargarReparaciones();
      if (typeof window.cargarEmpresasSelect === 'function') window.cargarEmpresasSelect();
    },
    reportes: function() {
      if (typeof cargarReportes === 'function') cargarReportes();
    },
    usuarios: function() {
      if (typeof cargarUsuarios === 'function') cargarUsuarios();
    },
    clientes: function() {
      if (typeof cargarClientes === 'function') cargarClientes();
    },
    presupuestos: function() {
      if (typeof cargarPresupuestos === 'function') cargarPresupuestos();
    },
    facturacion: function() {
      if (typeof cargarFacturacion === 'function') cargarFacturacion();
    },
    inventario: function() {
      if (typeof cargarInventario === 'function') cargarInventario();
    },
  };

  var loader = loaders[resolvedId];
  if (loader) loader();

  // 6. Cerrar sidebar en mobile
  closeSidebar();
}

// ── Sidebar toggle (mobile) ────────────────────────────────────

/**
 * Abre o cierra la sidebar en dispositivos moviles.
 *
 * @returns {void}
 *
 * @example
 * toggleSidebar();
 */
function toggleSidebar() {
  var sidebar = document.getElementById('sidebar');
  var overlay = document.getElementById('sidebarOverlay');
  if (!sidebar) return;

  var isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('show');
  } else {
    sidebar.classList.add('open');
    if (overlay) overlay.classList.add('show');
  }
}

/**
 * Cierra la sidebar (mobile). Se llama desde el overlay click y desde cambiarVista().
 *
 * @returns {void}
 *
 * @example
 * closeSidebar();
 */
function closeSidebar() {
  var sidebar = document.getElementById('sidebar');
  var overlay = document.getElementById('sidebarOverlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('show');
}

// ── Exponer en window ──────────────────────────────────────────
window.NAV_CONFIG = NAV_CONFIG;
window.VIEW_ALIASES = VIEW_ALIASES;
window.renderSidebar = renderSidebar;
window.cambiarVista = cambiarVista;
window.toggleSidebar = toggleSidebar;
window.closeSidebar = closeSidebar;
