// ── Auth & API Config ──────────────────────────────────────────

/** @type {string} Base URL para llamadas API (vacio si es mismo origen) */
const API_BASE = window.API_BASE || '';

/** @type {string|null} Token JWT de acceso */
let ACCESS_TOKEN = localStorage.getItem('access_token');

/** @type {string|null} Token JWT de refresh */
let REFRESH_TOKEN = localStorage.getItem('refresh_token');

/** @type {object|null} Datos del usuario autenticado */
let CURRENT_USER = JSON.parse(localStorage.getItem('user') || 'null');

/** @type {number} Valor monetario de cada punto */
let VALOR_PUNTO = 2000;

/** @type {boolean} Muestra totales en tablas de órdenes */
let mostrarTotales = false;

// ── Timer state ───────────────────────────────────────────────

/** @type {number|null} Interval ID del cronómetro */
let _timerInterval = null;

/** @type {number} Segundos acumulados del cronómetro */
let _timerSeconds = 0;

/** @type {number|null} ID de la sesión activa */
let _currentSesionId = null;

/** @type {number|null} ID de la orden en reparación */
let _timerOrdenId = null;

/** @type {string} Notas acumuladas entre pausas */
let _timerNotas = '';

// ── Buscador state ────────────────────────────────────────────

/** @type {number|null} Timeout para debounce del buscador */
let _buscarTimeout = null;

// ── Helpers ───────────────────────────────────────────────────

/**
 * Escapa texto HTML para prevenir XSS.
 *
 * @param {*} s - Valor a escapar
 * @returns {string} Texto escapado (o cadena vacia si es null/undefined)
 *
 * @example
 * esc('<script>alert("xss")</script>');
 * // → '&lt;script&gt;alert("xss")&lt;/script&gt;'
 */
const esc = (s) => {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : s;
  return d.innerHTML;
};

/**
 * Muestra un mensaje temporal en la barra de mensajes.
 *
 * @param {string} texto - Texto del mensaje
 * @param {'ok'|'err'} tipo - Tipo: 'ok' (verde) o 'err' (rojo)
 *
 * @example
 * mostrarMsg('Orden guardada', 'ok');
 * mostrarMsg('Error al guardar', 'err');
 */
function mostrarMsg(texto, tipo) {
  const m = document.getElementById('msg');
  if (!m) return;
  m.textContent = texto;
  m.className = 'msg show ' + tipo;
  setTimeout(() => m.classList.remove('show'), 3000);
}

/**
 * Traduce rutas legacy del frontend a las rutas RESTful del backend.
 * Mantiene compatibilidad con el codigo existente.
 *
 * @param {string} url - Ruta original (ej: '/api/ordenes/')
 * @returns {string} Ruta traducida (ej: '/api/orders/')
 *
 * @example
 * _apiPath('/api/ordenes?mes=2024-01');
 * // → '/api/orders?mes=2024-01'
 */
function _apiPath(url) {
  const elimMatch = url.match(/^\/api\/ordenes\/(\d+)\/eliminar$/);
  if (elimMatch) return '/api/orders/' + elimMatch[1];

  const map = [
    '/api/ordenes-detalle', '/api/orders/',
    '/api/mediciones-placa', '/api/boards/measurements',
    '/api/notas-placa', '/api/boards/notas',
    '/api/mediciones/', '/api/measurements/',
    '/api/mediciones?', '/api/measurements?',
    '/api/soluciones/', '/api/solutions/',
    '/api/soluciones?', '/api/solutions?',
    '/api/referencias/', '/api/references/',
    '/api/referencias?', '/api/references?',
    '/api/informe-puntos/pdf', '/api/reports/puntos/pdf',
    '/api/informe-puntos', '/api/reports/puntos',
    '/api/tipos-equipo', '/api/types/',
    '/api/sesiones/', '/api/sessions/',
    '/api/sesiones?', '/api/sessions?',
    '/api/ordenes/', '/api/orders/',
    '/api/ordenes?', '/api/orders?',
    '/api/ordenes', '/api/orders/',
    '/api/puntajes', '/api/scores/',
    '/api/agregar', '/api/orders/',
    '/api/meses', '/api/repairs/months',
    '/api/bloques', '/api/boards/blocks',
    '/api/placas', '/api/boards/placas',
    '/api/circuitos', '/api/ics',
    '/api/buscar', '/api/search/',
    '/api/empresas', '/api/tenants/',
    '/api/tipos', '/api/scores/tipos',
    '/api/dashboard', '/api/dashboard/',
    '/api/diagramas', '/api/boarddoctor/diagramas',
    '/api/ic-marcas', '/api/boarddoctor/ic-marcas',
    '/api/ic-compatibles', '/api/boarddoctor/ic-compatibles',
    '/api/datasheet', '/api/boarddoctor/datasheet',
    '/api/importar-boarddoctor', '/api/boarddoctor/import',
  ];

  for (let i = 0; i < map.length; i += 2) {
    const old = map[i], nu = map[i + 1];
    if (url === old || url.startsWith(old)) {
      return nu + url.slice(old.length);
    }
  }
  return url;
}

/**
 * Convierte body POST legacy (con _method, _action) a REST compat.
 * Muta el objeto urlRef (pasado por referencia) y options.
 *
 * @param {{value: string}} urlRef - Referencia mutable a la URL
 * @param {object} options - Opciones de fetch (metodo, body)
 *
 * @example
 * const ref = { value: '/api/ordenes-detalle' };
 * _restCompat(ref, { method:'POST', body: JSON.stringify({ _method:'DELETE', id:5 }) });
 * // ref.value → '/api/orders/5'
 * // options.method → 'DELETE'
 */
function _restCompat(urlRef, options) {
  if (options.method !== 'POST' || typeof options.body !== 'string') return;
  let body;
  try { body = JSON.parse(options.body); } catch { return; }

  if (body._method === 'DELETE') {
    options.method = 'DELETE';
    delete body._method;
    if (body.id != null) {
      urlRef.value = urlRef.value.replace(/\/$/, '') + '/' + body.id;
      delete body.id;
    }
    if (body.tipo) {
      const sep = urlRef.value.includes('?') ? '&' : '?';
      urlRef.value += sep + 'tipo=' + encodeURIComponent(body.tipo);
      delete body.tipo;
    }
    delete body._action;
    options.body = Object.keys(body).length ? JSON.stringify(body) : undefined;
    return;
  }

  if (body._method === 'PUT' || body._action === 'actualizar') {
    options.method = 'PUT';
    delete body._method;
    delete body._action;
    if (body.id != null) {
      urlRef.value = urlRef.value.replace(/\/$/, '') + '/' + body.id;
      delete body.id;
    }
    options.body = JSON.stringify(body);
    return;
  }

  if (body._action === 'eliminar') {
    delete body._action;
    urlRef.value = urlRef.value.replace(/\/?$/, '/delete');
    options.body = JSON.stringify(body);
    return;
  }

  if (body._action === 'crear') {
    delete body._action;
    options.body = JSON.stringify(body);
    return;
  }

  if (body._action === 'renombrar') {
    delete body._action;
    urlRef.value = urlRef.value.replace(/\/?$/, '/rename');
    options.body = JSON.stringify(body);
    return;
  }

  if (body._action === 'reordenar') {
    delete body._action;
    urlRef.value = urlRef.value.replace(/\/?$/, '/reorder');
    options.body = JSON.stringify(body);
    return;
  }

  if (body._action === 'reset-checklist') {
    delete body._action;
    urlRef.value = urlRef.value.replace(/\/?$/, '/reset-checklist');
    options.body = JSON.stringify(body);
    return;
  }

  if (body._action === 'check') {
    delete body._action;
    urlRef.value = urlRef.value.replace(/\/?$/, '/check');
    options.body = JSON.stringify(body);
    return;
  }

  if (body._action === 'actualizar-valor') {
    options.method = 'PUT';
    delete body._action;
    urlRef.value = urlRef.value.replace(/\/?$/, '/valor-punto');
    options.body = JSON.stringify(body);
    return;
  }
}

/**
 * Fetch wrapper que agrega auth headers, traduce rutas,
 * maneja REST compat, y hace auto-refresh en 401.
 *
 * @param {string} url - URL de la API
 * @param {object} [options={}] - Opciones de fetch
 * @returns {Promise<Response>} Respuesta del servidor
 *
 * @example
 * const r = await apiFetch('/api/ordenes?mes=2024-01');
 * const data = await r.json();
 */
async function apiFetch(url, options = {}) {
  url = _apiPath(url);
  const urlRef = { value: url };
  _restCompat(urlRef, options);
  url = urlRef.value;

  const headers = options.headers || {};
  if (ACCESS_TOKEN) headers['Authorization'] = 'Bearer ' + ACCESS_TOKEN;
  if (!headers['Content-Type'] && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const fullUrl = url.startsWith('http') ? url : API_BASE + url;
  let res = await fetch(fullUrl, { ...options, headers });
  if (res.status === 401 && REFRESH_TOKEN) {
    const ok = await tryRefresh();
    if (ok) {
      headers['Authorization'] = 'Bearer ' + ACCESS_TOKEN;
      res = await fetch(fullUrl, { ...options, headers });
      if (res.status === 401) { logout(); throw new Error('Sesion expirada'); }
    } else { logout(); throw new Error('Sesion expirada'); }
  }
  return res;
}

// ── Auth ───────────────────────────────────────────────────────

/**
 * Intenta renovar el token de acceso usando el refresh token.
 *
 * @returns {Promise<boolean>} true si se renovó exitosamente
 */
async function tryRefresh() {
  try {
    const r = await fetch(API_BASE + '/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: REFRESH_TOKEN }),
    });
    if (!r.ok) return false;
    const d = await r.json();
    ACCESS_TOKEN = d.access_token;
    REFRESH_TOKEN = d.refresh_token;
    localStorage.setItem('access_token', d.access_token);
    localStorage.setItem('refresh_token', d.refresh_token);
    return true;
  } catch { return false; }
}

/**
 * Muestra el overlay de login y oculta la app.
 */
function showLogin() {
  const overlay = document.getElementById('loginOverlay');
  const container = document.querySelector('.container');
  if (overlay) overlay.style.display = 'flex';
  if (container) container.style.display = 'none';
}

/**
 * Oculta el overlay de login y muestra la app.
 */
function hideLogin() {
  const overlay = document.getElementById('loginOverlay');
  const container = document.querySelector('.container');
  if (overlay) overlay.style.display = 'none';
  if (container) container.style.display = 'block';
}

/**
 * Autentica al usuario con email y password.
 *
 * @param {string} email - Email del usuario
 * @param {string} password - Contrasena
 *
 * @example
 * login('admin@example.com', '123456');
 */
async function login(email, password) {
  const btn = document.getElementById('loginBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Ingresando...'; }
  const errEl = document.getElementById('loginError');
  if (errEl) errEl.textContent = '';
  try {
    const r = await fetch(API_BASE + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const d = await r.json();
    if (!r.ok) {
      if (errEl) errEl.textContent = d?.detail?.detail || 'Error al iniciar sesion';
      return;
    }
    ACCESS_TOKEN = d.access_token;
    REFRESH_TOKEN = d.refresh_token;
    CURRENT_USER = d.user;
    localStorage.setItem('access_token', d.access_token);
    localStorage.setItem('refresh_token', d.refresh_token);
    localStorage.setItem('user', JSON.stringify(d.user));
    const userNameEl = document.getElementById('userName');
    if (userNameEl) userNameEl.textContent = '\uD83D\uDC64 ' + (d.user?.name || '');
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.style.display = 'inline-block';
    try {
      const vp = await apiFetch('/api/scores/');
      const vpd = await vp.json();
      VALOR_PUNTO = vpd.valor_punto || 2000;
    } catch (e) { console.error('Error fetching valor_punto:', e); }
    hideLogin();
    init();
  } catch (e) {
    if (errEl) errEl.textContent = 'Error de conexion';
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Ingresar'; }
  }
}

/**
 * Cierra la sesion del usuario (borra tokens y muestra login).
 */
function logout() {
  ACCESS_TOKEN = null; REFRESH_TOKEN = null; CURRENT_USER = null;
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  const userNameEl = document.getElementById('userName');
  if (userNameEl) userNameEl.textContent = '';
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) logoutBtn.style.display = 'none';
  showLogin();
}

/**
 * Verifica si el usuario tiene sesion activa al cargar la pagina.
 * Si hay token, valida con /api/auth/me.
 */
function checkAuth() {
  if (ACCESS_TOKEN) {
    fetch(API_BASE + '/api/auth/me', { headers: { 'Authorization': 'Bearer ' + ACCESS_TOKEN } })
      .then(r => {
        if (r.ok) {
          r.json().then(u => {
            CURRENT_USER = u;
            hideLogin();
            const userNameEl = document.getElementById('userName');
            if (userNameEl) userNameEl.textContent = '\uD83D\uDC64 ' + (u.name || '');
            const logoutBtn = document.getElementById('logoutBtn');
            if (logoutBtn) logoutBtn.style.display = 'inline-block';
            fetch(API_BASE + '/api/scores/', { headers: { 'Authorization': 'Bearer ' + ACCESS_TOKEN } })
              .then(r2 => r2.json()).then(d => { VALOR_PUNTO = d.valor_punto || 2000; }).catch(() => {});
            init();
          });
        } else if (REFRESH_TOKEN) {
          tryRefresh().then(ok => ok ? (hideLogin(), init()) : logout());
        } else { logout(); }
      })
      .catch(() => { hideLogin(); init(); });
  } else if (REFRESH_TOKEN) {
    tryRefresh().then(ok => ok ? (hideLogin(), init()) : showLogin());
  } else { showLogin(); }
}

// ── Init ───────────────────────────────────────────────────────

/**
 * Inicializa la app: carga meses, tipos, establece fecha actual,
 * marca servidor como conectado, y restaura sesion pendiente.
 */
async function init() {
  try {
    await Promise.all([
      typeof cargarMeses === 'function' ? cargarMeses() : Promise.resolve(),
      typeof cargarTipos === 'function' ? cargarTipos() : Promise.resolve(),
    ]);
  } catch (e) { /* funciones aun no cargadas */ }

  const hoy = new Date();
  const fechaInput = document.getElementById('fechaInput');
  if (fechaInput) fechaInput.value = hoy.toISOString().split('T')[0];
  const statusEl = document.getElementById('serverStatus');
  if (statusEl) {
    statusEl.textContent = '\u2705 Conectado';
    statusEl.style.color = 'var(--success)';
  }
  try {
    if (typeof cargarMes === 'function') await cargarMes();
  } catch (e) { /* */ }
  if (typeof restaurarSesionPendiente === 'function') restaurarSesionPendiente();
}

/**
 * Intenta restaurar una sesion de reparacion pendiente (post-recarga).
 */
async function restaurarSesionPendiente() {
  try {
    const r = await apiFetch('/api/sesiones/pendiente');
    const d = await r.json();
    if (!d.sesion) return;
    const s = d.sesion;
    _timerOrdenId = s.orden_id;
    _currentSesionId = s.id;
    _timerSeconds = s.duracion_total || 0;
    _timerNotas = s.notas || '';
    const ftNumero = document.getElementById('ftNumero');
    if (ftNumero) ftNumero.textContent = s.numero || s.orden_id;
    actualizarFtTime();
    if (s.estado === 'activa') {
      await apiFetch('/api/sesiones/pausar', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: s.id, duracion_segundos: _timerSeconds,
          notas: (_timerNotas ? _timerNotas + ' | ' : '') + '\u23F8 Pausada automatica por recarga'
        })
      });
      _timerNotas = (_timerNotas ? _timerNotas + ' | ' : '') + '\u23F8 Pausada automatica por recarga';
    }
    _ftSetPaused(true);
    mostrarMsg(
      '\u23F8 Sesion recuperada \u2014 #' + s.numero +
      ' (' + Math.floor(_timerSeconds / 60) + 'min ' + (_timerSeconds % 60) + 's)',
      'ok'
    );
  } catch (e) { console.error('restaurarSesionPendiente error:', e); }
}

// ── Toggle totales ─────────────────────────────────────────────

/**
 * Muestra/oculta totales en tablas de ordenes.
 *
 * @example
 * toggleMostrarTotal();
 */
function toggleMostrarTotal() {
  mostrarTotales = document.getElementById('toggleTotales')?.checked || false;
  const summary = document.getElementById('summary');
  if (summary) summary.style.display = mostrarTotales ? 'grid' : 'none';
  const mes = document.getElementById('mesSelector')?.value;
  if (mes) {
    apiFetch('/api/ordenes?mes=' + mes)
      .then(r => r.json())
      .then(data => {
        if (typeof renderOrdenes === 'function') renderOrdenes(data.ordenes, 'ordenesTable', mes);
      });
  }
  if (typeof cargarTodas === 'function') cargarTodas();
}

// ── Buscador unificado ─────────────────────────────────────────

/**
 * Busca resultados en tiempo real (debounced) y los muestra en el dropdown.
 * Se ejecuta desde oninput del buscador general.
 *
 * @param {Event} e - Evento de input
 *
 * @example
 * // En HTML: oninput="buscarResultados(event)"
 */
window.buscarResultados = (e) => {
  clearTimeout(_buscarTimeout);
  const q = e.target.value.trim();
  const cont = document.getElementById('buscadorResultados');
  if (!cont) return;
  if (q.length < 2) { cont.classList.remove('show'); cont.innerHTML = ''; return; }
  cont.innerHTML = '<div class="sr-loading">Buscando\u2026</div>';
  cont.classList.add('show');
  _buscarTimeout = setTimeout(async () => {
    try {
      const r = await apiFetch('/api/buscar?q=' + encodeURIComponent(q));
      const data = await r.json();
      if (!data.resultados || !data.resultados.length) {
        cont.innerHTML = '<div class="sr-empty">Sin resultados</div>';
        return;
      }
      let html = '';
      data.resultados.forEach(item => {
        let onclick = 'cerrarBusqueda();';
        if (item.tipo === 'referencia') {
          onclick += 'abrirReferencia(' + (item.id || 0) + ')';
        } else {
          onclick += 'abrirResultado(' +
            "'" + escAttr(String(item.tipo)) + "'," +
            "'" + escAttr(String(item.titulo)) + "'," +
            "'" + escAttr(String(item.subtitulo || '')) + "'," +
            "'" + escAttr(String(item.detalle || '')) + "'" +
            ')';
        }
        html += '<div class="sr-item" onclick="' + onclick + '">' +
          '<div class="sr-type">' + esc(item.tipo) + '</div>' +
          '<div class="sr-title">' + esc(item.titulo) + '</div>' +
          (item.subtitulo ? '<div class="sr-sub">' + esc(item.subtitulo) + '</div>' : '') +
          (item.detalle ? '<div class="sr-sub" style="color:var(--muted)">' + esc(item.detalle) + '</div>' : '') +
          '</div>';
      });
      cont.innerHTML = html;
    } catch (e) {
      cont.innerHTML = '<div class="sr-empty">Error al buscar</div>';
    }
  }, 250);
};

/**
 * Cierra el dropdown del buscador y limpia el input.
 */
window.cerrarBusqueda = () => {
  const cont = document.getElementById('buscadorResultados');
  if (cont) cont.classList.remove('show');
  const input = document.getElementById('buscadorInput');
  if (input) input.value = '';
};

// ── Timer / Cronometro ────────────────────────────────────────

/**
 * Inicia, reanuda o finaliza el cronometro de reparacion.
 *
 * @param {number} ordenId - ID de la orden
 * @param {number|string} numero - Numero visible de la orden
 *
 * @example
 * window.toggleTimer(123, '11459');
 */
window.toggleTimer = async (ordenId, numero) => {
  if (_timerOrdenId === ordenId && _timerInterval) {
    await window.finalizarTimer();
    return;
  }
  if (_timerOrdenId === ordenId && !_timerInterval) {
    await window.reanudarTimer();
    return;
  }
  if (_timerOrdenId !== null) {
    mostrarMsg(
      'Ya hay una reparacion pendiente (#' + _timerOrdenId + '), finalizala o reanudala desde la barra flotante',
      'err'
    );
    return;
  }
  try {
    const r = await apiFetch('/api/sesiones/iniciar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ orden_id: ordenId })
    });
    const d = await r.json();
    if (!d.ok) { mostrarMsg(d.error || 'Error al iniciar', 'err'); return; }
    _currentSesionId = d.id;
    _timerOrdenId = ordenId;
    _timerNotas = '';
    _timerSeconds = d.duracion_acumulada || 0;
    const ftNumero = document.getElementById('ftNumero');
    if (ftNumero) ftNumero.textContent = numero;
    actualizarFtTime();
    _ftSetPaused(false);
    if (_timerInterval) clearInterval(_timerInterval);
    _timerInterval = setInterval(() => {
      _timerSeconds++;
      actualizarFtTime();
    }, 1000);
    if (typeof window.cargarReparaciones === 'function') window.cargarReparaciones();
  } catch (e) { mostrarMsg('Error al iniciar', 'err'); }
};

/**
 * Actualiza los botones y visibilidad de la barra flotante del timer.
 *
 * @param {boolean} isPaused - true si el timer esta pausado
 */
function _ftSetPaused(isPaused) {
  const pauseBtn = document.getElementById('ftPauseBtn');
  const resumeBtn = document.getElementById('ftResumeBtn');
  const ft = document.getElementById('floatingTimer');
  if (pauseBtn) pauseBtn.style.display = isPaused ? 'none' : 'inline-block';
  if (resumeBtn) resumeBtn.style.display = isPaused ? 'inline-block' : 'none';
  if (ft) ft.style.display = 'flex';
}

/**
 * Reanuda el cronometro pausado.
 */
window.reanudarTimer = async () => {
  if (!_currentSesionId || !_timerOrdenId) return;
  try {
    const r = await apiFetch('/api/sesiones/iniciar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ orden_id: _timerOrdenId })
    });
    const d = await r.json();
    if (!d.ok) { mostrarMsg(d.error || 'Error al reanudar', 'err'); return; }
    _currentSesionId = d.id;
    _timerSeconds = d.duracion_acumulada || _timerSeconds;
    if (_timerInterval) clearInterval(_timerInterval);
    _timerInterval = setInterval(() => {
      _timerSeconds++;
      actualizarFtTime();
    }, 1000);
    _ftSetPaused(false);
    mostrarMsg('\u25B6 Reanudada #' + _timerOrdenId, 'ok');
    if (typeof window.cargarReparaciones === 'function') window.cargarReparaciones();
  } catch (e) { mostrarMsg('Error al reanudar', 'err'); }
};

/**
 * Pausa el cronometro activo y guarda las notas.
 */
window.pausarTimer = async () => {
  if (!_currentSesionId) return;
  if (_timerInterval) { clearInterval(_timerInterval); _timerInterval = null; }
  const notasExtra = prompt('Notas de esta pausa (opcional):', '');
  _timerNotas = (_timerNotas + ' | ' + (notasExtra || '')).trim().replace(/^\s*\|\s*/, '');
  try {
    const r = await apiFetch('/api/sesiones/pausar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: _currentSesionId, duracion_segundos: _timerSeconds, notas: _timerNotas })
    });
    const d = await r.json();
    if (!d.ok) { mostrarMsg('Error al pausar', 'err'); return; }
    const mins = Math.floor(_timerSeconds / 60);
    const secs = _timerSeconds % 60;
    mostrarMsg('\u23F8 Pausada \u2014 #' + _timerOrdenId + ' (' + mins + 'min ' + secs + 's)', 'ok');
    _ftSetPaused(true);
    if (typeof window.cargarReparaciones === 'function') window.cargarReparaciones();
  } catch (e) { mostrarMsg('Error al pausar', 'err'); }
};

/**
 * Finaliza el cronometro y guarda la sesion completa.
 */
window.finalizarTimer = async () => {
  if (!_currentSesionId) return;
  if (_timerInterval) { clearInterval(_timerInterval); _timerInterval = null; }
  const notasExtra = prompt('Notas finales de la sesion (opcional):', '');
  const notasFinales = (_timerNotas + ' | ' + (notasExtra || '')).trim().replace(/^\s*\|\s*/, '');
  try {
    const r = await apiFetch('/api/sesiones/finalizar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: _currentSesionId, duracion_segundos: _timerSeconds, notas: notasFinales })
    });
    const d = await r.json();
    if (!d.ok) { mostrarMsg('Error al finalizar', 'err'); return; }
    const mins = Math.floor(_timerSeconds / 60);
    const secs = _timerSeconds % 60;
    mostrarMsg('\u2705 Orden #' + _timerOrdenId + ' finalizada \u2014 ' + mins + 'min ' + secs + 's', 'ok');
    const ft = document.getElementById('floatingTimer');
    if (ft) ft.style.display = 'none';
    _currentSesionId = null;
    _timerOrdenId = null;
    _timerSeconds = 0;
    _timerNotas = '';
    if (typeof window.cargarReparaciones === 'function') window.cargarReparaciones();
  } catch (e) { mostrarMsg('Error al finalizar', 'err'); }
};

/**
 * Actualiza el display del cronometro en la barra flotante.
 */
function actualizarFtTime() {
  const m = String(Math.floor(_timerSeconds / 60)).padStart(2, '0');
  const s = String(_timerSeconds % 60).padStart(2, '0');
  const ftTime = document.getElementById('ftTime');
  if (ftTime) ftTime.textContent = m + ':' + s;
}

// ── Helpers menores ────────────────────────────────────────────

/**
 * Escapa un valor para usarlo dentro de un atributo HTML (comillas simples).
 *
 * @param {string} s - Valor a escapar
 * @returns {string} Valor escapado para atributo
 */
function escAttr(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/'/g, '&apos;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Obtiene o genera un deviceId persistente en localStorage.
 *
 * @returns {string} ID unico del dispositivo
 */
function _getDeviceId() {
  let id = localStorage.getItem('deviceId');
  if (!id) {
    id = 'dev_' + Math.random().toString(36).slice(2, 10) + '_' + Date.now().toString(36);
    localStorage.setItem('deviceId', id);
  }
  return id;
}

// ── Exponer en window (para compatibilidad onclick) ────────────
window.API_BASE = API_BASE;
window.ACCESS_TOKEN = ACCESS_TOKEN;
window.REFRESH_TOKEN = REFRESH_TOKEN;
window.CURRENT_USER = CURRENT_USER;
window.VALOR_PUNTO = VALOR_PUNTO;
window.mostrarMsg = mostrarMsg;
window.esc = esc;
window.apiFetch = apiFetch;
window._apiPath = _apiPath;
window._restCompat = _restCompat;
window.tryRefresh = tryRefresh;
window.showLogin = showLogin;
window.hideLogin = hideLogin;
window.login = login;
window.logout = logout;
window.checkAuth = checkAuth;
window.init = init;
window.restaurarSesionPendiente = restaurarSesionPendiente;
window.toggleMostrarTotal = toggleMostrarTotal;
window._getDeviceId = _getDeviceId;
window._ftSetPaused = _ftSetPaused;
window.actualizarFtTime = actualizarFtTime;
