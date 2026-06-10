# Spec: Buscador de Diagramas e ICs

## Funcionalidades

### F1 — Importar datos de BoardDoctor
- Al iniciar el server, detectar si las tablas `diagramas`, `ic_marcas`, `ic_compatibilidad` existen
- Si no existen, crearlas e importar los CSVs automáticamente desde `../boarddoctor_backup/`

### F2 — Buscar diagramas por modelo de placa
- Input parcial de texto
- Busca en `diagramas` por modelo, marca, nombre de archivo
- Devuelve: tipo (schematic/boardview), modelo, marca, nombre de archivo, URL de descarga (Google Drive), tamaño

### F3 — Buscar IC por marca física
- Input de código de marking (ej: AEA)
- Busca en `ic_marcas` por marking
- Devuelve: marking, modelo real, fabricante, función

### F4 — Buscar compatibilidad de IC
- Input de modelo de IC (ej: BQ24725)
- Busca en `ic_compatibilidad` por modelo
- Devuelve: modelo original, modelos compatibles, fabricante

### F5 — Buscar datasheet externo
- Input de componente
- Scraping a alldatasheet.com + datasheet4u.com
- Devuelve: título, URL del datasheet, fuente

## Tablas

### diagramas
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| marca | TEXT | Fabricante de la placa |
| modelo | TEXT | Modelo de la placa |
| tipo | TEXT | schematic / boardview |
| gdrive_id | TEXT | ID del archivo en Google Drive |
| nombre_archivo | TEXT | Nombre del archivo |
| tamaño_mb | REAL | Tamaño en MB |
| ultima_sync | TEXT | Fecha de última sincronización |

### ic_marcas
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| marking | TEXT | Código de marca física |
| modelo | TEXT | Modelo real del IC |
| fabricante | TEXT | Fabricante |
| funcion | TEXT | Descripción de la función |
| compatibilidad | TEXT | Notas de compatibilidad |

### ic_compatibilidad
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | |
| fabricante | TEXT | Fabricante |
| modelo | TEXT | Modelo original |
| compatibles | TEXT | Lista de modelos compatibles |

## API

### GET /api/diagramas?q=<texto>
Busca diagramas por modelo/marca/nombre
Response: `{ diagramas: [{ id, marca, modelo, tipo, gdrive_id, nombre_archivo, tamaño_mb, url_descarga }] }`

### GET /api/ic-marcas?q=<marking>
Busca ICs por código de marca
Response: `{ resultados: [{ marking, modelo, fabricante, funcion }] }`

### GET /api/ic-compatibles?modelo=<modelo>
Busca compatibilidades
Response: `{ resultados: [{ fabricante, modelo_original, compatibles }] }`

### GET /api/datasheet?componente=<nombre>
Busca datasheets externos
Response: `{ resultados: [{ titulo, url, fuente }] }`

### POST /api/importar-boarddoctor
Importa (o re-importa) los datos de BoardDoctor
Response: `{ ok: true, diagramas: N, ic_marcas: N, ic_compatibilidad: N }`
