# JC-Sistema — Especificación

> **Cambio**: Reestructuración completa del frontend: sidebar lateral, reorganización de vistas,
> placeholders para nuevos módulos, documentación exhaustiva.
> **Backend**: Sin cambios. Todo es frontend (HTML/CSS/JS vanilla).
> **Archivos afectados**: `static/index.html` (modificado), nuevos archivos en `static/css/`, `static/js/`, `docs/`.

---

## Tabla de contenidos

1. [Descripción general](#1-descripción-general)
2. [Requerimientos funcionales](#2-requerimientos-funcionales)
   - [RF1: Sidebar de navegación](#rf1-sidebar-de-navegación)
   - [RF2: Vistas y routing](#rf2-vistas-y-routing)
   - [RF3: Componentes reutilizables](#rf3-componentes-reutilizables)
   - [RF4: Placeholders](#rf4-placeholders)
   - [RF5: Lógica de órdenes — migración](#rf5-lógica-de-órdenes--migración)
   - [RF6: Documentación del código](#rf6-documentación-del-código)
3. [Requerimientos no funcionales](#3-requerimientos-no-funcionales)
   - [RNF1: Performance](#rnf1-performance)
   - [RNF2: Mantenibilidad](#rnf2-mantenibilidad)
   - [RNF3: Responsive / Mobile](#rnf3-responsive--mobile)
   - [RNF4: Compatibilidad](#rnf4-compatibilidad)
4. [Estructura de archivos](#4-estructura-de-archivos)
5. [Sidebar — estructura y secciones](#5-sidebar--estructura-y-secciones)
6. [Documentación externa](#6-documentación-externa)
7. [Reglas de negocio](#7-reglas-de-negocio)
8. [Criterios de aceptación](#8-criterios-de-aceptación)
9. [Glosario](#9-glosario)
10. [Preguntas abiertas](#10-preguntas-abiertas)

---

## 1. Descripción general

El sistema actual tiene un solo archivo `static/index.html` de **5046 líneas** con navegación horizontal
(tabs) que contiene 13 vistas. Este cambio reemplaza esa navegación por una **sidebar lateral** con
secciones agrupadas, elimina vistas obsoletas, renombra otras, agrega placeholders para módulos futuros
y reubica la lógica de órdenes en una sola vista consolidada.

Además, se **separa el monolito HTML** en archivos JS individuales organizados por responsabilidad
(componentes, vistas, utilidades), se crean archivos CSS específicos y se genera documentación
exhaustiva tanto en el código (JSDoc) como en la carpeta `docs/`.

El objetivo es preparar el frontend para la expansión del sistema JC sin tocar el backend.

### Principios de diseño

- **Zero nuevas dependencias**: sin frameworks, sin librerías externas. Todo vanilla JS + CSS puro.
- **Arquitectura de funciones-componente**: cada función de vista devuelve un string HTML y se inserta con `innerHTML`.
  No hay virtual DOM, no hay estado reactivo complejo. Se mantiene el patrón existente del sistema.
- **Separación por responsabilidad**: cada archivo JS tiene un propósito único. Las vistas no comparten estado global
  más allá de lo necesario.
- **Documentación first-class**: toda función pública tiene JSDoc con firma, parámetros, retorno y ejemplo.
  La carpeta `docs/` explica la arquitectura completa.
- **Preservación de funcionalidad existente**: ninguna vista actual pierde funcionalidad. Solo se reubica o renombra.
- **Mobile-first**: la sidebar debe ser usable en dispositivos móviles con colapso a íconos o menú hamburguesa.

---

## 2. Requerimientos funcionales

### RF1: Sidebar de navegación

#### RF1.1 — Estructura visual

La sidebar debe ser un panel lateral fijo a la izquierda con las siguientes características:

| Característica | Especificación |
|----------------|----------------|
| Posición | `position: fixed; left: 0; top: 0; height: 100vh` |
| Ancho default | `240px` (incluye padding) |
| Ancho colapsado (mobile) | `60px` (solo íconos) o `0` (oculto con hamburguesa) |
| Fondo | Mismo `--card` o ligeramente más oscuro que `--bg` |
| Z-index | Superior al contenido (`z-index: 100`) |
| Transición | Animación suave al colapsar/expandir (`transition: width 0.2s ease`) |
| Scroll interno | Si los items exceden el alto, scroll vertical dentro de la sidebar |
| Separación visual | Línea divisoria (`1px solid var(--border)`) entre secciones |
| Active item | Color de fondo o borde izquierdo (`--accent`) en el item activo |

#### RF1.2 — Secciones y agrupación

La sidebar se divide en 3 secciones con títulos en mayúsculas + espaciado:

```
┌──────────────────────┐
│  📊 Rendimiento      │  ← Logo/título, click → Dashboard
│  Juan                │
├──────────────────────┤
│  TALLER              │  ← Título de sección
│  🏠 Dashboard        │
│  📋 Órdenes          │
│  🔧 Reparaciones     │
│  👤 Clientes         │  ← Placeholder
│  💰 Presupuestos     │  ← Placeholder
│  🧾 Facturación      │  ← Placeholder
│  📦 Inventario       │  ← Placeholder
├──────────────────────┤
│  CONOCIMIENTO         │
│  🔩 Placas           │
│  🔌 ICs              │
│  📏 Mediciones       │
│  📐 Puntos placa     │
│  💡 Soluciones       │
│  📖 Referencias      │
│  🔍 Diagramas        │  ← Ex BoardDoctor
├──────────────────────┤
│  ADMIN               │
│  ⚙️ Config           │
│  📊 Reportes         │
├──────────────────────┤
│  👤 Admin            │  ← Nombre de usuario + Salir
│  [Salir]             │
└──────────────────────┘
```

#### RF1.3 — Comportamiento mobile (< 768px)

- La sidebar se oculta completamente por defecto.
- Un botón hamburguesa (☰) en la esquina superior izquierda la togglea.
- Al abrirse, aparece un overlay semitransparente (`rgba(0,0,0,0.5)`) detrás.
- El overlay es clickeable para cerrar la sidebar.
- El ancho de la sidebar en mobile es `280px` (suficiente para mostrar texto).
- Alternativa: colapsar a solo íconos (sin texto). En ese caso, al hacer hover sobre un ícono
  aparece un tooltip con el nombre.

#### RF1.4 — Ítems de navegación

Cada ítem de la sidebar debe tener:
- Un **ícono** (emoji, consistente con los usados actualmente en los tabs)
- Un **nombre** visible
- Al hacer **hover**: color de fondo suave (`--accent-soft` o similar) + cursor pointer
- Al estar **activo**: borde izquierdo de color `--accent` + color de fondo ligeramente distinto
- Al hacer **click**: ejecuta `cambiarVista(idVista)` y marca ese ítem como activo

#### RF1.5 — Header superior

El header original se simplifica y adapta a la sidebar:
- Título "📊 Rendimiento Juan" + subtítulo "NSP Notebooks"
- Nombre de usuario + botón "Salir"
- Indicador de estado del servidor (⏳ Conectando... / ✅ Conectado / ❌ Error)
- Botón hamburguesa (☰) visible solo en mobile (< 768px)
- El header se mantiene como barra superior, no dentro de la sidebar.

---

### RF2: Vistas y routing

#### RF2.1 — Mecanismo `cambiarVista()`

La función `cambiarVista(vistaId)` debe:
1. Ocultar todos los contenedores de vista (`display: none`)
2. Mostrar el contenedor correspondiente (`display: block`)
3. Marcar el ítem de sidebar correspondiente como activo
4. Ejecutar la carga de datos si corresponde (ej: si es "placas", cargar datos de Firebase)
5. Soporte para lazy loading: las vistas placeholder no cargan datos

El mecanismo actual usa `document.querySelectorAll(".tabs button")` para marcar activo — esto se reemplaza
por la sidebar.

#### RF2.2 — Mapeo de vistas

| ID vista | Nombre | Tipo | Origen | Notas |
|----------|--------|------|--------|-------|
| `dashboard` | Dashboard | Nueva | — | Primera vista al cargar. Asumimos que reemplaza/conserva `estadisticas`. |
| `ordenes` | Órdenes | Migrada | `viewMes` + `viewGeneral` | Consolidada. Unifica mes + general. |
| `reparaciones` | Reparaciones | Existente | `viewReparaciones` | Sin cambios en lógica. |
| `placas` | Placas | Existente | `viewPlacas` | Sin cambios (Firebase). |
| `ics` | ICs | Existente | `viewIcs` | Sin cambios. |
| `mediciones` | Mediciones | Existente | `viewMediciones` | Sin cambios. |
| `puntos-placa` | Puntos placa | Existente | `viewMedicionesPlaca` | Sin cambios. |
| `soluciones` | Soluciones | Existente | `viewSoluciones` | Sin cambios. |
| `referencias` | Referencias | Existente | `viewReferencia` | Sin cambios. |
| `diagramas` | Diagramas | Renombrada | `viewDiagramas` (ex BoardDoctor) | Misma funcionalidad, nuevo nombre. |
| `config` | Config | Existente | `viewConfig` | Sin cambios. |
| `reportes` | Reportes | Nueva | Modal de informe actual | Extraído del dashboard como vista standalone. |
| `clientes` | Clientes | Placeholder | — | Solo HTML, sin lógica. |
| `presupuestos` | Presupuestos | Placeholder | — | Solo HTML, sin lógica. |
| `facturacion` | Facturación | Placeholder | — | Solo HTML, sin lógica. |
| `inventario` | Inventario | Placeholder | — | Solo HTML, sin lógica. |

#### RF2.3 — Vistas eliminadas del sistema

| ID original | Contenido | Destino |
|-------------|-----------|---------|
| `viewMes` | Órdenes del mes + formulario agregar orden + selector de mes | Migrar a `ordenes` |
| `viewGeneral` | Todas las órdenes con buscador | Migrar a `ordenes` |
| `viewClasificador` | Clasificador de equipos por marca/generación | Eliminar completamente |

#### RF2.4 — Dashboard (vista principal)

El Dashboard actual (`viewEstadisticas`) usa el endpoint `GET /api/dashboard/` y muestra:
- Summary cards (órdenes del mes, resumen anual, tasa de éxito)
- Tendencia mensual (bar chart hecho con divs CSS)
- Tabla de rendimiento mensual
- Top 5 tipos
- Tasa de éxito mensual
- Top marcas, modelos, placas
- Botón "Generar informe" → ahora lleva a la vista Reportes

Este dashboard se mantiene funcionalmente igual, pero:
- Se mueve al ID `viewDashboard`
- Se convierte en la **primera vista** al cargar la app (después del login)
- La función `cambiarVista('dashboard')` llama a `cargarDashboard()`

#### RF2.5 — Vista Órdenes (consolidada)

Se crea una nueva vista `viewOrdenes` que consolida:
- **Formulario "Agregar orden"** (actualmente en `viewMes`): fecha, número de orden, tipo, botón agregar
- **Órdenes del mes** (actualmente en `viewMes`): tabla filtrada por mes, con selector de mes
- **Todas las órdenes** (actualmente en `viewGeneral`): tabla completa con buscador
- Se puede mostrar como dos secciones (una debajo de la otra) con subtítulos, o con un toggle "Mes actual / Todas"

Funciones preservadas sin cambios en su lógica interna:
- `agregarOrden()` — se mantiene idéntica
- `cargarMes()` — se mantiene, asociada al selector de mes
- `cargarTodas()` — se mantiene, asociada al buscador general
- Consultar puntaje de orden — se mantiene (inline en tabla)

#### RF2.6 — Vista Reportes (extraída del dashboard)

El modal de informe de puntos (función `abrirModalInforme()` dentro del dashboard)
se convierte en una vista standalone `viewReportes`.

Debe mantener exactamente la misma funcionalidad:
- Selector de tipo (Mensual / Anual)
- Selector de período (carga meses desde `GET /api/meses`)
- Vista previa del informe
- Botones de descarga (PDF, TXT fallback)
- Toda la lógica de `_informeData`, `generarInforme()`, `descargarPDF()`, `descargarTXT()`

El modal overlay existente (`#placaModal`, `#placaModalInner`) se reutiliza tal cual está.

#### RF2.7 — Vista Diagramas (renombrada)

La actual `viewDiagramas` (ex BoardDoctor) mantiene exactamente el mismo contenido y funcionalidad:
- Card 1: Buscador de diagramas/boardviews por modelo de placa
- Card 2: Buscador de ICs por código de marca (marking)
- Card 3: Buscador de reemplazos compatibles de IC
- Card 4: Buscador de datasheets externos
- Admin: Botón para re-importar datos desde CSVs

Solo cambia:
- El ID del contenedor sigue siendo `viewDiagramas` (ya estaba así)
- El nombre en la sidebar cambia de "🔍 Diagramas / ICs" a "🔍 Diagramas"
- Las referencias a "BoardDoctor" en el código se mantienen internamente (nombres de funciones, endpoints)
  pero la UI ya no muestra ese nombre.

---

### RF3: Componentes reutilizables

Se crean funciones-componente en `static/js/components/` que devuelven HTML. Son funciones puras:
reciben datos, devuelven un string HTML. No manejan estado, no tienen side effects.

#### RF3.1 — `table.js`

```js
/**
 * Renderiza una tabla HTML a partir de datos.
 *
 * @param {string[]} headers - Nombres de las columnas
 * @param {Array<Array<string>>} rows - Datos: cada row es un array de celdas
 * @param {object} [opts] - Opciones adicionales
 * @param {string} [opts.className] - Clase CSS extra para la tabla
 * @param {boolean} [opts.responsive] - Si debe envolverse en contenedor scrollable
 * @param {string} [opts.emptyMessage] - Mensaje cuando no hay filas
 * @returns {string} HTML de la tabla
 *
 * @example
 * renderTable(['Nombre', 'Edad'], [['Juan', '30'], ['María', '25']])
 * // → '<table class="table"><thead><tr><th>Nombre</th><th>Edad</th></tr></thead>...'
 */
function renderTable(headers, rows, opts = {}) {}
```

#### RF3.2 — `card.js`

```js
/**
 * Renderiza una card genérica.
 *
 * @param {object} config - Configuración de la card
 * @param {string} config.title - Título de la card
 * @param {string} config.content - HTML del contenido
 * @param {string} [config.className] - Clase CSS extra
 * @param {string} [config.icon] - Emoji para el título (opcional)
 * @returns {string} HTML de la card
 *
 * @example
 * renderCard({ title: 'Resumen', content: '<p>10 órdenes activas</p>', icon: '📊' })
 * // → '<div class="card"><div class="card-title">📊 Resumen</div><div class="card-body">...'
 */
function renderCard(config) {}
```

#### RF3.3 — `modal.js`

```js
/**
 * Abre un modal con overlay usando el contenedor existente #placaModal.
 *
 * @param {object} config - Configuración del modal
 * @param {string} config.title - Título del modal
 * @param {string} config.content - HTML del cuerpo
 * @param {Array<{label:string, onClick:Function, variant?:string}>} [config.buttons] - Botones del footer
 * @param {Function} [config.onClose] - Callback al cerrar el modal
 * @returns {void}
 *
 * @example
 * openModal({ title: 'Confirmar', content: '<p>¿Eliminar orden?</p>',
 *   buttons: [{ label: 'Cancelar', variant: 'cancel' }, { label: 'Eliminar', onClick: eliminar }] })
 */
function openModal(config) {}
```

#### RF3.4 — `form.js`

```js
/**
 * Crea el HTML de un field de formulario (label + input/select).
 *
 * @param {object} config - Configuración del field
 * @param {string} config.label - Texto del label
 * @param {string} config.id - ID del input
 * @param {'text'|'date'|'number'|'select'|'checkbox'|'textarea'} config.type - Tipo de input
 * @param {string} [config.value] - Valor por defecto
 * @param {Array<{value:string, label:string}>} [config.options] - Opciones para type='select'
 * @param {string} [config.placeholder] - Placeholder del input
 * @param {boolean} [config.required] - Si el campo es requerido
 * @returns {string} HTML del field
 *
 * @example
 * renderField({ label: 'Fecha', id: 'fechaInput', type: 'date', required: true })
 * // → '<div class="field"><label for="fechaInput">Fecha</label><input type="date" id="fechaInput" required></div>'
 */
function renderField(config) {}
```

#### RF3.5 — `badge.js`

```js
/**
 * Renderiza un badge de estado con color semántico.
 *
 * @param {string} text - Texto del badge
 * @param {'success'|'warning'|'danger'|'info'|'default'} variant - Variante de color
 * @returns {string} HTML del badge
 *
 * @example
 * renderBadge('Reparado', 'success')
 * // → '<span class="badge badge--success">Reparado</span>'
 */
function renderBadge(text, variant = 'default') {}
```

---

### RF4: Placeholders

Cuatro vistas placeholder que muestran un mensaje unificado:

| Vista | Ícono | Título | Descripción |
|-------|-------|--------|-------------|
| Clientes | 👤 | Próximamente | Gestión de clientes — próximamente disponible |
| Presupuestos | 💰 | Próximamente | Presupuestos — próximamente disponible |
| Facturación | 🧾 | Próximamente | Facturación — próximamente disponible |
| Inventario | 📦 | Próximamente | Inventario — próximamente disponible |

Todas usan el mismo patrón visual con una función compartida (puede vivir en `main.js` o en cada archivo):

```js
/**
 * Renderiza una vista placeholder de "Próximamente".
 *
 * @param {string} icon - Emoji del módulo
 * @param {string} title - Título del módulo
 * @param {string} description - Descripción breve
 * @returns {string} HTML del placeholder
 */
function renderPlaceholder(icon, title, description) {
  return `
    <div class="placeholder-card">
      <div class="placeholder-icon">${icon}</div>
      <h2>${title}</h2>
      <p>${description}</p>
    </div>
  `;
}
```

Requerimientos de placeholders:
- Sin llamadas fetch a ningún endpoint
- Sin lógica de negocio
- Sin eventos o listeners
- CSS: card centrada vertical y horizontalmente, ícono grande (3rem+), texto suave
- Todos idénticos en estructura, solo cambia el contenido

---

### RF5: Lógica de órdenes — migración

#### RF5.1 — Funciones a preservar

Todas estas funciones existen actualmente en `index.html` a nivel global. Se extraen a `views/orders.js`
y se exponen en `window` si son llamadas desde atributos HTML `onclick`:

| Función | Origen (línea aprox.) | Se expone en window |
|---------|----------------------|---------------------|
| `agregarOrden()` | ~468 | Sí |
| `cargarMes()` | ~450 | Sí |
| `cargarTodas()` | ~1481 | Sí |
| `renderOrdenes(data, containerId, filterFn)` | — | Sí |
| `eliminarOrden(id)` | ~1436 | Sí |
| Consultar puntaje de orden | inline en renderOrdenes | No (se mantiene interna) |

#### RF5.2 — Vista órdenes unificada

La vista `viewOrdenes` combina la funcionalidad de `viewMes` y `viewGeneral`:

```
┌─────────────────────────────────────────────┐
│  📋 Órdenes                                 │
├─────────────────────────────────────────────┤
│  [Selector Mes: ▼ Julio 2026] [Ver mes]     │
│  ─────────────────────────────────────────── │
│  ➕ Agregar orden                           │
│  [Fecha] [N°] [Tipo ▼] [Agregar]            │
│  ─────────────────────────────────────────── │
│  Órdenes del mes                             │
│  ┌─────┬──────┬──────┬─────┬────┐          │
│  │ N°  │Fecha │Tipo  │Pts  │Acc │          │
│  ├─────┼──────┼──────┼─────┼────┤          │
│  │     │      │      │     │    │          │
│  └─────┴──────┴──────┴─────┴────┘          │
│  ─────────────────────────────────────────── │
│  Todas las órdenes                           │
│  [🔍 Buscar orden, tipo o fecha...]         │
│  ┌─────┬──────┬──────┬─────┬────┐          │
│  │ N°  │Fecha │Tipo  │Pts  │Acc │          │
│  └─────┴──────┴──────┴─────┴────┘          │
└─────────────────────────────────────────────┘
```

---

### RF6: Documentación del código

#### RF6.1 — JSDoc obligatorio

TODA función pública o exportada debe tener JSDoc completo con:

```js
/**
 * [Verbo en 3ra persona] [qué hace en UNA línea].
 *
 * @param {tipo} nombreParam - Descripción del parámetro
 * @param {tipo} [nombreOpcional] - Descripción (corchetes = opcional)
 * @returns {tipo} Descripción del valor de retorno
 *
 * @example
 * miFuncion('ejemplo');
 * // → 'resultado esperado'
 */
```

Excepciones:
- Callbacks cortos de eventos (`onclick`, `addEventListener`) no requieren JSDoc
- Funciones privadas (con prefijo `_`) pueden tener JSDoc simplificado de una línea
- Getters/setters triviales no requieren JSDoc

#### RF6.2 — Comentarios de sección

Cada archivo JS debe tener comentarios de sección para agrupar funciones relacionadas,
usando el mismo formato que el código existente:

```js
// ── Auth ──────────────────────────────────────────────────────
// ── Órdenes ────────────────────────────────────────────────────
// ── Helpers ────────────────────────────────────────────────────
```

#### RF6.3 — Archivos de documentación externa

Ver [Sección 6 — Documentación externa](#6-documentación-externa).

---

## 3. Requerimientos no funcionales

### RNF1: Performance

| ID | Requerimiento |
|----|---------------|
| RNF1.1 | El sidebar no debe afectar el tiempo de carga inicial perceptiblemente. |
| RNF1.2 | Las transiciones de colapso/expansión de la sidebar deben ser < 300ms. |
| RNF1.3 | Las vistas existentes deben cargar con la misma velocidad que antes. No se agregan llamadas HTTP nuevas. |
| RNF1.4 | Los placeholders no hacen ninguna llamada a la API. Son HTML estático inline. |
| RNF1.5 | Las funciones existentes no se modifican en su lógica interna, solo se reubican. Esto garantiza que no se introducen regresiones de performance. |

### RNF2: Mantenibilidad

| ID | Requerimiento |
|----|---------------|
| RNF2.1 | Cada archivo JS tiene una única responsabilidad claramente definida. |
| RNF2.2 | Ningún archivo JS debe superar las 500 líneas (a excepción de vistas complejas como `dashboard.js` o `boards.js` que pueden llegar a 600-700). |
| RNF2.3 | Las funciones-componente (`renderTable`, `renderCard`, etc.) son puras: reciben datos, devuelven HTML. No modifican el DOM directamente. |
| RNF2.4 | La configuración de navegación debe estar en un solo lugar: `NAV_CONFIG` en `navigation.js`. |
| RNF2.5 | Para agregar una nueva vista se requieren solo 3 pasos: (1) crear archivo en `views/`, (2) agregar entrada en `NAV_CONFIG`, (3) agregar `<script src="...">` en `index.html`. |
| RNF2.6 | Las variables globales se minimizan. Solo se exponen en `window` aquellas funciones llamadas desde HTML inline (`onclick`). |

### RNF3: Responsive / Mobile

| ID | Requerimiento |
|----|---------------|
| RNF3.1 | Breakpoint: `max-width: 768px`. Por debajo, sidebar oculta con toggle. |
| RNF3.2 | En mobile, el contenido principal ocupa `width: 100%` sin margen izquierdo. |
| RNF3.3 | En desktop, el contenido principal tiene `margin-left: 240px` (ancho de la sidebar). |
| RNF3.4 | El botón hamburguesa (☰) es visible solo en mobile. |
| RNF3.5 | El overlay al abrir sidebar en mobile es clickeable para cerrar. |
| RNF3.6 | Las tablas existentes deben mantener su comportamiento responsive actual (wrap/scroll horizontal). |

### RNF4: Compatibilidad

| ID | Requerimiento |
|----|---------------|
| RNF4.1 | La app debe funcionar en Chrome 90+, Firefox 90+, Edge 90+, Safari 15+. |
| RNF4.2 | No se requiere polyfill de ninguna característica moderna. |
| RNF4.3 | Firebase (placas) debe seguir funcionando exactamente igual, sin cambios en la integración. |
| RNF4.4 | El modal overlay existente (`#placaModal`) se mantiene y se reusa. |
| RNF4.5 | No se requiere build step, bundler, preprocessor ni tooling adicional. |

---

## 4. Estructura de archivos

### Estado actual

```
static/
  index.html          ← 5046 líneas, TODO el frontend en un solo archivo
  placas-data.js      ← Datos de Firebase para placas
docs/
  ARQUITECTURA.md     ← Documentación existente del backend
```

### Estado deseado

```
static/
  index.html                  ← HTML base: header, sidebar, view containers, scripts
  css/
    style.css                 ← Variables CSS, reset, tipografía, cards, tablas, forms
    sidebar.css               ← Estilos específicos de la sidebar
  js/
    main.js                   ← Entry point: init(), API_BASE, apiFetch(), helpers globales
    auth.js                   ← Login, refresh token, user state, logout
    navigation.js             ← NAV_CONFIG, renderSidebar(), cambiarVista(), toggleSidebar()
    components/
      table.js                ← renderTable()
      card.js                 ← renderCard()
      modal.js                ← openModal()
      form.js                 ← renderField() + helpers de formularios
      badge.js                ← renderBadge()
    views/
      dashboard.js            ← Dashboard: cargarDashboard(), renderSummaryCards(), chart, etc.
      orders.js               ← Órdenes: cargarMes(), cargarTodas(), agregarOrden(), renderOrdenes()
      repairs.js              ← Reparaciones (window.cargarReparaciones(), etc.)
      boards.js               ← Placas (Firebase) — lógica de Firebase + renderizado
      ics.js                  ← ICs: fetchIcs(), openAddIc()
      measurements.js         ← Mediciones: cargarMediciones()
      board-points.js         ← Puntos placa: cargarMedicionesPlaca()
      solutions.js            ← Soluciones: cargarSoluciones(), openAddSolucion()
      references.js           ← Referencias: cargarReferencias(), abrirAgregarReferencia()
      diagramas.js            ← Diagramas: buscarBoardDoctor(), importarBoardDoctor()
      config.js               ← Config: cargarConfiguracion(), guardarValorPunto(), etc.
      reports.js              ← Reportes: generarInforme(), descargarPDF()
      clients.js              ← Placeholder
      budgets.js              ← Placeholder
      invoices.js             ← Placeholder
      inventory.js            ← Placeholder
docs/
  README.md                   ← Visión general de la arquitectura frontend
  ARCHITECTURE.md             ← Organización del frontend, flujo de datos
  COMPONENTS.md               ← Cada función-componente con firma, ejemplo y justificación
  NAVIGATION.md               ← Cómo funciona la sidebar, cómo agregar nuevas vistas
  STYLE.md                    ← Variables CSS, cómo mantener consistencia visual
  EXAMPLES.md                 ← Ejemplos de cómo agregar un módulo completo
```

### Orden de carga en `index.html`

```html
<!-- CSS -->
<link rel="stylesheet" href="css/style.css">
<link rel="stylesheet" href="css/sidebar.css">

<!-- JS: Core primero, luego componentes, luego vistas -->
<script src="js/auth.js"></script>
<script src="js/navigation.js"></script>
<script src="js/main.js"></script>

<script src="js/components/table.js"></script>
<script src="js/components/card.js"></script>
<script src="js/components/modal.js"></script>
<script src="js/components/form.js"></script>
<script src="js/components/badge.js"></script>

<script src="js/views/dashboard.js"></script>
<script src="js/views/orders.js"></script>
<script src="js/views/repairs.js"></script>
<script src="js/views/boards.js"></script>
<script src="js/views/ics.js"></script>
<script src="js/views/measurements.js"></script>
<script src="js/views/board-points.js"></script>
<script src="js/views/solutions.js"></script>
<script src="js/views/references.js"></script>
<script src="js/views/diagramas.js"></script>
<script src="js/views/config.js"></script>
<script src="js/views/reports.js"></script>
<script src="js/views/clients.js"></script>
<script src="js/views/budgets.js"></script>
<script src="js/views/invoices.js"></script>
<script src="js/views/inventory.js"></script>

<script src="placas-data.js"></script>
```

---

## 5. Sidebar — estructura y secciones

### Configuración de navegación centralizada

El archivo `navigation.js` debe contener `NAV_CONFIG`, un array que define toda la sidebar:

```js
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

Esta configuración es la **única fuente de verdad** para la navegación. `renderSidebar()` y
`cambiarVista()` la leen de aquí. Para modificar items, se cambia solo este array.

### Estados visuales de la sidebar

| Estado | Desktop | Mobile |
|--------|---------|--------|
| Expandida | Ancho 240px, visible siempre | Ancho 280px, toggle con ☰ + overlay |
| Colapsada | No aplica (no se colapsa en desktop) | Ancho 60px solo íconos (alternativa) |
| Cerrada | No aplica | 0 — solo se ve ☰ en el header |

### Funciones de `navigation.js`

```js
/**
 * Renderiza la sidebar completa a partir de NAV_CONFIG.
 * Crea los elementos del DOM dentro de <nav id="sidebar">.
 * Asigna event listeners a cada ítem. Se llama una vez al iniciar la app.
 */
function renderSidebar() {}

/**
 * Cambia la vista activa: oculta todos los view containers,
 * muestra el solicitado, marca el item activo en la sidebar,
 * y ejecuta la carga de datos correspondiente.
 *
 * @param {string} vistaId - ID de la vista a mostrar (ej: 'dashboard', 'ordenes')
 */
function cambiarVista(vistaId) {}

/**
 * Togglea la visibilidad de la sidebar en mobile (< 768px).
 * Muestra/oculta el overlay y agrega/remueve clase .sidebar-open.
 */
function toggleSidebar() {}

/**
 * Cierra la sidebar en mobile (remueve clase .sidebar-open + oculta overlay).
 * Se llama al hacer click en el overlay o al seleccionar un item.
 */
function closeSidebar() {}
```

---

## 6. Documentación externa

Se crearán 6 archivos de documentación en `docs/`. Todos en español neutral profesional.
NO deben contener jerga rioplatense ni tono coloquial. Deben ser documentos técnicos formales.

### `docs/README.md`

Visión general de la arquitectura frontend (~40 líneas):
- Qué tecnología usa (vanilla JS, CSS puro, sin frameworks)
- Estructura de carpetas con breve descripción de cada una
- Cómo se sirve (archivos estáticos desde FastAPI)
- Cómo levantar el entorno de desarrollo
- Convenciones generales (nombres de archivos, idioma, JSDoc obligatorio)

### `docs/ARCHITECTURE.md`

Organización del frontend y flujo de datos (~100 líneas):
- Arquitectura general: SPA con funciones-componente que devuelven HTML
- Flujo de datos: API fetch → función vista → innerHTML (diagrama ASCII)
- Patrón de funciones-componente explicado con ejemplos
- Cómo se maneja el estado (variables globales mínimas, localStorage para auth)
- Cómo se comunican los módulos (scope global, window)
- Seguridad: tokens JWT, refresh, almacenamiento

### `docs/COMPONENTS.md`

Catálogo de todas las funciones-componente (~150 líneas):
- `renderTable(headers, rows, opts)` — tabla reutilizable | firma, parámetros, ejemplo de uso, por qué existe
- `renderCard(config)` — card genérica | firma, parámetros, variantes de uso
- `openModal(config)` — modal reutilizable | firma, parámetros, ejemplo
- `renderField(config)` — helpers de formularios | firma, variantes (text, date, select)
- `renderBadge(text, variant)` — badges de estado | firma, variantes de color

Cada entrada debe explicar **el problema que resuelve** y dar al menos un ejemplo completo.

### `docs/NAVIGATION.md`

Cómo funciona la navegación (~80 líneas):
- Estructura de `NAV_CONFIG` explicada
- Cómo `renderSidebar()` consume la configuración
- Qué hace `cambiarVista()` paso a paso
- **Guía paso a paso para agregar una nueva vista:**
  1. Crear archivo en `static/js/views/mi-vista.js`
  2. Agregar contenedor `<div id="viewMiVista">` en `index.html`
  3. Agregar el item a `NAV_CONFIG` en `navigation.js`
  4. Agregar `<script src="js/views/mi-vista.js">` en `index.html`
  5. Si requiere carga de datos, agregar `if (vista === 'mi-vista')` en `cambiarVista()`
- Cómo funciona el colapso en mobile (media query, toggle, overlay)

### `docs/STYLE.md`

Guía de estilo visual (~80 líneas):
- Variables CSS existentes en `:root` (cada una explicada con su propósito y valor)
- Variables nuevas agregadas para la sidebar
- Convenciones de nombres de clases CSS
- Cómo mantener consistencia visual (paleta, espaciado, tipografía)
- Patrones de responsive (breakpoints, grid, flex)
- Cómo contribuir estilos nuevos sin romper los existentes

### `docs/EXAMPLES.md`

Ejemplos completos de cómo agregar funcionalidad (~150 líneas):

- **Ejemplo 1: Agregar un módulo de "Proveedores"** — paso a paso completo:
  Crear archivo `static/js/views/providers.js`, agregar a `NAV_CONFIG`, agregar script en HTML,
  función renderPlaceholder inicial, documentación JSDoc.

- **Ejemplo 2: Agregar una columna a la tabla de órdenes** — workflow completo:
  Modificar `renderOrdenes()` para incluir nueva columna, actualizar headers, verificar
  que el dato existe en la respuesta de la API.

- **Ejemplo 3: Crear un nuevo componente reutilizable** — `renderList()`:
  Desde cero: especificación, implementación, JSDoc, documentación en COMPONENTS.md, integración.

Cada ejemplo debe incluir: código real, explicación de cada paso, y el resultado esperado.

---

## 7. Reglas de negocio

| ID | Regla |
|----|-------|
| RN1 | La primera vista al cargar la aplicación (post-login) debe ser **Dashboard**. No "Por mes" como antes. |
| RN2 | La lógica de agregar órdenes (`agregarOrden()`) y consultar puntaje debe preservarse exactamente igual, solo reubicada en `views/orders.js`. |
| RN3 | El Clasificador se elimina. No debe haber código del clasificador ni referencias en HTML ni JS. |
| RN4 | "BoardDoctor" como nombre visible desaparece. Internamente los endpoints de API y nombres de funciones pueden mantener "boarddoctor" para compatibilidad. |
| RN5 | Los placeholders no tienen ninguna lógica de negocio. Son exclusivamente UI. No hacen fetch. |
| RN6 | La sidebar lee su configuración de `NAV_CONFIG`. Para agregar/modificar items solo se modifica ese array. |
| RN7 | No se agregan dependencias externas (npm, CDN, librerías). Todo vanilla JS. |
| RN8 | Firebase (placas) se mantiene intacto. No se modifica `placas-data.js` ni la lógica de sincronización. |
| RN9 | El modal overlay existente (`#placaModal`) se reutiliza. No se crea un nuevo sistema de modales. |

---

## 8. Criterios de aceptación

### Sidebar

- [ ] CA1: La sidebar se renderiza a la izquierda con las 3 secciones (TALLER, CONOCIMIENTO, ADMIN)
- [ ] CA2: Cada sección tiene sus items con ícono + nombre, en el orden correcto según RF1.2
- [ ] CA3: El hover sobre un item ilumina el fondo (usando `--accent-soft` o similar)
- [ ] CA4: El item activo tiene un indicador visual claro (borde izquierdo `--accent`)
- [ ] CA5: La sidebar tiene scroll interno si los items exceden el alto del viewport

### Mobile

- [ ] CA6: En viewport < 768px, la sidebar está oculta por defecto
- [ ] CA7: El botón hamburguesa (☰) togglea la sidebar
- [ ] CA8: Al abrir la sidebar en mobile, aparece un overlay semitransparente
- [ ] CA9: Click en el overlay cierra la sidebar
- [ ] CA10: En mobile el contenido principal ocupa `width: 100%`

### Vistas

- [ ] CA11: Dashboard es la primera vista al cargar (post-login)
- [ ] CA12: Dashboard funciona exactamente como el anterior `viewEstadisticas`
- [ ] CA13: La vista Órdenes consolida el contenido de `viewMes` + `viewGeneral`
- [ ] CA14: `agregarOrden()` funciona exactamente como antes
- [ ] CA15: `cargarMes()` y `cargarTodas()` funcionan exactamente como antes
- [ ] CA16: Reparaciones, Placas, ICs, Mediciones, Puntos placa, Soluciones, Referencias, Config funcionan igual que antes
- [ ] CA17: "Diagramas" aparece en el sidebar y vista, con la misma funcionalidad de BoardDoctor
- [ ] CA18: Reportes funciona como vista standalone con toda la funcionalidad del modal anterior
- [ ] CA19: Clientes, Presupuestos, Facturación, Inventario muestran placeholder "Próximamente"

### Eliminaciones

- [ ] CA20: `viewMes` eliminado del HTML y JS (contenido migrado a órdenes)
- [ ] CA21: `viewGeneral` eliminado del HTML y JS (contenido migrado a órdenes)
- [ ] CA22: `viewClasificador` eliminado del HTML y JS completamente
- [ ] CA23: No hay referencias visibles a "BoardDoctor" en la UI
- [ ] CA24: Los tabs horizontales originales (`<div class="tabs">`) no existen en el HTML

### Documentación

- [ ] CA25: `docs/README.md` existe y describe la arquitectura frontend
- [ ] CA26: `docs/ARCHITECTURE.md` existe con diagrama de flujo de datos
- [ ] CA27: `docs/COMPONENTS.md` existe con todas las funciones-componente documentadas
- [ ] CA28: `docs/NAVIGATION.md` existe con guía paso a paso para agregar nuevas vistas
- [ ] CA29: `docs/STYLE.md` existe con variables CSS y convenciones visuales
- [ ] CA30: `docs/EXAMPLES.md` existe con al menos 3 ejemplos completos
- [ ] CA31: Toda función pública en archivos JS tiene JSDoc completo con @param y @returns
- [ ] CA32: Las funciones-componente tienen @example en su JSDoc

### No funcionales

- [ ] CA33: No hay nuevas dependencias externas (npm, CDN, librerías)
- [ ] CA34: No hay cambios en el backend (FastAPI, SQLAlchemy, endpoints)
- [ ] CA35: No hay cambios en Firebase ni en `placas-data.js`
- [ ] CA36: La app carga sin errores en consola del navegador (Chrome/Firefox)
- [ ] CA37: Las 13 vistas/funcionalidades existentes funcionan post-migración
- [ ] CA38: Login y auth (JWT, refresh) fluyen exactamente igual que antes
- [ ] CA39: El botón "Generar informe" en Dashboard lleva a la vista Reportes

---

## 9. Glosario

| Término | Definición |
|---------|------------|
| **BoardDoctor** | Sistema previo de importación de diagramas, ICs y compatibilidades. El nombre visible se reemplaza por "Diagramas". Los endpoints y funciones internas pueden conservar el nombre para compatibilidad. |
| **Función-componente** | Patrón de diseño donde una función pura recibe datos y devuelve un string HTML. No tiene estado interno, no modifica el DOM directamente. Ej: `renderTable(data)` → `"<table>...</table>"` |
| **JSDoc** | Estándar de documentación de código JavaScript mediante comentarios estructurados `/** ... */`. Similar a JavaDoc. |
| **NAV_CONFIG** | Array de configuración centralizada en `navigation.js` que define todos los items de la sidebar, sus secciones, íconos y propiedades. |
| **Placeholder** | Vista sin lógica de negocio que muestra un mensaje "Próximamente". No carga datos, no hace fetch a la API. |
| **Sidebar colapsable** | Sidebar que en mobile se puede ocultar (ancho reducido a 0 o solo íconos) mediante un botón toggle, con overlay de fondo semitransparente. |
| **SPA** | Single-Page Application: toda la UI se maneja desde una sola página HTML que intercambia vistas mediante JavaScript, sin recargar la página. |
| **View container** | Elemento `<div>` con `id="viewX"` y `style="display:none"` que contiene el HTML de una vista. `cambiarVista()` togglea entre `display: block` y `display: none`. |

---

## 10. Preguntas abiertas

| # | Pregunta | Impacto | Resolución propuesta |
|---|----------|---------|---------------------|
| P1 | ¿El Dashboard actual (`viewEstadisticas`) es el que se quiere como "Dashboard" principal o se quiere uno nuevo (más simple/resumido)? | Determina si se modifica o conserva la vista actual. | Se asume que el dashboard actual es suficiente. Si se requiere uno nuevo, se crea en un cambio posterior. |
| P2 | ¿La vista Reportes debe ser un modal o una vista standalone? Actualmente es un modal dentro del dashboard. | Afecta la UI/UX de reportes. | Se especifica como vista standalone en la sidebar, pero se puede mantener como modal si se prefiere. |
| P3 | ¿"Usuarios" aparece en la propuesta dentro de ADMIN pero no en la lista de vistas del usuario. ¿Se agrega como placeholder o se omite? | Afecta el contenido de la sección ADMIN. | Se omite por ahora. Si se necesita, se agrega como placeholder en un paso posterior. |
| P4 | ¿El sidebar colapsa a solo íconos en mobile o se oculta completamente con hamburguesa? | Afecta diseño de sidebar.css y toggleSidebar(). | Se prioriza la opción de hamburguesa + overlay por ser más limpia en mobile. La opción de solo íconos queda como alternativa. |
