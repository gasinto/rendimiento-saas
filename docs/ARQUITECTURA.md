# Rendimiento SaaS — Documentación del sistema

> Versión SaaS del sistema de gestión de reparaciones de NSP Notebooks.  
> FastAPI + PostgreSQL + SQLAlchemy async + Alembic.

---

## Índice

1. [Estructura del proyecto](#1-estructura-del-proyecto)
2. [Cómo levantar el servidor](#2-cómo-levantar-el-servidor)
3. [Arquitectura general](#3-arquitectura-general)
4. [Base de datos (PostgreSQL)](#4-base-de-datos-postgresql)
5. [Backend — FastAPI](#5-backend--fastapi)
6. [Frontend — SPA](#6-frontend--spa)
7. [Routers — cada endpoint explicado](#7-routers--cada-endpoint-explicado)
8. [Migraciones con Alembic](#8-migraciones-con-alembic)
9. [Modelos de datos (ORM)](#9-modelos-de-datos-orm)
10. [Autenticación](#10-autenticación)
11. [Docker / Railway](#11-docker--railway)
12. [Cómo agregar una funcionalidad nueva](#12-cómo-agregar-una-funcionalidad-nueva)

---

## 1. Estructura del proyecto

```
rendimiento-saas/
├── app/                          # Código principal (backend)
│   ├── alembic/                  # Migraciones de base de datos
│   │   ├── env.py                #   Config de Alembic (lee modelos, conecta DB)
│   │   ├── script.py.mako        #   Template para nuevas migraciones
│   │   └── versions/             #   Migraciones generadas (una por cambio)
│   ├── models/                   # Modelos SQLAlchemy (ORM → tablas)
│   │   ├── __init__.py           #   Exporta todos los modelos
│   │   ├── tenant.py             #   Tenants (multi-empresa)
│   │   ├── user.py               #   Usuarios
│   │   ├── order.py              #   Órdenes de reparación
│   │   ├── repair.py             #   Reparaciones (resumen)
│   │   ├── board.py              #   Placas / modelos
│   │   ├── measurement.py        #   Mediciones de componentes
│   │   ├── solution.py           #   Soluciones conocidas
│   │   ├── reference.py          #   Referencias técnicas
│   │   ├── score.py              #   Puntajes / valoraciones
│   │   ├── ic.py                 #   Circuitos integrados
│   │   ├── boarddoctor.py        #   Diagramas / compatibilidad ICs
│   │   ├── equipment.py          #   Tipos de equipo
│   │   └── config_model.py       #   Configuraciones del sistema
│   ├── routers/                  # Endpoints de la API (cada uno es un router)
│   │   ├── __init__.py
│   │   ├── health.py             #   GET /health — health check
│   │   ├── auth.py               #   POST /auth/login, /auth/refresh
│   │   ├── tenants.py            #   CRUD de empresas (multi-tenant)
│   │   ├── orders.py             #   CRUD de órdenes de reparación
│   │   ├── repairs.py            #   CRUD de reparaciones
│   │   ├── sessions.py           #   Sesiones de reparación (temporizador)
│   │   ├── scores.py             #   CRUD de puntajes
│   │   ├── boards.py             #   CRUD de placas
│   │   ├── ics.py                #   CRUD de circuitos integrados
│   │   ├── measurements.py       #   CRUD de mediciones
│   │   ├── solutions.py          #   CRUD de soluciones conocidas
│   │   ├── references.py         #   CRUD de referencias técnicas
│   │   ├── types.py              #   CRUD de tipos de equipo
│   │   ├── dashboard.py          #   GET /dashboard — estadísticas
│   │   ├── reports.py            #   GET /reports — reportes PDF/XLSX
│   │   ├── search.py             #   GET /search — búsqueda global
│   │   └── boarddoctor.py        #   GET /boarddoctor — importar datos
│   ├── schemas/                  # Schemas Pydantic (validación de datos)
│   ├── services/                 # Lógica de negocio (capa de servicios)
│   ├── __init__.py
│   ├── main.py                   # ★ PUNTO DE ENTRADA — fábrica de la app
│   ├── config.py                 # Configuración desde .env / variables de entorno
│   ├── database.py               # Engine y sesión de SQLAlchemy async
│   ├── dependencies.py           # Dependencias compartidas (get_db, get_current_user)
│   └── middleware.py             # Middleware (CORS, logging, etc.)
├── static/                       # Frontend (archivos estáticos)
│   ├── index.html                #   ★ App SPA (single-page application)
│   └── placas-data.js            #   Datos de placas
├── scripts/                      # Scripts auxiliares
├── docs/                         # Documentación
│   └── ARQUITECTURA.md           #   Este archivo
├── .env                          # Variables de entorno locales
├── .env.example                  # Ejemplo de variables de entorno
├── docker-compose.yml            # PostgreSQL en Docker
├── Dockerfile                    # Para Railway / deploy
├── railway.json                  # Config de Railway
├── requirements.txt              # Dependencias Python
├── alembic.ini                   # Config de Alembic
└── iniciar-servidor.bat          # ★ Script para arrancar todo
```

---

## 2. Cómo levantar el servidor

### Automático (recomendado)

Hacé doble clic en `iniciar-servidor.bat`. Ese script:

1. Verifica que PostgreSQL esté corriendo en Docker
2. Si no está, lo inicia o lo crea desde `docker-compose.yml`
3. Aplica migraciones pendientes con Alembic
4. Inicia el servidor con `uvicorn`

### Manual paso a paso

```bash
# 1. Pararse en la carpeta del proyecto
cd C:\Users\Diego\Documents\rendimiento-saas

# 2. Iniciar PostgreSQL (si no está corriendo)
docker start rendimiento-pg
# o si nunca se creó:
docker compose up -d

# 3. Aplicar migraciones (crea/actualiza tablas)
alembic upgrade head

# 4. Iniciar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8501
```

### URLs una vez iniciado

| URL | Qué es |
|-----|--------|
| http://localhost:8501 | Frontend SPA |
| http://localhost:8501/docs | Documentación interactiva (Swagger) |
| http://localhost:8501/redoc | Documentación alternativa (ReDoc) |
| http://localhost:8501/openapi.json | Esquema OpenAPI |
| http://localhost:8501/health | Health check |

---

## 3. Arquitectura general

El sistema sigue una arquitectura en capas típica de FastAPI:

```
Cliente (navegador / app)
       │
       ▼
  ┌──────────────┐
  │  Middleware   │  ← CORS, logging, errores
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │    Router    │  ← Endpoints (cada archivo = un grupo de rutas)
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │   Service    │  ← Lógica de negocio (capa opcional)
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │    Modelo    │  ← SQLAlchemy ORM (define la tabla)
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │  PostgreSQL  │  ← Base de datos real
  └──────────────┘
```

**Flujo de una petición típica:**

1. El navegador hace `GET /api/ordenes`
2. FastApplication recibe la request
3. Pasa por middleware (CORS, logging)
4. El router `orders.py` procesa la ruta
5. Hace una consulta a la base de datos vía SQLAlchemy async
6. Devuelve JSON al frontend

---

## 4. Base de datos (PostgreSQL)

### Conexión

- **URL**: `postgresql+asyncpg://postgres:postgres@localhost:5432/rendimiento`
- Se configura en `.env` con `DATABASE_URL`
- El engine se crea en `app/database.py`

### Tablas principales

Creadas por las migraciones de Alembic en base a los modelos (ver [Modelos](#9-modelos-de-datos-orm)):

| Tabla | Modelo | Descripción |
|-------|--------|-------------|
| `tenants` | `Tenant` | Empresas/clientes (multi-tenant) |
| `users` | `User` | Usuarios del sistema |
| `ordenes` | `Order` | Órdenes de reparación (detalle completo) |
| `reparaciones` | `Repair` | Reparaciones (resumen para dashboard) |
| `sesiones_reparacion` | `RepairSession` | Sesiones con temporizador |
| `placas` | `Board` | Modelos de placa madre |
| `bloques_placa` | `BoardBlock` | Bloques funcionales de cada placa |
| `notas_placa` | `BoardNote` | Notas técnicas por placa |
| `circuitos` | `Circuit` | Circuitos integrados de cada placa |
| `mediciones` | `Measurement` | Mediciones de referencia |
| `mediciones_placa` | `BoardMeasurement` | Mediciones específicas de una placa |
| `soluciones` | `Solution` | Soluciones documentadas por falla |
| `referencias` | `Reference` | Referencias técnicas (pines, etc.) |
| `puntajes` | `Score` | Valoraciones/resultados |
| `tipos_equipo` | `EquipmentType` | Tipos de equipo (Notebook, PC, etc.) |
| `diagramas` | `Diagram` | Diagramas/boardviews importados |
| `ic_marcas` | `ICMark` | Marcas de circuitos integrados |
| `ic_compatibilidad` | `ICCompatibility` | Compatibilidad entre ICs |

### ¿Dónde están los datos?

Los datos persisten en un volumen Docker: `pgdata:/var/lib/postgresql/data`

Si borrás el contenedor con `docker compose down -v`, perdés todos los datos.

---

## 5. Backend — FastAPI

### `app/main.py` — Punto de entrada

```python
app = create_app()  # Se ejecuta al importar
```

La función `create_app()`:
1. Crea la instancia de FastAPI con metadata
2. Registra middleware (CORS, logging)
3. Incluye todos los routers (cada uno = grupo de endpoints)
4. Monta archivos estáticos (SPA frontend)
5. Registra exception handlers globales
6. En startup: corre migraciones Alembic + seed del admin
7. En shutdown: cierra conexiones de base de datos

### `app/config.py` — Configuración

Usa `pydantic-settings` para leer de `.env` y variables de entorno.

```python
class Settings(BaseSettings):
    database_url: str              # PostgreSQL connection string
    jwt_secret: str                # Firma de tokens JWT
    jwt_algorithm: str             # Algoritmo (HS256)
    admin_email: str               # Email del admin por defecto
    admin_password: str            # Password del admin por defecto
    cors_origin: str               # Origen permitido para CORS
    app_name: str                  # Nombre de la app
    debug: bool                    # Modo debug
```

Se accede como `from app.config import settings`.

### `app/database.py` — Conexión a DB

Crea un engine asíncrono con `asyncpg`:

```python
engine = create_async_engine(settings.database_url, ...)
async_session_factory = async_sessionmaker(engine, ...)
```

El `Base` es la clase base de todos los modelos ORM.
`get_db()` es un dependency generator que da una sesión por request.

### `app/middleware.py` — Middleware

- **CORS**: permite que el frontend se comunique con el backend desde cualquier origen
- **Request logging**: loguea cada request con método, ruta, status y tiempo

### `app/dependencies.py` — Dependencias

Funciones compartidas entre routers:
- `get_db()`: devuelve una sesión de base de datos
- `get_current_user()`: valida JWT y devuelve el usuario autenticado

---

## 6. Frontend — SPA

El frontend es una Single-Page Application hecha en vanilla HTML + JavaScript.

Se sirve desde `static/index.html`. La app:
- Hace fetch a los endpoints de la API
- Renderiza las vistas según la pestaña activa
- Usa el mismo diseño que el sistema original (rendimiento/)

La API se llama con la URL base que está configurada en el frontend (por defecto, misma origen).

---

## 7. Routers — cada endpoint explicado

### `health.py` — Health check

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Devuelve `{"status":"ok","db":"connected"}` si todo funciona |

### `auth.py` — Autenticación

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/auth/me` | Devuelve el usuario autenticado (requiere token) |
| POST | `/auth/login` | Login: email + password → devuelve access_token + refresh_token |
| POST | `/auth/refresh` | Refresca el access_token usando refresh_token |

### `tenants.py` — Empresas (multi-tenant)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/tenants/` | Lista todos los tenants |
| POST | `/api/tenants/` | Crea un nuevo tenant |
| GET | `/api/tenants/{id}` | Obtiene un tenant por ID |
| PUT | `/api/tenants/{id}` | Actualiza un tenant |
| DELETE | `/api/tenants/{id}` | Elimina un tenant |

### `orders.py` — Órdenes de reparación

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/orders/` | Lista órdenes (filtro por ?estado=, ?empresa_id=, ?q=) |
| POST | `/api/orders/` | Crea una nueva orden |
| GET | `/api/orders/{id}` | Obtiene detalle de una orden |
| PUT | `/api/orders/{id}` | Actualiza una orden |
| DELETE | `/api/orders/{id}` | Elimina una orden |
| GET | `/api/orders/{id}/sessions` | Sesiones de reparación de una orden |

### `sessions.py` — Sesiones de reparación

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/sessions/` | Lista sesiones |
| POST | `/api/sessions/` | Inicia una sesión (start) |
| PUT | `/api/sessions/{id}` | Actualiza sesión (pause/resume/end) |
| DELETE | `/api/sessions/{id}` | Elimina sesión |

### `repairs.py` — Reparaciones (resumen)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/reparaciones/` | Lista reparaciones |
| POST | `/api/reparaciones/` | Crea una reparación |
| GET | `/api/reparaciones/{id}` | Obtiene detalle |
| PUT | `/api/reparaciones/{id}` | Actualiza |
| DELETE | `/api/reparaciones/{id}` | Elimina |

### `scores.py` — Puntajes

CRUD completo de puntajes/valoraciones.

### `boards.py` — Placas

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/boards/` | Lista placas |
| POST | `/api/boards/` | Crea placa |
| GET | `/api/boards/{id}` | Detalle de placa con bloques y mediciones |
| PUT | `/api/boards/{id}` | Actualiza placa |
| DELETE | `/api/boards/{id}` | Elimina placa |
| GET | `/api/boards/{id}/blocks` | Bloques de una placa |
| GET | `/api/boards/{id}/measurements` | Mediciones de una placa |
| GET | `/api/boards/placas` | Lista compacta de placas (para selectores) |
| GET | `/api/boards/blocks` | Todos los bloques |

### `ics.py` — Circuitos Integrados

CRUD de ICs con búsqueda por marking.

### `measurements.py` — Mediciones

CRUD de mediciones de referencia y por placa.

### `solutions.py` — Soluciones

CRUD de soluciones documentadas.

### `references.py` — Referencias técnicas

CRUD de referencias (pinouts, datasheets).

### `types.py` — Tipos de equipo

CRUD de tipos de equipo.

### `dashboard.py` — Estadísticas

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/dashboard/` | Estadísticas generales (órdenes del mes, puntajes, etc.) |

### `reports.py` — Reportes

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/reports/orders?formato=pdf` | Reporte PDF de órdenes |
| GET | `/api/reports/orders?formato=xlsx` | Reporte Excel de órdenes |

### `search.py` — Búsqueda global

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/search?q=texto` | Busca en órdenes, placas, soluciones, referencias |

### `boarddoctor.py` — BoardDoctor

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/boarddoctor/diagramas` | Lista diagramas importados |
| GET | `/api/boarddoctor/diagramas?marca=&modelo=&tipo=` | Filtro de diagramas |
| POST | `/api/boarddoctor/importar` | Re-importa datos desde CSVs |

---

## 8. Migraciones con Alembic

Las migraciones mantienen la base de datos sincronizada con los modelos ORM.

### Comandos útiles

```bash
# Crear una migración automática (compara modelos con DB actual)
alembic revision --autogenerate -m "descripcion del cambio"

# Aplicar migraciones pendientes
alembic upgrade head

# Volver una migración atrás
alembic downgrade -1

# Ver historial de migraciones
alembic history

# Ver migración actual
alembic current
```

### Archivos importantes

- `alembic.ini` — Configuración general de Alembic
- `app/alembic/env.py` — Entorno de Alembic (importa modelos, conecta DB)
- `app/alembic/versions/` — Migraciones generadas (una por archivo)

### Cómo funciona

1. Definís los modelos en `app/models/` heredando de `Base`
2. Corrés `alembic revision --autogenerate -m "mensaje"`
3. Alembic compara los modelos con el estado actual de la DB y genera el diff
4. Revisás la migración generada en `app/alembic/versions/`
5. Corrés `alembic upgrade head` para aplicarla

---

## 9. Modelos de datos (ORM)

Cada archivo en `app/models/` define una clase que hereda de `Base` (SQLAlchemy).

**Ejemplo** (`app/models/order.py`):

```python
class Order(Base):
    __tablename__ = "ordenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    numero: Mapped[int]
    fecha: Mapped[str]
    placa: Mapped[str]
    falla: Mapped[str]
    diagnostico: Mapped[str]
    proceso: Mapped[str]
    solucion: Mapped[str]
    estado: Mapped[str]       # en_curso / completado
    resultado: Mapped[str]    # reparado / no_reparado / n/a
    tipo: Mapped[str]
    puntaje: Mapped[float]
    tipo_equipo: Mapped[str]
    marca: Mapped[str]
    modelo: Mapped[str]
    checklist: Mapped[str]
    created_at: Mapped[str]
```

Relaciones principales:
- `Order → Tenant`: Muchos a uno (cada orden pertenece a una empresa)
- `Order → RepairSession`: Uno a muchos (una orden puede tener varias sesiones)

---

## 10. Autenticación

El sistema usa JWT (JSON Web Tokens) para autenticación.

### Login

```
POST /auth/login
Body: { "email": "admin@nsp.com", "password": "admin123" }
Response: { "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

### Uso del token

El `access_token` se envía como header `Authorization: Bearer <token>`.

- **access_token**: dura 15 minutos
- **refresh_token**: dura 7 días

### Usuario admin por defecto

- Email: `admin@nsp.com`
- Password: `admin123`

Se crea automáticamente al iniciar el servidor (en `main.py` → `seed_default_admin()`).

---

## 11. Docker / Railway

### Local (Docker Desktop)

El `docker-compose.yml` solo levanta PostgreSQL:

```yaml
services:
  postgres:
    image: postgres:16
    container_name: rendimiento-pg
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: rendimiento
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
```

### Railway (producción)

El `Dockerfile` y `railway.json` están configurados para deploy en Railway.

Railway provee la variable `DATABASE_URL` automáticamente con la URL de PostgreSQL del servicio.

Si el URL viene como `postgresql://` (sin `+asyncpg`), el código lo transforma automáticamente en `postgresql+asyncpg://` en `app/config.py`.

---

## 12. Cómo agregar una funcionalidad nueva

### Ejemplo: agregar un campo "presupuesto" a las órdenes

```bash
# 1. Agregar el campo al modelo
#    En app/models/order.py:
#    presupuesto: Mapped[float] = mapped_column(default=0.0)

# 2. Generar migración
alembic revision --autogenerate -m "add presupuesto to ordenes"

# 3. Aplicar migración
alembic upgrade head

# 4. Agregar el campo al schema (app/schemas/)
#     y al router si querés exponerlo

# 5. Agregarlo al frontend (static/index.html)
```

### Agregar un endpoint nuevo

```bash
# 1. Crear router en app/routers/mi_cosa.py
# 2. Importarlo en app/main.py
# 3. Agregar app.include_router(mi_cosa.router)
# 4. Agregar la ruta correspondiente (si no existe) al frontend
```

### Arquitectura Router (estructura típica)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db

router = APIRouter(prefix="/api/mi-cosa", tags=["Mi Cosa"])

@router.get("/")
async def listar(db: AsyncSession = Depends(get_db)):
    """Lista todos los items."""
    # ... consulta con db.execute(...)
    return {"items": [...]}

@router.post("/")
async def crear(data: dict, db: AsyncSession = Depends(get_db)):
    """Crea un nuevo item."""
    # ... insert con db.execute(...) + db.commit()
    return {"ok": True, "id": nuevo_id}
```

### Debug / Troubleshooting

| Problema | Causa probable | Solución |
|----------|---------------|----------|
| `No es posible conectar con el servidor remoto` | Server no iniciado o puerto ocupado | Revisá que uvicorn esté corriendo. Fijate si otro proceso ocupa el :8501 |
| `relation "ordenes" does not exist` | Migraciones no aplicadas | Ejecutá `alembic upgrade head` |
| `Fatal error in launcher: Unable to create process` | Python no encontrado | Revisá tu PATH y que Python esté instalado |
| `dialect postgresql+asyncpg does not exist` | `asyncpg` no instalado | `pip install asyncpg` |
| `JWT invalid` | Token expirado o malformado | Hacé login de nuevo |
| Login no funciona | Admin no se creó | Revisá logs del startup. Podés forzar seed ejecutando `app/main.py` directamente |

---

## Convenciones de código

- **Idioma**: el código está en inglés (nombres de funciones, variables, clases, comentarios técnicos)
- **Strings al usuario**: en español (como en el sistema original)
- **Logging**: en español o inglés, lo que sea más claro
- **Commits**: Conventional Commits en español (ej: `feat: agregar campo presupuesto a ordenes`)

---

> Documentación generada el 2026-06-11. Para mantenerla actualizada, actualizá este archivo cuando agregues o modifiques funcionalidades.
