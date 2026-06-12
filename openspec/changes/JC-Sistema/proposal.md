# JC Sistema — Propuesta

## Intent

Reemplazar la navegación horizontal por una sidebar lateral con secciones agrupadas, renombrar "BoardDoctor" a "Diagramas", eliminar vistas obsoletas y agregar placeholders para nuevos módulos del taller — preparando el frontend para la expansión del sistema JC sin tocar el backend.

## Scope

### In Scope

- Sidebar lateral con secciones: **Dashboard**, **TALLER** (Clientes, Órdenes, Reparaciones, Facturación, Inventario), **CONOCIMIENTO** (ICs+Mediciones, Puntos Placa, Soluciones, Referencias, Diagramas), **ADMIN** (Config, Usuarios, Reportes)
- Sidebar colapsable en mobile (< 768px) con toggle
- Placeholders para Clientes, Presupuestos, Facturación, Inventario — mensaje "Próximamente", sin lógica
- Renombrar vista "BoardDoctor" → "Diagramas" (incluye las 4 cards: diagramas, ICs marca, compatibilidad, datasheets)
- Eliminar pestañas: "Por mes" (viewMes), "Todas las órdenes" (viewGeneral), "Clasificador" (viewClasificador)
- Reubicar lógica de agregar órdenes y consultar puntaje — de viewMes a vista Órdenes o donde corresponda
- Modificar `cambiarVista()` para sidebar en vez de tabs horizontales
- Coherencia visual con las variables CSS `:root` existentes

### Out of Scope

- Lógica de negocio de nuevos módulos (clientes, facturación, etc.) — solo placeholders
- Backend (FastAPI, SQLAlchemy, DB, endpoints)
- Autenticación o roles de usuario nuevos
- Base de conocimiento existente (ICs, mediciones, soluciones, referencias)
- Firebase / vista Placas — se mantiene igual

## Capabilities

### New Capabilities

- `navigation-sidebar`: Sidebar reemplaza tabs horizontales. Grupos colapsables. Colapsable en mobile. Sin nuevas dependencias.
- `placeholder-modules`: Vistas placeholder para Clientes, Presupuestos, Facturación, Inventario — solo UI, sin datos.

### Modified Capabilities

None — cambio puramente frontend. Ninguna capacidad existente cambia su comportamiento a nivel de especificación.

## Approach

1. **HTML**: Reemplazar `<div class="tabs">` horizontal (líneas 417–431) por un `<nav id="sidebar">` con estructura de secciones y sub-items
2. **JS**: Modificar `cambiarVista()` (líneas 1465–1501) para sidebar en vez de `.tabs button.active`. Agregar handlers de toggle para colapsar sidebar en mobile
3. **Vistas**: Crear divs placeholder ocultos (`display:none`) para los 4 nuevos módulos. Eliminar `viewMes`, `viewGeneral`, `viewClasificador` del HTML y de cambiarVista(). Renombrar referencias a "BoardDoctor" → "Diagramas"
4. **CSS**: Sidebar con `position: fixed`, `z-index`. Mantener paleta de variables CSS `:root`. Transition animada para colapsar. Overlay backdrop en mobile
5. **Lógica preservada**: `cargarMes()`, `cargarTodas()`, `agregarOrden()`, etc. se mantienen — solo se reubican o asocian a la nueva vista Órdenes
6. **Sin frameworks ni librerías** — vanilla JS, CSS puro, mismas herramientas

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `static/index.html` | Modified | Nav → sidebar, cambiarVista(), vistas reubicadas, placeholders nuevos |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Romper `cambiarVista()` | Low | Migración controlada. Probar todas las vistas post-cambio |
| Perder lógica de agregar órdenes | Low | Preservar funciones `agregarOrden()`, solo reubicar en vista Órdenes |
| Sidebar no usable en mobile | Low | Mobile-first con media query < 768px, toggle hamburguesa, overlay |
| CSS conflictos con sidebar fija | Low | Usar variables existentes, `position: fixed`, separar estilos nuevos |

## Rollback Plan

Git revert del commit. Restaurar `index.html` original. Sin migraciones de DB, sin cambios de backend — rollback inmediato y seguro.

## Dependencies

Ninguna. Sin cambios en backend, DB, paquetes, ni tooling.

## Success Criteria

- [ ] Sidebar visible con 4 secciones y todos los items agrupados
- [ ] Sidebar colapsable en mobile (< 768px) con botón toggle
- [ ] Todas las vistas existentes (Placas, ICs, Mediciones, Soluciones, etc.) funcionan desde sidebar
- [ ] Placeholders visibles para Clientes, Presupuestos, Facturación, Inventario
- [ ] "Diagramas" visible en lugar de "BoardDoctor" con misma funcionalidad
- [ ] viewMes, viewGeneral, viewClasificador eliminados del HTML y JS
- [ ] Log in / auth fluye igual
