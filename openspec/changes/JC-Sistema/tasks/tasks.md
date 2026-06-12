# JC-Sistema — Plan de tareas

## Resumen ejecutivo

Migración del frontend monolítico (`index.html`, 5046 líneas) a archivos modulares por responsabilidad: CSS separado, JS organizado en `main.js` + `navigation.js` + 5 componentes + 14 vistas, y documentación externa. Sin cambiar el stack (vanilla JS + CSS puro), sin build step, sin tocar backend.

**4 fases**, **~16 tareas accionables**, estimado **~600-700 líneas modificadas** en `index.html` + **~2500 líneas nuevas** en archivos separados.

---

## Convenciones

### Nombres de archivos

- **CSS**: `static/css/*.css` — kebab-case (ej: `sidebar.css`)
- **JS componentes**: `static/js/components/*.js` — kebab-case (ej: `table.js`)
- **JS vistas**: `static/js/views/*.js` — kebab-case, nombre corto (ej: `board-points.js`, `diagramas.js`)
- **JS core**: `main.js`, `auth.js`, `navigation.js`
- **Docs**: `docs/*.md` — MAYÚSCULAS (ej: `ARCHITECTURE.md`)

### Estilo de código

- **HTML**: Mantener `onclick`/`oninput` para compatibilidad. No migrar a addEventListener.
- **JS**: Toda función pública expuesta en `window.nombre = function`. Funciones internas como `function _nombre()` o `const _nombre`.
- **JSDoc obligatorio** en toda función pública: `@param`, `@returns`, `@example` en componentes.
- **Comentarios de sección**: `// ── Sección ────────────────────────────────────────────`
- **Variables CSS**: Usar `:root` existente. Nuevas variables con prefijo `--sidebar-*`.
- **Sin dependencias externas**: nada de npm, CDN, librerías.

### Commits

- Commits atómicos por tarea o grupo pequeño de tareas relacionadas.
- Prefijo `feat:` para features nuevas, `refactor:` para extracción de código, `docs:` para documentación.
- Mensajes en español (el proyecto está en español).
- NO hacer commit hasta que `sdd-apply` indique.

---

## Fase 1: Preparación

> Sin cambios funcionales. Creación de estructura y extracción de código existente. Co-existencia con el código original.

### T1.1: Crear estructura de carpetas

- [ ] Crear `static/css/`
- [ ] Crear `static/js/components/`
- [ ] Crear `static/js/views/`
- [ ] Verificar estructura:
  ```
  static/
    css/
    js/
      components/
      views/
  ```

**Dependencias**: Ninguna.
**Archivos**: Solo carpetas.
**Estimado**: ~5 min, 0 líneas de código.

---

### T1.2: Extraer CSS a `style.css`

- [ ] Crear `static/css/style.css` con TODO el contenido del bloque `<style>` del `index.html` (líneas 7-375)
- [ ] Agregar `<link rel="stylesheet" href="css/style.css">` en el `<head>` de `index.html`
- [ ] Mantener el `<style>` inline intacto (co-existencia)
- [ ] Verificar que la app carga visualmente igual (mismas reglas CSS, el segundo `<link>` no sobreescribe porque es idéntico)

**Dependencias**: T1.1.
**Archivos**: `static/css/style.css` (crear), `static/index.html` (modificar — agregar `<link>`).
**Estimado**: ~375 líneas extraídas, +1 línea en index.html.
**Riesgo**: Muy bajo — co-existencia garantiza que no se pierde nada.

---

### T1.3: Extraer core global a `main.js`

- [ ] Crear `static/js/main.js` con las funciones y variables globales INDEPENDIENTES del index.html (sin referencias a vistas):
  - `init()`, `API_BASE`, `ACCESS_TOKEN`, `REFRESH_TOKEN`, `CURRENT_USER`, `VALOR_PUNTO`
  - `_apiPath(url)`, `_restCompat()`, `apiFetch()`, `mostrarMsg()`, `esc()`
  - `showLogin()`, `hideLogin()`, `login()`, `logout()`, `checkAuth()`, `tryRefresh()`
  - Variables de timer: `_timerSeconds`, `_timerOrdenId`, `_currentSesionId`, `_timerNotas`
  - `_ftSetPaused()`, `actualizarFtTime()`, `pausarTimer()`, `reanudarTimer()`, `finalizarTimer()`
  - Buscador general: `buscarResultados()`, `cerrarBusqueda()`
  - Helpers: `toggleMostrarTotal()`, `_getDeviceId()`
- [ ] Agregar `<script src="js/main.js"></script>` en `index.html` ANTES del `<script>` monolítico
- [ ] Mantener el `<script>` inline intacto (co-existencia)
- [ ] Verificar que las funciones se definen dos veces pero la segunda (inline) NO sobreescribe comportamiento

**Dependencias**: T1.1.
**Archivos**: `static/js/main.js` (crear), `static/index.html` (modificar — agregar `<script>`).
**Estimado**: ~150 líneas extraídas.
**Riesgo**: Bajo — co-existencia. Las funciones del inline sobrescriben las de main.js, pero son idénticas.

---

### T1.4: Crear componentes base (table, card, modal, form, badge)

- [ ] Crear `static/js/components/table.js`:
  - `renderTable(headers, rows, opts)` — genera `<table>` completo
  - JSDoc completo con `@param`, `@returns`, `@example`
- [ ] Crear `static/js/components/card.js`:
  - `renderCard(config)` — genera `<div class="card">`
  - Soporte para `{title, content, className, icon, size}`
- [ ] Crear `static/js/components/modal.js`:
  - `openModal(config)` — usa `#placaModal` existente
  - `closeModal()` — cierra modal
  - Manejo de botones, variante `.modal-wide`, callback `onClose`
- [ ] Crear `static/js/components/form.js`:
  - `renderField(config)` — genera label + input/select
  - Tipos: text, date, number, select, checkbox, textarea, email, password
- [ ] Crear `static/js/components/badge.js`:
  - `renderBadge(text, variant)` — `<span class="badge badge--{variant}">`
  - Variantes: success, warning, danger, info, default
- [ ] Agregar `<script src="js/components/*.js">` en index.html (orden: table, card, modal, form, badge)
- [ ] Verificar que los componentes se cargan sin errores (aunque no se usen aún)

**Dependencias**: T1.1.
**Archivos**: 5 archivos nuevos en `static/js/components/`, `static/index.html` (agregar 5 scripts).
**Estimado**: ~200 líneas total (5 componentes × ~40 líneas c/u).
**Criterio**: Cada componente es una función pura — no se prueba visualmente hasta Fase 3.

---

## Fase 2: Sidebar + navegación

> Commit único. Se reemplazan los tabs horizontales por la sidebar. `cambiarVista()` se reescribe.

### T2.1: Crear `navigation.js` con NAV_CONFIG y funciones de navegación

- [ ] Crear `static/js/navigation.js` con:
  - `const NAV_CONFIG` — array de 3 secciones (TALLER, CONOCIMIENTO, ADMIN) con todos los items según el spec (RF1.2), incluyendo `placeholder: true` para Clientes, Presupuestos, Facturación, Inventario
  - `const VIEW_ALIASES` — mapeo de IDs viejos a nuevos:
    ```js
    { 'estadisticas': 'dashboard', 'referencia': 'referencias', 'mediciones-placa': 'puntos-placa' }
    ```
  - `renderSidebar()` — genera el HTML del `<nav id="sidebar">` a partir de NAV_CONFIG, incluyendo logo, secciones, items, footer con usuario y botón Salir
  - `cambiarVista(vistaId)` — nueva implementación:
    1. Oculta todos los `[id^="view"]` containers
    2. Muestra el container target (usando VIEW_ALIASES)
    3. Marca el item activo en la sidebar (`.sidebar-item[data-vista].active`)
    4. Ejecuta loader correspondiente desde mapa `loaders`
    5. Cierra sidebar en mobile (`closeSidebar()`)
  - `toggleSidebar()` — toggle clase `.open` en sidebar + overlay
  - `closeSidebar()` — remueve clase `.open` de sidebar y overlay
- [ ] Mapa `loaders` dentro de `cambiarVista()` con entrada para cada vista existente (dashboard, ordenes, placas, ics, mediciones, puntos-placa, soluciones, referencias, config, diagramas, reparaciones, reportes)
- [ ] Las vistas placeholder NO tienen entrada en `loaders`
- [ ] Exponer en `window`: `cambiarVista`, `toggleSidebar`, `closeSidebar`

**Dependencias**: T1.3 (usa `init()`), T1.4 (usa `renderCard`/`renderBadge` indirectamente).
**Archivos**: `static/js/navigation.js` (crear).
**Estimado**: ~180 líneas.
**Criterio**: `NAV_CONFIG` es la única fuente de verdad para la navegación.

---

### T2.2: Crear `sidebar.css` con estilos de sidebar + responsive

- [ ] Crear `static/css/sidebar.css`:
  - `:root` — nuevas variables: `--sidebar-width`, `--sidebar-bg`, `--sidebar-item-hover`, `--sidebar-item-active`, `--sidebar-border`, `--sidebar-icon-width`, `--sidebar-mobile-width`, `--overlay-bg`
  - `#sidebar` — `position: fixed; left: 0; top: 0; width: 240px; height: 100vh; z-index: 100; flex-direction: column; overflow-y: auto; transition: transform 0.2s ease;`
  - `.sidebar-header` — logo/título del sistema
  - `.sidebar-section-label` — texto de sección (TALLER, CONOCIMIENTO, ADMIN) en mayúsculas
  - `.sidebar-item` — display flex, hover iluminado, active con borde izquierdo `--accent`
  - `.sidebar-icon` — ancho fijo 36px, centrado
  - `.sidebar-label` — texto truncado con ellipsis
  - `.sidebar-footer` — usuario + botón Salir, al fondo (margin-top: auto)
  - `#sidebarOverlay` — `position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 99; display: none;`
  - `#hamburgerBtn` — `display: none` por defecto (solo mobile)
  - `@media (max-width: 768px)`:
    - Container: `margin-left: 0`
    - Sidebar: `transform: translateX(-100%)` → `.open` → `transform: translateX(0); width: 280px`
    - Overlay: `.show` → `display: block`
    - Hamburger: `display: block`
- [ ] Agregar `<link rel="stylesheet" href="css/sidebar.css">` en index.html DESPUÉS de `style.css`

**Dependencias**: T1.2 (style.css existe).
**Archivos**: `static/css/sidebar.css` (crear), `static/index.html` (agregar `<link>`).
**Estimado**: ~120 líneas CSS.

---

### T2.3: Modificar `index.html` — reemplazar tabs por sidebar + header

- [ ] En `index.html`:
  - Agregar `<nav id="sidebar"></nav>` justo después del `<div class="container">` (o antes, según layout)
  - Agregar `<div id="sidebarOverlay" onclick="closeSidebar()"></div>`
  - Agregar botón hamburguesa en el header: `<button id="hamburgerBtn" onclick="toggleSidebar()">☰</button>` (visible solo mobile vía CSS)
  - **REEMPLAZAR** `<div class="tabs">...</div>` (líneas 417-431) por nada — la sidebar lo reemplaza
  - Modificar `.container` CSS: en lugar de `max-width: 1100px; margin: 0 auto;`, ahora `margin-left: 240px` (desktop) / `margin-left: 0` (mobile)
  - Asegurar que `body { padding: 0 }` para que la sidebar fija funcione
- [ ] Agregar `<script src="js/navigation.js"></script>` en el `<head>` o antes del script inline
- [ ] Modificar `init()` (o agregar inline) para llamar `renderSidebar()` después de login exitoso
- [ ] Ajustar el flujo post-login: después de `hideLogin()`, llamar `renderSidebar()` y luego `cambiarVista('dashboard')`

**Dependencias**: T2.1, T2.2.
**Archivos**: `static/index.html` (modificado — reemplazar tabs, ajustar layout).
**Estimado**: ~30 líneas modificadas en HTML + ~10 líneas en CSS inline.
**Verificación**: La sidebar se renderiza con todos los items. Click en cada item cambia la vista. Active state funciona. Mobile toggle funciona.

---

## Fase 3: Vistas individuales

> Extracción de cada vista a su archivo individual. Commit principal + commit de limpieza.

### T3.1: Migrar órdenes a `views/orders.js`

- [ ] Crear `static/js/views/orders.js` con:
  - `_cargarMes()`, `_cargarTodas()`, `_cargarMeses()`, `_agregarOrden()`, `_eliminarOrden()`, `_renderOrdenes()`, `_toggleMostrarTotal()`
  - Exponer en window: `cargarMes`, `cargarTodas`, `cargarMeses`, `agregarOrden`, `eliminarOrden`, `toggleMostrarTotal`
- [ ] Preservar EXACTAMENTE la misma lógica de cada función (solo reubicar, no modificar)
- [ ] Agregar `<script src="js/views/orders.js"></script>` en index.html
- [ ] Verificar que `agregarOrden()`, `cargarMes()`, `cargarTodas()` funcionan desde el nuevo archivo

**Dependencias**: T1.3 (usa `apiFetch`, `mostrarMsg`).
**Archivos**: `static/js/views/orders.js` (crear), `static/index.html` (agregar script).
**Estimado**: ~120 líneas extraídas.

---

### T3.2: Migrar dashboard + reportes a `views/dashboard.js` y `views/reports.js`

- [ ] Crear `static/js/views/dashboard.js` con:
  - `cargarDashboard()`, `renderSummaryCards()`, `renderBarChart()`, `renderTablaMensual()`, `renderTopTipos()`, `renderTasaExitoMensual()`, `renderTopMarcas()`, `renderTopModelos()`, `renderTopPlacas()`
  - Botón "Generar informe" → `cambiarVista('reportes')` en vez de `abrirModalInforme()`
- [ ] Crear `static/js/views/reports.js` con:
  - `cargarReportes()` — renderiza el contenido inline en `viewReportes`
  - `generarInforme()`, `cargarPeriodosInforme()`, `cambiarTipoInforme()`, `renderPreview()`, `descargarPDF()`, `descargarTXT()`
  - La lógica es la misma de `abrirModalInforme()` pero renderizada en `viewReportes` en vez de modal
  - Exponer en window: `generarInforme`, `cargarPeriodosInforme`, `cambiarTipoInforme`, `descargarPDF`, `descargarTXT`
- [ ] Agregar scripts en index.html
- [ ] Agregar contenedor `viewReportes` en el HTML (div oculto con display:none)

**Dependencias**: T1.3 (usa `apiFetch`), T1.4 (usa `renderCard`, `renderTable`, `renderBadge`).
**Archivos**: `static/js/views/dashboard.js`, `static/js/views/reports.js` (crear), `static/index.html` (agregar scripts + contenedor).
**Estimado**: ~200 líneas total (dashboard ~120, reports ~80).

---

### T3.3: Migrar vistas existentes a archivos individuales

Crear cada archivo de vista con su lógica preservada exactamente igual:

- [ ] `static/js/views/repairs.js` — `cargarReparaciones()`, `cargarEmpresasSelect()`, `openAddReparacion()`
- [ ] `static/js/views/boards.js` — `renderPlacas()`, `openAddPlaca()`, `openAddCaja()`, `exportCSV()`, `backupDownload()`, `openBackups()`, `renderPlacaModal()`, toda la lógica Firebase + S
- [ ] `static/js/views/ics.js` — `fetchIcs()`, `openAddIc()`
- [ ] `static/js/views/measurements.js` — `cargarMediciones()`
- [ ] `static/js/views/board-points.js` — `cargarMedicionesPlaca()`, `abrirAddPuntoPlaca()`, `agregarMedicionPlaca()`, `eliminarMedicionPlaca()`, `editarMedicionPlaca()`, `guardarEdicionMedicionPlaca()`
- [ ] `static/js/views/solutions.js` — `cargarSoluciones()`, `openAddSolucion()`
- [ ] `static/js/views/references.js` — `cargarReferencias()`, `abrirAgregarReferencia()`, `cargarReferenciasConDelay()`
- [ ] `static/js/views/diagramas.js` — `buscarBoardDoctor()`, `debounceBd()`, `importarBoardDoctor()`, `buscarDatasheetDeModelo()`, funciones internas `_bdInput()`, `_bdResult()`, `_bdUrl()`, `_bdRender()`
- [ ] `static/js/views/config.js` — `cargarConfiguracion()`, `guardarValorPunto()`, `agregarPuntaje()`, `agregarTipoEquipo()`, `agregarEmpresa()`

**Por cada archivo**:
- Preservar la lógica interna idéntica
- Exponer en `window` solo las funciones llamadas desde `onclick`/`oninput`
- Agregar JSDoc en cada función pública
- Agregar `<script src="...">` en index.html

**Dependencias**: T1.3 (usa `apiFetch`), T3.1, T3.2 (mismo patrón).
**Archivos**: 9 archivos nuevos, `static/index.html` (9 scripts agregados).
**Estimado**: ~1200 líneas extraídas total (promedio ~130 por vista).
**Riesgo**: ALTO — cada extracción puede romper onclick si no se expone correctamente en window. Verificar cada vista manualmente.

---

### T3.4: Crear placeholders (clientes, presupuestos, facturación, inventario)

- [ ] Crear función compartida `renderPlaceholder(icon, title, description)` en `main.js` o en cada archivo (según prefiera el implementador)
- [ ] Crear `static/js/views/clients.js` con `renderPlaceholder('👤', 'Clientes', 'Gestión de clientes — próximamente disponible')`
- [ ] Crear `static/js/views/budgets.js` — `renderPlaceholder('💰', 'Presupuestos', 'Presupuestos — próximamente disponible')`
- [ ] Crear `static/js/views/invoices.js` — `renderPlaceholder('🧾', 'Facturación', 'Facturación — próximamente disponible')`
- [ ] Crear `static/js/views/inventory.js` — `renderPlaceholder('📦', 'Inventario', 'Inventario — próximamente disponible')`
- [ ] Agregar 4 contenedores en index.html: `viewClientes`, `viewPresupuestos`, `viewFacturacion`, `viewInventario` (divs ocultos)
- [ ] Los placeholders NO tienen entrada en el mapa `loaders` de `cambiarVista()`
- [ ] CSS: `.placeholder-card { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 40vh; }`
- [ ] Agregar scripts en index.html

**Dependencias**: T1.3, T2.1 (NAV_CONFIG ya tiene placeholder: true).
**Archivos**: 4 archivos JS, `static/index.html` (4 contenedores + 4 scripts), `static/css/style.css` (estilo placeholder).
**Estimado**: ~50 líneas total (4 archivos × ~8 líneas + ~20 líneas HTML + ~15 líneas CSS).

---

### T3.5: Consolidar vista Órdenes (unificar viewMes + viewGeneral)

- [ ] En `index.html`:
  - **ELIMINAR** `<div id="viewMes">...</div>` (líneas 447-474)
  - **ELIMINAR** `<div id="viewGeneral">...</div>` (líneas 477-483)
- [ ] Crear **nuevo** `<div id="viewOrdenes" style="display:none">` que combine:
  - Selector de mes + botón "Ver mes"
  - Formulario "Agregar orden" (mismo que estaba en viewMes)
  - Sección "Órdenes del mes" con tabla
  - Sección "Todas las órdenes" con buscador
- [ ] El layout puede ser dos secciones verticales o un toggle "Mes actual / Todas" (según prefiera el implementador)
- [ ] En `cambiarVista()`, cuando `vistaId === 'ordenes'`, ejecutar `cargarMes()` + `cargarTodas()`

**Dependencias**: T3.1 (órdenes ya extraídas a orders.js).
**Archivos**: `static/index.html` (eliminar 2 divs, crear 1 nuevo).
**Estimado**: ~40 líneas HTML nuevas, ~20 líneas eliminadas.
**Verificación**: La vista Órdenes muestra mes y todas las órdenes. Agregar orden funciona. CargarMes() y cargarTodas() funcionan.

---

### T3.6: Eliminar Clasificador

- [ ] En `index.html`:
  - **ELIMINAR** `<div id="viewClasificador">...</div>` (líneas 617-743)
  - **ELIMINAR** CSS del clasificador (líneas 255-334 en el `<style>`, pero ya extraído a style.css en T1.2)
  - **ELIMINAR** del `<style>` inline (o de `style.css`) TODO el bloque CSS del clasificador (`.clasif-grid`, `.clasif-toggles`, `.clasif-tog`, `.gama-badge`, `.clasif-rules`, etc.)
  - **ELIMINAR** del `<script>` inline todas las funciones del clasificador: `clasData`, `clasMarcaChange()`, `clasGenChange()`, `clasClasificar()`, `clasToggle()`, `clasOrigen()`, `clasToggleTabla()`, `clasResetear()`, variables relacionadas
  - **ELIMINAR** referencias a `viewClasificador` en el `cambiarVista()` original
- [ ] Verificar que no hay referencias a `clas*` en el resto del código

**Dependencias**: T2.3 (sidebar activa, cambiarVista reescrita).
**Archivos**: `static/index.html` (eliminar div + funciones + CSS), `static/css/style.css` (eliminar CSS clasificador).
**Estimado**: ~80 líneas eliminadas HTML + ~80 líneas CSS + ~200 líneas JS eliminadas.

---

### T3.7: Renombrar BoardDoctor a Diagramas

- [ ] En la sidebar (NAV_CONFIG, navigation.js): cambiar label de `'🔍 Diagramas / ICs'` a `'🔍 Diagramas'`
- [ ] En `viewDiagramas`: no hay cambios en el HTML (ya se llama `viewDiagramas` y muestra "Diagramas / Boardviews")
- [ ] En `diagramas.js`: los nombres de funciones internas (`buscarBoardDoctor`, `importarBoardDoctor`, etc.) se MANTIENEN para compatibilidad con API
- [ ] NO hay cambios en endpoints del backend
- [ ] Verificar que no aparece "BoardDoctor" como texto visible en la UI

**Dependencias**: T2.1 (NAV_CONFIG), T3.3 (diagramas.js).
**Archivos**: `static/js/navigation.js` (modificar label).
**Estimado**: 1 línea modificada.

---

### T3.8: Limpiar código inline duplicado en index.html

- [ ] En el `<script>` inline de `index.html`, **ELIMINAR** las funciones que ahora viven en sus archivos individuales:
  - Funciones de órdenes (agregarOrden, cargarMes, cargarTodas, eliminarOrden, cargarMeses, renderOrdenes, toggleMostrarTotal)
  - Funciones de dashboard (cargarDashboard, renderSummaryCards, renderBarChart, renderTablaMensual, renderTopTipos, renderTasaExitoMensual, renderTopMarcas, renderTopModelos, renderTopPlacas, abrirModalInforme, _dashboardData)
  - Funciones de reportes (generarInforme, descargarPDF, descargarTXT, renderPreview, cargarPeriodosInforme, cambiarTipoInforme, _informeData)
  - Funciones de reparaciones (cargarReparaciones, cargarEmpresasSelect, openAddReparacion)
  - Funciones de boards/placas (renderPlacas, openAddPlaca, openAddCaja, exportCSV, backupDownload, openBackups, renderPlacaModal)
  - Funciones de ICs (fetchIcs, openAddIc, _icsData, etc.)
  - Funciones de mediciones (cargarMediciones)
  - Funciones de board-points (cargarMedicionesPlaca, abrirAddPuntoPlaca, agregarMedicionPlaca, eliminarMedicionPlaca, editarMedicionPlaca, guardarEdicionMedicionPlaca)
  - Funciones de soluciones (cargarSoluciones, openAddSolucion)
  - Funciones de referencias (cargarReferencias, abrirAgregarReferencia, cargarReferenciasConDelay)
  - Funciones de diagramas (buscarBoardDoctor, debounceBd, importarBoardDoctor, buscarDatasheetDeModelo, _bdInput, _bdResult, _bdUrl, _bdRender)
  - Funciones de config (cargarConfiguracion, guardarValorPunto, agregarPuntaje, agregarTipoEquipo, agregarEmpresa)
  - Funciones del timer (ya en main.js)
  - Buscador general (ya en main.js)
  - Helpers (ya en main.js)
  - **MANTENER** solo: event listeners con addEventListener (Firebase onSnapshot, inputs)
- [ ] Verificar que ningún evento `onclick`/`oninput` en el HTML quede huérfano
- [ ] Verificar que `window.funcionX` existe para cada onclick del HTML
- [ ] Verificar que la app carga sin errores en consola

**Dependencias**: TODAS las T3.x anteriores deben estar completas.
**Archivos**: `static/index.html` (eliminar ~2000 líneas de JS inline).
**Estimado**: ~2000 líneas eliminadas del script inline.
**Riesgo**: MUY ALTO — si una función se elimina pero su onclick en HTML no se migró correctamente, la app se rompe. Verificación exhaustiva requerida.

---

## Fase 4: Documentación + limpieza final

> Sin cambios en el comportamiento. Solo documentación y pulido.

### T4.1: Crear documentación externa en `docs/`

- [ ] `docs/README.md` (~40 líneas): Visión general, stack vanilla, estructura de carpetas, dev setup, convenciones
- [ ] `docs/ARCHITECTURE.md` (~100 líneas): SPA con funciones-componente, flujo de datos (API → función → innerHTML), estado global mínimo, JWT auth, diagrama ASCII de flujo
- [ ] `docs/COMPONENTS.md` (~150 líneas): Catálogo de 5 componentes con firma, @param, @returns, ejemplo, problema que resuelve
- [ ] `docs/NAVIGATION.md` (~80 líneas): NAV_CONFIG, renderSidebar(), cambiarVista(), guía 3 pasos para agregar vistas, mobile behavior
- [ ] `docs/STYLE.md` (~80 líneas): Variables CSS explicadas, convenciones de nombres, breakpoints responsive
- [ ] `docs/EXAMPLES.md` (~150 líneas): 3 ejemplos completos (módulo Proveedores, columna en órdenes, nuevo componente renderList)

**Dependencias**: Ninguna técnica. Puede hacerse en paralelo con Fase 3.
**Archivos**: 6 archivos nuevos en `docs/`.
**Estimado**: ~600 líneas total de documentación.

---

### T4.2: Agregar JSDoc completo en funciones públicas

- [ ] Revisar cada archivo JS en `static/js/` y asegurar que toda función pública tenga JSDoc completo con `@param`, `@returns`
- [ ] Las funciones-componente (table, card, modal, form, badge) deben tener `@example`
- [ ] Las funciones privadas (prefijo `_`) pueden tener JSDoc simplificado de 1 línea
- [ ] Archivos a revisar: `main.js`, `navigation.js`, todos en `components/`, todos en `views/`

**Dependencias**: T3.8 (código final estable).
**Archivos**: ~20 archivos JS.
**Estimado**: ~100 líneas agregadas en JSDoc.

---

### T4.3: Limpieza final de CSS no usado

- [ ] Eliminar del `<style>` inline en `index.html` TODO el contenido (ya extraído a `style.css` y `sidebar.css`) — el `<style>` tag ya no es necesario si todo está en CSS externos
- [ ] Opcional: eliminar del `style.css` los selectores del clasificador si no se eliminaron en T3.6
- [ ] Verificar que no haya selectores CSS huerfanos (tabs viejos, clasificador)
- [ ] Verificar que la app carga visualmente igual SIN el `<style>` inline

**Dependencias**: T2.2, T3.6.
**Archivos**: `static/index.html` (eliminar `<style>`), `static/css/style.css` (eliminar CSS no usado).
**Estimado**: ~10 líneas eliminadas de index.html, ~100 líneas eliminadas de style.css.

---

### T4.4: Verificación final cross-cutting

- [ ] Verificar CA1 a CA39 de la especificación (sección 8)
- [ ] Probar cada vista existente: dashboard, órdenes, reparaciones, placas, ICs, mediciones, puntos-placa, soluciones, referencias, diagramas, config
- [ ] Probar cada placeholder: clientes, presupuestos, facturación, inventario
- [ ] Probar reportes como vista standalone
- [ ] Probar login/logout
- [ ] Probar mobile: sidebar toggle, overlay, cierre
- [ ] Probar que no hay errores en consola (Chrome DevTools)
- [ ] Probar que el timer flotante funciona
- [ ] Probar que el buscador general funciona
- [ ] Probar que Firebase (placas) sigue funcionando
- [ ] Confirmar que no hay referencias a "BoardDoctor" en la UI
- [ ] Confirmar que no existe `viewMes`, `viewGeneral`, `viewClasificador`
- [ ] Confirmar que los tabs horizontales no existen en el HTML

**Dependencias**: TODAS las anteriores.
**Archivos**: Ninguno.
**Estimado**: ~30 min de prueba manual.

---

## Review Workload Forecast

### Líneas estimadas (cambios netos)

| Fase | Nuevas | Modificadas | Eliminadas | Neto |
|------|--------|-------------|------------|------|
| **Fase 1** | ~730 (375 CSS + 150 main.js + 200 componentes) | ~5 (index.html scripts/links) | 0 | +735 |
| **Fase 2** | ~300 (180 navigation.js + 120 sidebar.css) | ~40 (index.html layout) | ~20 (tabs HTML) | +320 |
| **Fase 3** | ~1570 (14 vistas × ~100-150 c/u + placeholders) | ~100 (index.html contenedores) | ~2300 (clasificador + funciones inline) | -630 |
| **Fase 4** | ~600 (docs) | ~100 (JSDoc) | ~110 (CSS no usado + style inline) | +590 |
| **Total** | ~3200 | ~245 | ~2430 | **+1015 neto** |

### Archivos modificados

- **Modificados**: 1 (`static/index.html`)
- **Creados**: ~28 (2 CSS + 20 JS + 6 docs)
- **Eliminados**: 0 (todo está en index.html, no hay archivos separados que eliminar)
- **Total archivos tocados**: ~29

### Riesgo de chained PRs

| Factor | Valor |
|--------|-------|
| Líneas totales estimadas | ~3200 agregadas + ~2430 eliminadas ≈ **5600 líneas tocadas** |
| Líneas modificadas en el archivo crítico (index.html) | ~200 (HTML estructural) + ~2000 eliminadas del script = ~2200 tocadas |
| Archivos JS nuevos | 20 |
| Review effort por vista | Media (cada vista es extracción directa, no lógica nueva) |
| Review effort por sidebar | Alta (cambiarVista() y navigation.js tienen lógica nueva) |
| Review effort por docs | Baja (solo documentación) |

### Decisión

**Chained PRs recomendados: SÍ**, dividido en **3 PRs**:

| PR | Fases | Líneas aprox. | Descripción |
|----|-------|---------------|-------------|
| **PR #1** | Fase 1 + Fase 2 | ~1030 agregadas, ~20 eliminadas | Preparación + Sidebar. El cambio más riesgoso (navegación nueva). Independiente y verificable. |
| **PR #2** | Fase 3 | ~1570 agregadas, ~2300 eliminadas | Vistas individuales. Muchas líneas pero son extracciones directas. Riesgo de onclicks huérfanos. |
| **PR #3** | Fase 4 | ~700 agregadas, ~110 eliminadas | Documentación + JSDoc + limpieza. Bajo riesgo, fácil de revisar. |

Si se prefiere un solo PR, requiere revisión adversarial con atención especial a:
- `cambiarVista()` nuevo (Fase 2)
- Funciones expuestas en `window` que quedan huérfanas (Fase 3)
- Eliminación del clasificador sin romper otras vistas (T3.6)

**400-line budget risk**: ALTO. Este cambio supera ampliamente las 400 líneas. Justificado porque ~70% del código es extracción directa (no lógica nueva) y ~20% es documentación. El único código nuevo significativo es `navigation.js` (~180 líneas) y `sidebar.css` (~120 líneas).

### Dependencia entre PRs

```
PR #1 (Fase 1+2) → PR #2 (Fase 3) → PR #3 (Fase 4)
```

Estrictamente secuencial: no se puede hacer Fase 3 sin la sidebar funcionando, y no se puede hacer Fase 4 sin el código estable.
