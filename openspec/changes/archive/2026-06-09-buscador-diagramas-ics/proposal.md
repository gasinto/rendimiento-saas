# Proposal: Buscador de Diagramas e ICs

## Intent
Integrar los datos del catálogo de BoardDoctor (15,003 diagramas en Google Drive, 1,313 marcas de IC, 107 compatibilidades) en el sistema de Rendimiento como un módulo de búsqueda técnica.

## Alcance
- Importar `cloud_catalog.csv`, `ic_catalog.csv`, `ic_compatibility.csv` a la DB
- Buscar diagramas/boardviews por modelo de placa
- Buscar ICs por marca física (código de marking)
- Buscar datasheets externos (alldatasheet.com, datasheet4u.com)
- Mostrar reemplazos compatibles de ICs
- No incluye: descarga directa de Google Drive (solo mostrar URL), visualización de boardviews en el navegador

## Fuentes de datos
- `boarddoctor_backup/cloud_catalog.csv` — 15,003 archivos (9,303 esquemáticos + 5,700 boardviews)
- `boarddoctor_backup/ic_catalog.csv` — 1,313 marcas de IC
- `boarddoctor_backup/ic_compatibility.csv` — 107 compatibilidades
