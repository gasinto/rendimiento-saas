# Design: JC-Sistema — Sidebar, reorganización de vistas y extracción del monolito

## Technical Approach

Refactor del frontend monolítico (`index.html`, 5046 líneas) a archivos modulares sin cambiar el stack (vanilla JS + CSS puro). Se reemplaza la navegación horizontal por una sidebar lateral con 3 secciones agrupadas, se consolidan vistas duplicadas (órdenes), se elimina el clasificador, se renombra BoardDoctor a Diagramas, se agregan 4 placeholders, y se extrae todo el código a archivos individuales por responsabilidad. Sin nuevas dependencias, sin build step, sin cambios en backend.

## Architecture Decisions

### AD1: Funciones globales en `window` (onclick compat)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A: Seguir exponiendo en `window` | + Mínimo cambio, 100% retrocompatible con `onclick` en HTML. - Contamina global scope. | ✅ **Elegida**. Todas las funciones llamadas desde HTML (`onclick`, `oninput`, `onchange`) se exponen en `window`. Las internas se mantienen como `const`/`let` locales. |
| B: Delegación de eventos con addEventListener | + Sin `onclick` en HTML, scope más limpio. - Requiere modificar TODO el HTML inline + refactor de todas las vistas. Riesgo alto de romper funcionalidad. | ❌ Descartada. El HTML actual tiene ~80 atributos `onclick`/`oninput`. Migrar a delegación duplica el riesgo y no aporta valor para un equipo de 1 persona. El paso a delegación puede hacerse como refactor futuro. |

Fundamento: la app actual es 100% `onclick`-based. Exponer en `window` es el puente más seguro. Cada función existente se declara como `window.nombre = function(...) {...}` en su archivo destino.

### AD2: NAV_CONFIG como única fuente de verdad

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A: Array centralizado en `navigation.js` | + + Agregar vista = 3 pasos exactos. Renderizado y routing automáticos. | ✅ **Elegida**. `NAV_CONFIG` define items, secciones, íconos, IDs y si es placeholder. `renderSidebar()` genera el HTML desde este array. `cambiarVista()` lo usa para mapear IDs a funciones. |
| B: HTML hardcodeado en index.html | + - Cada vista nueva requiere tocar HTML + JS + CSS. Propenso a errores. | ❌ Descartada. Justamente lo que queremos evitar. |

### AD3: Migración en 4 fases sin feature flags

No se usan feature flags porque no hay deploy progresivo (todo estático). Se trabaja sobre el mismo `index.html` transformándolo fase por fase, con commits atómicos por fase. Si algo se rompe, `git revert` del commit.

### AD4: Vista Reportes como standalone (no modal)

El spec define Reportes como vista standalone en la sidebar, pero su lógica actual (`abrirModalInforme`, `generarInforme`, `descargarPDF`, `descargarTXT`) vive en `viewEstadisticas` y usa el modal `#placaModal`. Se extrae a `views/reports.js` sin cambiar la lógica interna — solo se cambia el entry point: en vez de `abrirModalInforme()`, se llama `cargarReportes()` que renderiza el contenido inline en `viewReportes` y conserva la opción de abrir vista previa en el mismo contenedor. El modal overlay `#placaModal` se mantiene para otras vistas.

## Data Flow

```
[HTML] ──<link src="js/navigation.js">──→ renderSidebar() → genera <nav id="sidebar">
         ──<link src="js/views/orders.js">──→ expone window.cargarMes(), window.agregarOrden()
         
User click sidebar item
  → onclick="cambiarVista('ordenes')" 
  → navigation.cambiarVista('ordenes')
     → 1. Oculta todos los view containers (querySelectorAll("[id^=view]"))
     → 2. Muestra contenedor #viewOrdenes (display:block)
     → 3. Marca item activo en sidebar (#sidebar a[data-vista=ordenes].active)
     → 4. Ejecuta carga condicional (if/vistaMap): cargarMes(), cargarTodas()
     → 5. Vista llama a apiFetch("/api/orders/") → renderOrdenes() → innerHTML
```

### Flujo de carga inicial

```
checkAuth()
  → login / tryRefresh / checkAuth from localStorage
  → hideLogin() → init()
     → NAV_CONFIG → renderSidebar()
     → cargarMeses(), cargarTipos()
     → cambiarVista('dashboard') ← primera vista post-login
```

## File Changes

### static/

| File | Action | Description |
|------|--------|-------------|
| `index.html` | **Modify** | Mantiene estructura HTML, header, view containers, scripts. Remueve `<style>` inline → `<link>` a CSS. Remueve `<script>` monolítico → `<script src="...">` individuales. Elimina tabs, clasificador. Agrega sidebar nav. |
| `css/style.css` | **Create** | Variables CSS, reset, tipografía, cards, tablas, forms, header, modal, summary, search, timer, dashboard-charts, login. Hereda TODO el `<style>` de index.html. |
| `css/sidebar.css` | **Create** | Sidebar: `position:fixed`, 240px, secciones, hover, active, scroll, hamburguesa, overlay, responsive <768px. |
| `js/main.js` | **Create** | Entry point: `init()`, `API_BASE`, `ACCESS_TOKEN`, `REFRESH_TOKEN`, `CURRENT_USER`, `VALOR_PUNTO`, `apiFetch()`, `_apiPath()`, `_restCompat()`, `mostrarMsg()`, `esc()`, `showLogin()`, `hideLogin()`, `login()`, `logout()`, `checkAuth()`, `tryRefresh()`. Variables de timer: `_timerSeconds`, `_timerOrdenId`, `_currentSesionId`, `_timerNotas`, `_ftSetPaused()`, `actualizarFtTime()`. Buscador general: `buscarResultados()`, `cerrarBusqueda()`. |
| `js/auth.js` | **Create** | Se fusiona en `main.js` — el auth está integrado con `apiFetch()`. Si se prefiere separar, se extraen `login()`, `logout()`, `checkAuth()`, `tryRefresh()`, `showLogin()`, `hideLogin()`. |
| `js/navigation.js` | **Create** | `NAV_CONFIG`, `renderSidebar()`, `cambiarVista()`, `toggleSidebar()`, `closeSidebar()`. Exporta en window: `cambiarVista`, `toggleSidebar`. |
| `js/components/table.js` | **Create** | `renderTable(headers, rows, opts)` |
| `js/components/card.js` | **Create** | `renderCard(config)` |
| `js/components/modal.js` | **Create** | `openModal(config)`, `closeModal()` |
| `js/components/form.js` | **Create** | `renderField(config)`, helpers |
| `js/components/badge.js` | **Create** | `renderBadge(text, variant)` |
| `js/views/dashboard.js` | **Create** | `cargarDashboard()`, `renderSummaryCards()`, `renderBarChart()`, `renderTablaMensual()`, `renderTopTipos()`, `renderTasaExitoMensual()`, `renderTopMarcas()`, `renderTopModelos()`, `renderTopPlacas()`. Adaptar `cargarDashboard()` (ex `viewEstadisticas`). Botón "Generar informe" → `cambiarVista('reportes')`. |
| `js/views/orders.js` | **Create** | `cargarMes()`, `cargarTodas()`, `cargarMeses()`, `agregarOrden()`, `eliminarOrden()`, `renderOrdenes()`, `toggleMostrarTotal()`. Exporta en window: `cargarMes`, `cargarTodas`, `cargarMeses`, `agregarOrden`, `eliminarOrden`, `toggleMostrarTotal`. |
| `js/views/repairs.js` | **Create** | `cargarReparaciones()`, `cargarEmpresasSelect()`, `openAddReparacion()`. Exporta en window: `cargarReparaciones`, `cargarEmpresasSelect`, `openAddReparacion`. |
| `js/views/boards.js` | **Create** | Renderizado de placas + Firebase. `renderPlacas()`, `openAddPlaca()`, `openAddCaja()`, `exportCSV()`, `backupDownload()`, `openBackups()`, `renderPlacaModal()`. Toda la lógica Firebase + S (estado). Exporta funciones necesarias. |
| `js/views/ics.js` | **Create** | `fetchIcs(q)`, `openAddIc()`. Exporta: `fetchIcs`, `openAddIc`. |
| `js/views/measurements.js` | **Create** | `cargarMediciones()`. Exporta: `cargarMediciones`. |
| `js/views/board-points.js` | **Create** | `cargarMedicionesPlaca()`. Exporta: `cargarMedicionesPlaca`. |
| `js/views/solutions.js` | **Create** | `cargarSoluciones()`, `openAddSolucion()`. Exporta: `cargarSoluciones`, `openAddSolucion`. |
| `js/views/references.js` | **Create** | `cargarReferencias()`, `abrirAgregarReferencia()`. Exporta: `cargarReferencias`, `abrirAgregarReferencia`. |
| `js/views/diagramas.js` | **Create** | `buscarBoardDoctor(tab)`, `debounceBd(tab)`, `importarBoardDoctor()`, `buscarDatasheetDeModelo()`. Nombres internos preservan "boarddoctor". Exporta en window. |
| `js/views/config.js` | **Create** | `cargarConfiguracion()`, `guardarValorPunto()`, `agregarPuntaje()`, `agregarTipoEquipo()`, `agregarEmpresa()`. Exporta en window. |
| `js/views/reports.js` | **Create** | `cargarReportes()`, `generarInforme()`, `cargarPeriodosInforme()`, `cambiarTipoInforme()`, `renderPreview()`, `descargarPDF()`, `descargarTXT()`. La lógica es la misma de `abrirModalInforme()` pero renderizada inline. Exporta `generarInforme`, `cargarPeriodosInforme`, `cambiarTipoInforme`, `descargarPDF`, `descargarTXT`. |
| `js/views/clients.js` | **Create** | Placeholder: `renderPlaceholder('👤', 'Clientes', 'Gestión de clientes — próximamente disponible')`. |
| `js/views/budgets.js` | **Create** | Placeholder: `renderPlaceholder('💰', 'Presupuestos', 'Presupuestos — próximamente disponible')`. |
| `js/views/invoices.js` | **Create** | Placeholder: `renderPlaceholder('🧾', 'Facturación', 'Facturación — próximamente disponible')`. |
| `js/views/inventory.js` | **Create** | Placeholder: `renderPlaceholder('📦', 'Inventario', 'Inventario — próximamente disponible')`. |
| `placas-data.js` | **Unchanged** | No se modifica. Datos de Firebase. |

### docs/

| File | Action | Description |
|------|--------|-------------|
| `docs/README.md` | **Create** | Visión general de la arquitectura frontend (~40 líneas) |
| `docs/ARCHITECTURE.md` | **Create** | Flujo de datos, funciones-componente, mención superadmin futuro (~100 líneas) |
| `docs/COMPONENTS.md` | **Create** | Catálogo de componentes con firma, ejemplo, justificación (~150 líneas) |
| `docs/NAVIGATION.md` | **Create** | NAV_CONFIG, renderSidebar, cambiarVista, cómo agregar vistas (~80 líneas) |
| `docs/STYLE.md` | **Create** | Variables CSS, convenciones, guía visual (~80 líneas) |
| `docs/EXAMPLES.md` | **Create** | Ejemplos completos de extensión (~150 líneas) |

### Deleted

| File | Reason |
|------|--------|
| `viewMes` (HTML div) | Contenido migrado a `viewOrdenes` |
| `viewGeneral` (HTML div) | Contenido migrado a `viewOrdenes` |
| `viewClasificador` (HTML div + styles) | Funcionalidad eliminada completamente |
| `viewClasificador` CSS (~80 líneas en `<style>`) | Eliminado |
| `clasData` + ~15 funciones clasificador | Eliminado del JS |

## Migration Plan (4 Fases)

### Fase 1: Preparación (sin riesgo)

**Commits**: 2-3 commits atómicos. Sin cambios funcionales.

1. Crear `static/css/` y `static/js/` con subcarpetas `components/` y `views/`
2. Extraer TODO el `<style>` de index.html a `css/style.css` (conservando exactamente el mismo contenido)
3. Extraer CSS de tabs/clasificador a `css/style.css` (se eliminarán después)
4. Crear `js/main.js` con las funciones globales independientes: `API_BASE`, tokens, `apiFetch()`, `_apiPath()`, `_restCompat()`, `mostrarMsg()`, `esc()`, `showLogin()`, `hideLogin()`, `login()`, `logout()`, `checkAuth()`, `tryRefresh()`, variables de timer, buscador general
5. Crear `js/components/` con los 5 componentes puros (table, card, modal, form, badge) — funciones que NO existen en index.html pero se usarán en vistas nuevas
6. Agregar `<link rel="stylesheet">` y `<script src="...">` al index.html
7. **NO modificar** el bloque `<style>` ni `<script>` aún — co-existen
8. Verificar que la app carga sin errores con ambas fuentes

**Verificación**: La app funciona exactamente igual, los estilos no cambian (mismo CSS), las funciones están definidas dos veces pero las segundas definiciones sobrescriben a las primeras sin cambios visibles.

### Fase 2: Sidebar + navegación

**Commit**: 1 commit.

1. Crear `js/navigation.js` con:
   - `NAV_CONFIG` — el array completo del spec
   - `renderSidebar()` — genera `<nav id="sidebar">` desde NAV_CONFIG
   - `cambiarVista(vistaId)` — reemplaza el original, usa NAV_CONFIG para mapeo
   - `toggleSidebar()` / `closeSidebar()` — para mobile
2. Crear `css/sidebar.css` con todos los estilos de sidebar + overlay + responsive
3. En `index.html`:
   - Reemplazar `<div class="tabs">...</div>` por `<nav id="sidebar"></nav>`
   - Agregar botón hamburguesa en el header: `<button id="hamburgerBtn" onclick="toggleSidebar()">☰</button>`
   - Agregar overlay div: `<div id="sidebarOverlay" onclick="closeSidebar()"></div>`
4. `renderSidebar()` se llama en `init()` de `main.js` (o se agrega una llamada inline)
5. Mantener temporalmente los view containers originales con sus IDs
6. `cambiarVista()` ahora:
   - Oculta TODOS los `[id^=view]` containers
   - Muestra el correspondiente
   - Marca el ítem de sidebar activo
   - Ejecuta carga de datos

**Verificación**: Todas las vistas existentes funcionan desde la sidebar. El marcado activo funciona. Mobile toggle funciona.

### Fase 3: Vistas individuales

**Commits**: 1 commit principal + 1 commit de limpieza.

1. Crear `js/views/orders.js` con `cargarMes()`, `cargarTodas()`, `cargarMeses()`, `agregarOrden()`, `eliminarOrden()`, `renderOrdenes()`, `toggleMostrarTotal()` — y exponer en window
2. Crear cada vista existente en su archivo individual
3. En el index.html:
   - Reemplazar `viewMes` + `viewGeneral` por `viewOrdenes` con ambos paneles
   - Mantener `viewEstadisticas` → ID `viewDashboard` (alias en cambiarVista)
   - Mantener `viewDiagramas` exactamente igual pero renombrar texto visible
   - Eliminar `viewClasificador` del HTML (div + todo su contenido)
   - Agregar 4 divs placeholder: `viewClientes`, `viewPresupuestos`, `viewFacturacion`, `viewInventario`
4. Agregar contenedor `viewReportes` — la lógica de informe se renderiza inline aquí
5. En el `<script>` inline eliminar:
   - Todo el clasificador (~15 funciones + `clasData`)
   - Las funciones de órdenes (ahora en orders.js)
   - Las funciones de dashboard/reportes (ahora en sus archivos)
   - Las funciones ya extraídas a main.js
   - Dejar solo lo que se esté migrando gradualmente si hay dependencias
6. Agregar `<script src="js/views/*.js">` en el orden correcto

**Verificación**: Cada vista funciona individualmente. `agregarOrden()`, `cargarMes()`, `cargarTodas()` funcionan desde orders.js. No hay referencias a `viewClasificador`.

### Fase 4: Documentación + limpieza final

**Commit**: 1 commit.

1. Crear los 6 archivos `docs/` según la especificación
2. Agregar JSDoc completo en todas las funciones públicas de todos los archivos JS
3. Verificar que ningún `onclick` en HTML quede huérfano
4. Eliminar CSS no usado (clasificador, tabs viejos)
5. Verificar que no haya errores en consola
6. Último commit: limpieza del `<script>` inline en index.html — si queda algo que no se pudo extraer, evaluar si se deja o se extrae

## NAV_CONFIG y manejo de navegación

### Estructura exacta de NAV_CONFIG

```javascript
const NAV_CONFIG = [
  {
    section: 'TALLER',
    items: [
      { id: 'dashboard',    icon: '🏠', label: 'Dashboard' },
      { id: 'ordenes',      icon: '📋', label: 'Órdenes' },
      { id: 'reparaciones', icon: '🔧', label: 'Reparaciones' },
      { id: 'clientes',     icon: '👤', label: 'Clientes', placeholder: true },
      { id: 'presupuestos', icon: '💰', label: 'Presupuestos', placeholder: true },
      { id: 'facturacion',  icon: '🧾', label: 'Facturación', placeholder: true },
      { id: 'inventario',   icon: '📦', label: 'Inventario', placeholder: true },
    ],
  },
  {
    section: 'CONOCIMIENTO',
    items: [
      { id: 'placas',        icon: '🔩', label: 'Placas' },
      { id: 'ics',           icon: '🔌', label: 'ICs' },
      { id: 'mediciones',    icon: '📏', label: 'Mediciones' },
      { id: 'puntos-placa',  icon: '📐', label: 'Puntos placa' },
      { id: 'soluciones',    icon: '💡', label: 'Soluciones' },
      { id: 'referencias',   icon: '📖', label: 'Referencias' },
      { id: 'diagramas',     icon: '🔍', label: 'Diagramas' },
    ],
  },
  {
    section: 'ADMIN',
    items: [
      { id: 'config',   icon: '⚙️', label: 'Config' },
      { id: 'reportes', icon: '📊', label: 'Reportes' },
    ],
  },
];
```

### Cómo renderSidebar() genera HTML

```javascript
function renderSidebar() {
  const sidebar = document.getElementById('sidebar');
  let html = '';
  // Logo/header de la sidebar
  html += `<div class="sidebar-header">📊 Rendimiento</div>`;
  
  NAV_CONFIG.forEach(group => {
    html += `<div class="sidebar-section-label">${group.section}</div>`;
    html += `<div class="sidebar-section">`;
    group.items.forEach(item => {
      html += `<a class="sidebar-item" data-vista="${item.id}" onclick="cambiarVista('${item.id}')">
        <span class="sidebar-icon">${item.icon}</span>
        <span class="sidebar-label">${item.label}</span>
      </a>`;
    });
    html += `</div>`;
  });
  
  // User area at bottom
  html += `<div class="sidebar-footer">
    <span id="sidebarUser">👤 <span id="sidebarUserName"></span></span>
    <button onclick="logout()" class="sidebar-logout">Salir</button>
  </div>`;
  
  sidebar.innerHTML = html;
}
```

### Cómo cambiarVista() maneja el marcado activo

```javascript
function cambiarVista(vistaId) {
  // 1. Hide all view containers
  document.querySelectorAll('[id^="view"]').forEach(el => {
    el.style.display = 'none';
  });
  
  // 2. Show target view
  const targetId = VIEW_ALIASES[vistaId] || vistaId;
  const container = document.getElementById('view' + targetId.charAt(0).toUpperCase() + targetId.slice(1));
  if (container) container.style.display = 'block';
  
  // 3. Mark sidebar active
  document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active'));
  const activeItem = document.querySelector(`.sidebar-item[data-vista="${vistaId}"]`);
  if (activeItem) activeItem.classList.add('active');
  
  // 4. Load data (from a registry/map)
  const loaders = {
    dashboard: () => cargarDashboard(),
    ordenes: () => { cargarMes(); cargarTodas(); },
    placas: () => setTimeout(() => document.getElementById('placaQ')?.focus(), 100),
    ics: () => { fetchIcs(); setTimeout(() => document.getElementById('icsQ')?.focus(), 100); },
    mediciones: () => cargarMediciones(),
    'puntos-placa': () => cargarMedicionesPlaca(),
    soluciones: () => cargarSoluciones(),
    referencias: () => cargarReferencias(),
    config: () => cargarConfiguracion(),
    diagramas: () => setTimeout(() => document.getElementById('bdDiagramaQ')?.focus(), 100),
    reparaciones: () => { window.cargarReparaciones(); window.cargarEmpresasSelect(); },
    reportes: () => cargarReportes(),
  };
  
  if (loaders[vistaId]) loaders[vistaId]();
  
  // 5. Close sidebar on mobile
  closeSidebar();
}
```

VIEW_ALIASES mapea IDs viejos a nuevos:
```
{ 'estadisticas': 'dashboard', 'referencia': 'referencias', 'mediciones-placa': 'puntos-placa' }
```

### Cómo se agregan nuevas vistas (3 pasos)

1. **Crear** `static/js/views/mi-vista.js` con la función de renderizado y exponer en window si usa `onclick`
2. **Agregar** entrada en `NAV_CONFIG` en `navigation.js` (con `placeholder: true` si no tiene lógica)
3. **Agregar** `<script src="js/views/mi-vista.js">` en `index.html` y contenedor `<div id="viewMiVista">`

Si requiere carga de datos, agregar entrada en el mapa `loaders` de `cambiarVista()`.

## Component Specification

### renderTable

```javascript
/**
 * @param {string[]} headers - Nombres de columnas
 * @param {Array<Array<string>>} rows - Datos por fila
 * @param {object} [opts]
 * @param {string} [opts.className] - Clase extra para <table>
 * @param {boolean} [opts.responsive] - Envolver en <div> scrollable
 * @param {string} [opts.emptyMessage] - Mensaje si rows vacío
 * @returns {string} HTML de tabla completa
 */
```

**Casos borde**: rows vacío → mensaje configurable. headers vacío → tabla sin thead. responsive=true → `<div style="overflow-x:auto"><table>...</table></div>`. No escapa HTML internamente (las vistas controlan su contenido).

**Integración CSS**: usa las clases `table` existentes del `<style>` original. Compatible con `.table`, `.ref-table`, `.clasif-eq-table`.

### renderCard

```javascript
/**
 * @param {object} config
 * @param {string} config.title - Título visible
 * @param {string} config.content - HTML del cuerpo
 * @param {string} [config.className] - Clase extra
 * @param {string} [config.icon] - Emoji antes del título
 * @param {'sm'|'md'|'lg'} [config.size] - Tamaño de padding
 * @returns {string} HTML de card
 */
```

**Casos borde**: content vacío → card con solo título. icon omitido → título sin emoji. className permite composición: `renderCard({..., className: 'card--compact'})`.

**Integración CSS**: usa `.card` existente (border-radius, padding, background). Las cards se usan en dashboard (summary), boarddoctor (4 cards), y placeholders.

### openModal

```javascript
/**
 * @param {object} config
 * @param {string} config.title - Título del modal
 * @param {string} config.content - HTML del cuerpo
 * @param {string} [config.subtitle] - Subtítulo menor
 * @param {Array<{label:string, onClick:Function, variant?:string, className?:string}>} [config.buttons]
 * @param {Function} [config.onClose] - Callback al cerrar
 * @param {boolean} [config.wide] - Clase .modal-wide
 * @returns {void}
 */
```

**Comportamiento**: reutiliza `#placaModal` y `#placaModalInner` existentes. Overlay con `onclick="if(event.target===this)closeModal()"` (se mantiene en HTML). Agrega `config.wide` → clase `modal-wide`. Botón por defecto "Cerrar" si no se pasan buttons.

**Casos borde**: llamado sin `#placaModal` presente → no crash (verifica existencia). Múltiples modales → solo uno a la vez (reemplaza contenido). `onClose` se llama después de ocultar el modal.

### renderField

```javascript
/**
 * @param {object} config
 * @param {string} config.label - Texto del label
 * @param {string} config.id - ID único para el input
 * @param {'text'|'date'|'number'|'select'|'checkbox'|'textarea'|'email'|'password'} config.type
 * @param {string} [config.value] - Valor por defecto
 * @param {Array<{value:string, label:string}>} [config.options] - Para select
 * @param {string} [config.placeholder]
 * @param {boolean} [config.required]
 * @param {string} [config.helpText] - Texto de ayuda debajo del field
 * @returns {string}
 */
```

**Casos borde**: type='select' sin options → `<select><option>Sin opciones</option></select>`. required=true → atributo `required` + label con asterisco visual. helpText → `<small class="field-help">texto</small>`.

### renderBadge

```javascript
/**
 * @param {string} text - Texto del badge
 * @param {'success'|'warning'|'danger'|'info'|'default'} variant - Color
 * @returns {string} HTML: <span class="badge badge--{variant}">{text}</span>
 */
```

**CSS asociado**: `.badge { font-size: 11px; padding: 2px 8px; border-radius: 999px; font-weight: 600; display: inline-block; }`. Variantes con bg-color semántico usando variables CSS existentes.

## CSS and Visual Design

### New CSS Variables for Sidebar

```css
:root {
  /* Existing */
  --bg: #141414;
  --card: #1c1c1c;
  --surface: #1e1e1e;
  --accent: #f0b429;
  /* ... */
  
  /* New for sidebar */
  --sidebar-width: 240px;
  --sidebar-bg: #1a1a1a;        /* Ligeramente más claro que --bg */
  --sidebar-item-hover: rgba(240, 180, 41, 0.08);
  --sidebar-item-active: rgba(240, 180, 41, 0.15);
  --sidebar-border: #2a2a2a;
  --sidebar-icon-width: 36px;
  --sidebar-collapsed-width: 0px;    /* Mobile: hidden */
  --sidebar-mobile-width: 280px;     /* Mobile: expanded */
  --overlay-bg: rgba(0, 0, 0, 0.5);
}
```

### Layout Adaptation

**Before** (current):
```css
.container { max-width: 1100px; margin: 0 auto; }
body { padding: 1rem; }
```

**After** (desktop):
```css
body { padding: 0; }
.container { margin-left: var(--sidebar-width); max-width: none; padding: 1rem 1.5rem; }
#sidebar { position: fixed; left: 0; top: 0; width: var(--sidebar-width); height: 100vh; ... }
```

**Mobile** (< 768px):
```css
@media (max-width: 768px) {
  .container { margin-left: 0; padding: 0.75rem; }
  #sidebar { transform: translateX(-100%); }
  #sidebar.open { transform: translateX(0); width: var(--sidebar-mobile-width); }
  #sidebarOverlay { display: none; position: fixed; inset: 0; background: var(--overlay-bg); z-index: 99; }
  #sidebarOverlay.show { display: block; }
  #hamburgerBtn { display: block; }
}
```

### Sidebar Specific Styles

```css
#sidebar {
  position: fixed; left: 0; top: 0;
  width: var(--sidebar-width); height: 100vh;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  z-index: 100;
  display: flex; flex-direction: column;
  overflow-y: auto; /* scroll interno */
  transition: transform 0.2s ease;
}

.sidebar-header {
  padding: 1rem 1rem 0.75rem;
  font-size: 1.1rem; font-weight: 700;
  border-bottom: 1px solid var(--sidebar-border);
}

.sidebar-section-label {
  padding: 1rem 1rem 0.35rem;
  font-size: 0.65rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--muted);
}

.sidebar-item {
  display: flex; align-items: center;
  padding: 0.5rem 1rem;
  gap: 0.5rem;
  cursor: pointer;
  color: var(--text);
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}
.sidebar-item:hover { background: var(--sidebar-item-hover); }
.sidebar-item.active { background: var(--sidebar-item-active); border-left-color: var(--accent); }

.sidebar-icon { width: var(--sidebar-icon-width); text-align: center; font-size: 1.1rem; flex-shrink: 0; }
.sidebar-label { font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.sidebar-footer {
  margin-top: auto;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--sidebar-border);
  display: flex; justify-content: space-between; align-items: center;
  font-size: 0.8rem;
}
```

## Global Function Handling

**Decisión**: Opción A — exponer en `window`.

Todas las funciones llamadas desde HTML (onclick, oninput, onchange, onkeydown) se asignan explícitamente a `window`.

Patrón estándar en cada archivo:

```javascript
// views/orders.js
async function _cargarMes() { /* ... */ }
async function _agregarOrden() { /* ... */ }

// Exponer solo lo necesario para onclick
window.cargarMes = _cargarMes;
window.agregarOrden = _agregarOrden;
window.eliminarOrden = _eliminarOrden;
window.cargarTodas = _cargarTodas;
window.cargarMeses = _cargarMeses;
window.toggleMostrarTotal = _toggleMostrarTotal;
```

Las funciones internas (no llamadas desde HTML) se declaran como `function` normales o `const` dentro del módulo, sin exponer.

**Fundamento**: ~80 atributos onclick/oninput existen en el HTML. Cambiar a addEventListener requeriría modificar cada uno + asegurar que los event listeners se registran después de que los elementos existen. Para un equipo de 1 persona, el riesgo de omitir un listener o romper una interacción es alto. La exposición en window es directa, verificable, y no introduce cambios de comportamiento. La migración a delegación puede planificarse como refactor futuro si se justifica.

## Lazy Loading de Placeholders

Los placeholders NO cargan datos. Garantía:

1. En `NAV_CONFIG`, `placeholder: true` marca vistas placeholder
2. En `cambiarVista()`, las vistas placeholder NO tienen entrada en el mapa `loaders`
3. Los archivos JS de placeholders (`clients.js`, `budgets.js`, etc.) solo tienen `renderPlaceholder()` — sin fetch, sin API calls
4. Los divs `<div id="viewClientes">...</div>` contienen el HTML inline generado al cargar la página, pero el display default es `none`

Para vistas existentes, la carga de datos ocurre en el mapa `loaders` de `cambiarVista()`, igual que ahora.

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Perder función `onclick` durante extracción a archivo separado | Baja | Alto | Cada extracción verifica que la función existe en `window` post-migración. Test manual de cada vista. |
| Sidebar no se renderiza bien en mobile | Media | Medio | Probar en viewport < 768px con DevTools. overlay + toggle verificados. |
| CSS conflictos entre sidebar fija y layout centrado original | Media | Alto | Usar `margin-left` en `.container`. Probar dashboard, cards, tablas. Layout responsive con media queries. |
| Dependencia circular entre archivos JS | Baja | Medio | main.js es independiente. navigation.js depende de main.js (API_BASE, etc. — no, navigation es auto-contenido). Las vistas llaman a sus propios helpers. Sin imports — solo script tags en orden. |
| Firebase/placas-data.js deja de funcionar por cambio en orden de carga | Baja | Alto | `placas-data.js` se carga AL FINAL, después de todos los view JS. El script module de Firebase se carga al final también. Verificar que `renderPlacas()` existe cuando Firebase `onSnapshot` dispare. |
| Olvidar agregar `<script>` de una vista en index.html | Baja | Medio | Checklist post-migración con cada vista de la spec. Template de index.html con todos los scripts listados. |
| Regresión en alguna función del timer flotante | Baja | Alto | El timer se mantiene 100% igual — solo se reubica en `main.js` (Fase 1). Se verifica manualmente creando una orden y confirmando timer. |

## Testing Strategy

No hay test runner configurado (`strict_tdd: false`). La verificación es manual:

| Capa | Qué probar | Cómo |
|------|-----------|------|
| Carga inicial | App carga sin errores en consola | Abrir app, verificar Chrome DevTools Console |
| Login | Auth fluye, tokens se guardan | Login con credenciales válidas, verificar localStorage |
| Sidebar | Renderizado, active state, hover | Click en cada item, verificar clase active |
| Mobile | Toggle, overlay, cierre | DevTools viewport < 768px |
| Cada vista existente | Funciona igual que antes | Navegar a cada vista, verificar datos cargan |
| Órdenes | Mes, todas, agregar, eliminar | Agregar orden, verificar tabla, eliminar |
| Placeholders | Muestran mensaje correcto | Click en Clientes, Presupuestos, Facturación, Inventario |
| Diagramas | BoardDoctor funciona con nuevo nombre | Buscar diagrama, IC, compatibilidad |
| Reportes | Modal inline funciona | Generar informe, descargar |

## Documentation to Generate

Ver RF6 en la especificación (sección 6) para el contenido detallado de cada archivo:

| File | Contenido principal |
|------|-------------------|
| `docs/README.md` | Visión general, stack, estructura de carpetas, dev setup, convenciones |
| `docs/ARCHITECTURE.md` | SPA con funciones-componente, flujo data (API → función → innerHTML), estado global mínimo, JWT auth, mención superadmin futuro como "Rol superadmin contemplado en arquitectura: bypassea tenant_id, sin implementar" |
| `docs/COMPONENTS.md` | Catálogo de 5 componentes con firma, @param, @returns, ejemplo, problema que resuelve |
| `docs/NAVIGATION.md` | NAV_CONFIG estructura, renderSidebar(), cambiarVista(), guía 3 pasos para agregar vistas, mobile behavior |
| `docs/STYLE.md` | Variables CSS (cada una explicada), convenciones de nombres, breakpoints, responsive |
| `docs/EXAMPLES.md` | 3 ejemplos: módulo Proveedores completo, columna en órdenes, nuevo componente renderList() |

## Open Questions

None — todas las preguntas abiertas del spec fueron resueltas en las decisiones confirmadas del diseño.
