# Tasks: Buscador de Diagramas e ICs

## T1 — Backend: Importar datos de BoardDoctor a la DB
- Agregar tablas `diagramas`, `ic_marcas`, `ic_compatibilidad` a `init_db()`
- Crear método `importar_boarddoctor_data()` que carga los 3 CSVs
- Llamarlo desde `init_db()` si tablas vacías

## T2 — Backend: API de búsqueda de diagramas
- `APIHandler.buscar_diagramas(params)` con filtro LIKE por modelo/marca/nombre
- Armar URL de descarga de Google Drive
- Ruta: `GET /api/diagramas?q=<texto>`

## T3 — Backend: API de búsqueda de ICs por marca
- `APIHandler.buscar_ic_marca(params)` con filtro LIKE por marking
- Ruta: `GET /api/ic-marcas?q=<marking>`

## T4 — Backend: API de compatibilidad de ICs
- `APIHandler.buscar_ic_compatibles(params)` con filtro LIKE por modelo
- Ruta: `GET /api/ic-compatibles?modelo=<modelo>`

## T5 — Backend: API de búsqueda de datasheets externos
- `APIHandler.buscar_datasheet_externo(params)` con requests + BS4
- Scrapea alldatasheet.com y datasheet4u.com
- Ruta: `GET /api/datasheet?componente=<componente>`

## T6 — Backend: Importación manual (POST)
- Ruta `POST /api/importar-boarddoctor`
- Llama a `importar_boarddoctor_data()` forzadamente

## T7 — Frontend: Sección de Diagramas e ICs
- Nueva solapa "🔍 Diagramas / ICs" en el navbar
- Sub-pestañas: Diagramas | ICs | Compatibilidad | Datasheets
- Cada una con input de búsqueda + resultados en cards/tabla
- Estilo consistente con el diseño dark existente

## T8 — Verificación
- Server.py se importa y ejecuta sin errores
- Datos de BoardDoctor se importan correctamente
- Búsquedas devuelven resultados
- Frontend carga sin errores
