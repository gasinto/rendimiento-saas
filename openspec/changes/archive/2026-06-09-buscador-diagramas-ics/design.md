# Design: Buscador de Diagramas e ICs

## Arquitectura

### Backend (server.py)
- Nuevas tablas en `init_db()`: `diagramas`, `ic_marcas`, `ic_compatibilidad`
- Nuevo método estático `importar_boarddoctor_data()` que se llama desde `init_db()` si las tablas están vacías
- 4 nuevos métodos en `APIHandler`:
  - `buscar_diagramas(params)` — query sobre diagramas
  - `buscar_ic_marca(params)` — query sobre ic_marcas
  - `buscar_ic_compatibles(params)` — query sobre ic_compatibilidad
  - `buscar_datasheet_externo(params)` — web scraping a alldatasheet/datasheet4u
- 5 nuevas rutas GET + 1 POST en RequestHandler
- La URL de descarga se construye como `https://drive.google.com/uc?export=download&id={gdrive_id}`

### Frontend (index.html)
- Nueva solapa "Diagramas" en la navegación principal
- Sección de búsqueda con input + resultados
- Pestañas internas: Diagramas, ICs, Datasheets
- Cada pestaña con su propio buscador

### Datasheet scraping
- requests + BeautifulSoup para alldatasheet.com y datasheet4u.com
- Manejo de errores si no hay conexión o el componente no se encuentra
- Timeout de 10 segundos

## Flujo de datos

1. Server inicia → `init_db()` → tablas creadas si no existen
2. Si tablas vacías → `importar_boarddoctor_data()` carga CSVs
3. Frontend se conecta a `/api/diagramas?q=...` etc.
4. Backend consulta DB o hace scraping y devuelve JSON
5. Frontend renderiza resultados en cards/tabla

## Paths
- CSV origen: `../boarddoctor_backup/cloud_catalog.csv`, `ic_catalog.csv`, `ic_compatibility.csv`
- DB destino: `rendimiento/rendimiento.db` (misma DB existente)
