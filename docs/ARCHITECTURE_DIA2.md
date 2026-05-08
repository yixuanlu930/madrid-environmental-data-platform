# Práctica 2 — Infraestructura Big Data ambiental para Madrid

Infraestructura de datos para analizar variables ambientales de Madrid usando dos APIs de Open-Meteo, orquestada con n8n, almacenada en MinIO, consultable mediante PostgreSQL y visualizable desde Apache Superset y Jupyter Lab.

---

## 1. Objetivo

La infraestructura recupera datos horarios del **día anterior** para Madrid, los almacena sin pérdida en un Data Lake por capas (raw → clean → processed → curated), los carga en una base de datos relacional para consultas SQL, y produce tablas optimizadas para análisis y dashboards.

Coordenadas usadas:

```text
latitude  = 40.4168
longitude = -3.7038
timezone  = Europe/Madrid
```

---

## 2. Fuentes de datos

| Fuente | URL base | Variables |
|---|---|---|
| Historical Weather API | `https://archive-api.open-meteo.com/v1/archive` | `temperature_2m`, `precipitation` |
| Air Quality API | `https://air-quality-api.open-meteo.com/v1/air-quality` | `ozone`, `carbon_dioxide` |

Cada API se consulta para el día anterior con resolución horaria. La salida esperada es:

- 24 filas horarias de meteorología
- 24 filas horarias de calidad del aire
- 96 observaciones en formato largo (24h × 4 variables)
- 24 filas en la tabla analítica final

---

## 3. Arquitectura

```text
n8n (orquestador)
  │
  │  POST /ingest → /preprocess → /analytics  (diario a las 07:00 Europe/Madrid)
  ▼
Servicio ETL Python (servidor HTTP interno)
  ├── Stage 1 /ingest:      Llama a las APIs → guarda RAW JSON → MinIO
  ├── Stage 2 /preprocess:  RAW → CLEAN CSV + PROCESSED (long) → MinIO + PostgreSQL
  └── Stage 3 /analytics:   RAW → CURATED (wide + resumen) → MinIO + PostgreSQL
  │
  │  Doble escritura: SDK MinIO  +  psycopg2 → PostgreSQL
  ▼
┌─────────────────────┐     ┌──────────────────────────────────┐
│   MinIO Data Lake   │     │         PostgreSQL               │
│   (compatible S3)   │     │   esquema: madrid_environment    │
│                     │     │                                  │
│  raw/               │     │  environment_observations_long   │
│  clean/             │     │  hourly_environment_wide         │
│  processed/         │     │  daily_variable_summary          │
│  curated/           │     │                                  │
└─────────────────────┘     └──────────────────┬───────────────┘
         ▲                                      │ SQL
         │                                      ▼
    Jupyter Lab                         Apache Superset
  (análisis Python)                   (dashboards BI)
```

> El nodo n8n **no llama directamente** a las APIs de Open-Meteo. Delega toda la lógica al servicio ETL Python, que hace las llamadas, las transformaciones y la carga tanto en MinIO como en PostgreSQL.

---

## 4. Componentes

| Componente | Imagen / Build | Función |
|---|---|---|
| `minio` | `minio/minio:latest` | Data Lake persistente tipo S3 |
| `minio-init` | `minio/mc:latest` | Crea el bucket al arrancar |
| `rabbitmq` | `rabbitmq:3-management` | Cola de mensajes entre servicios |
| `etl` | Build local (`Dockerfile`) | Ingesta, transformación y carga |
| `n8n` | `n8nio/n8n:latest` | Orquestación del flujo periódico |
| `n8n-init` | `n8nio/n8n:latest` | Importa los workflows automáticamente |
| `jupyter` | Build local (`Dockerfile`) | Entorno de análisis Python |
| `postgres` | `postgres:16` | Base de datos relacional para consultas SQL |
| `superset` | `apache/superset:3.1.0` | Dashboards e interfaz BI |
| `superset-init` | `apache/superset:3.1.0` | Inicialización del admin de Superset |
| Red `madrid-data-net` | bridge | Comunicación interna entre servicios |

---

## 5. Estructura del Data Lake

```text
data/
├── raw/                              ← JSON originales, sin modificar
│   ├── open_meteo_historical_weather/
│   │   └── date=YYYY-MM-DD/weather.json
│   └── open_meteo_air_quality/
│       └── date=YYYY-MM-DD/air_quality.json
├── clean/                            ← CSV limpios, una tabla por API (24 filas)
│   ├── historical_weather_hourly/
│   │   └── date=YYYY-MM-DD/weather_hourly.csv
│   └── air_quality_hourly/
│       └── date=YYYY-MM-DD/air_quality_hourly.csv
├── processed/                        ← Tabla larga unificada (96 filas) + manifests
│   ├── environment_observations_long/
│   │   └── date=YYYY-MM-DD/environment_observations_long.csv
│   └── manifests/
│       └── date=YYYY-MM-DD/manifest.json
└── curated/                          ← Tablas optimizadas para análisis
    ├── hourly_environment_wide/      ← 24 filas, todas las variables en columnas
    │   └── date=YYYY-MM-DD/hourly_environment_wide.csv
    └── daily_variable_summary/       ← 4 filas, estadísticas min/avg/max por variable
        └── date=YYYY-MM-DD/daily_variable_summary.csv
```

Todos los archivos siguen particionado Hive (`date=YYYY-MM-DD`) para facilitar consultas por fecha.

---

## 6. Esquema en PostgreSQL

Las zonas processed y curated se cargan automáticamente en el esquema `madrid_environment`:

| Tabla | Origen | Descripción |
|---|---|---|
| `environment_observations_long` | processed | 96 filas/día, una por variable/hora. Útil para filtros por variable |
| `hourly_environment_wide` | curated | 24 filas/día, todas las variables en columnas. Óptima para series temporales |
| `daily_variable_summary` | curated | 4 filas/día, estadísticas min/avg/max por variable. Principal tabla para dashboards |

---

## 7. Puesta en marcha

### Prerrequisitos

- Docker y Docker Compose instalados
- Puertos libres: 8000, 5432, 5672, 5678, 8088, 8890, 9000, 9001, 15672

### Paso 1 — Configuración del entorno

```bash
cp env.example .env
```

Los valores por defecto funcionan sin ningún cambio adicional.

### Paso 2 — Arrancar los servicios

```bash
docker compose up --build
```

Al arrancar ocurre lo siguiente de forma automática:

1. MinIO, RabbitMQ y PostgreSQL inician (con healthcheck)
2. `minio-init` espera a que MinIO esté sano y crea el bucket
3. El servicio ETL arranca cuando MinIO y PostgreSQL están listos
4. n8n arranca y `n8n-init` importa los tres workflows automáticamente
5. Superset arranca y `superset-init` crea el usuario administrador

Verifica que todos los servicios están en marcha:

```bash
docker compose ps
```

---

## 8. URLs de acceso

| Servicio | URL | Credenciales |
|---|---|---|
| ETL healthcheck | `http://localhost:8000/health` | — |
| n8n | `http://localhost:5678` | (ninguna por defecto) |
| MinIO Console | `http://localhost:9001` | `minioadmin / minioadmin` |
| RabbitMQ Management | `http://localhost:15672` | `admin / admin` |
| Jupyter Lab | `http://localhost:8890` | (sin token) |
| PostgreSQL | `localhost:5432` | `madrid / madrid` |
| Superset | `http://localhost:8088` | `admin / admin` |

---

## 9. Ejecutar el pipeline manualmente

Por defecto recupera el día anterior según la zona horaria `Europe/Madrid`.

Los tres stages en secuencia:

```bash
curl -X POST "http://localhost:8000/ingest"
curl -X POST "http://localhost:8000/preprocess"
curl -X POST "http://localhost:8000/analytics"
```

O todo en una sola llamada:

```bash
curl -X POST "http://localhost:8000/run"
```

Para una fecha concreta:

```bash
curl -X POST "http://localhost:8000/run?date=2026-05-05"
```

También puedes lanzarlo desde n8n con el botón **Test workflow** en la interfaz.

---

## 10. Validación de outputs

```bash
docker compose exec etl python src/validate_outputs.py --date 2026-05-05
```

Salida esperada (todos los checks en `[OK]`):

```text
Validating Madrid Open-Meteo outputs for date=2026-05-05
[OK] /app/data/raw/open_meteo_historical_weather/date=2026-05-05/weather.json
[OK] /app/data/raw/open_meteo_air_quality/date=2026-05-05/air_quality.json
[OK] /app/data/clean/historical_weather_hourly/date=2026-05-05/weather_hourly.csv rows=24
[OK] /app/data/clean/air_quality_hourly/date=2026-05-05/air_quality_hourly.csv rows=24
[OK] /app/data/processed/environment_observations_long/date=2026-05-05/environment_observations_long.csv rows=96
[OK] /app/data/curated/hourly_environment_wide/date=2026-05-05/hourly_environment_wide.csv rows=24
[OK] /app/data/curated/daily_variable_summary/date=2026-05-05/daily_variable_summary.csv rows=4
[OK] /app/data/processed/manifests/date=2026-05-05/manifest.json
```

---

## 11. n8n — workflows

Se importan automáticamente al arrancar gracias al servicio `n8n-init`. Hay tres workflows encadenados:

| Workflow | Descripción |
|---|---|
| `madrid_ingesta` | Llama a `/ingest` — descarga las APIs y guarda los JSON en raw/ |
| `madrid_preprocesamiento` | Llama a `/preprocess` — genera clean/ y processed/, carga en PostgreSQL |
| `madrid_analitica` | Llama a `/analytics` — genera curated/, carga en PostgreSQL |

Cada workflow se ejecuta diariamente a las 07:00 (Europe/Madrid) y puede lanzarse a mano desde la UI de n8n.

---

## 12. Configurar Superset

1. Acceder a `http://localhost:8088` — usuario `admin`, contraseña `admin`
2. Ir a **Settings → Database Connections → + Database**
3. Seleccionar **PostgreSQL**
4. Introducir la cadena de conexión:
   ```
   postgresql://madrid:madrid@postgres:5432/madrid_env
   ```
5. **Test Connection** → debe aparecer en verde → Guardar

### Crear datasets

1. **Data → Datasets → + Dataset**
2. Seleccionar la base de datos PostgreSQL, esquema `madrid_environment`
3. Empezar por `daily_variable_summary` para dashboards de alto nivel
4. Usar `hourly_environment_wide` para gráficos de series temporales

### Consultas SQL de ejemplo (SQL Lab o psql)

```sql
-- Temperatura media por día
SELECT date, avg_value AS temperatura_media_c
FROM madrid_environment.daily_variable_summary
WHERE variable = 'temperature_2m'
ORDER BY date;

-- Serie horaria de ozono y CO2
SELECT time, ozone, carbon_dioxide
FROM madrid_environment.hourly_environment_wide
ORDER BY time;

-- Días con mayor concentración de ozono
SELECT date, max_value AS ozono_max
FROM madrid_environment.daily_variable_summary
WHERE variable = 'ozone'
ORDER BY max_value DESC
LIMIT 10;
```

---

## 13. Notebook de análisis (Jupyter)

Abre `http://localhost:8890`. El notebook está en:

```text
notebooks/analyze_curated_data.ipynb
```

Lee directamente desde MinIO usando el endpoint interno `minio:9000`. También puede conectarse a PostgreSQL usando las variables de entorno `POSTGRES_*` disponibles en el contenedor.

---

## 14. Comandos útiles

```bash
# Ver estado de los servicios
docker compose ps

# Ver logs en tiempo real
docker compose logs -f etl
docker compose logs -f n8n
docker compose logs -f superset

# Ejecutar pipeline para una fecha específica (dentro del contenedor)
docker compose exec etl python src/pipeline.py --date 2026-05-05

# Conectarse a PostgreSQL
docker exec -it madrid-postgres psql -U madrid -d madrid_env

# Parar servicios (conserva volúmenes y datos)
docker compose down

# Parar y eliminar todos los datos persistidos
docker compose down -v
```

---

## 15. Estructura del repositorio

```text
.
├── docker-compose.yml        # Definición de todos los servicios
├── Dockerfile                # Imagen compartida por etl y jupyter
├── requirements.txt          # Dependencias Python
├── env.example               # Plantilla de variables de entorno (copiar a .env)
├── .env                      # Variables de entorno activas (NO subir a git)
├── src/
│   ├── config.py             # Configuración centralizada desde variables de entorno
│   ├── sources.py            # Llamadas HTTP a las APIs de Open-Meteo
│   ├── transform.py          # Transformaciones raw → clean → processed → curated
│   ├── storage.py            # Carga de archivos en MinIO
│   ├── db_loader.py          # Carga de datos en PostgreSQL
│   ├── pipeline.py           # Orquestación del flujo (3 stages)
│   ├── server.py             # Servidor HTTP (/ingest /preprocess /analytics /run /health)
│   ├── utils.py              # Utilidades (escritura CSV/JSON, listado de ficheros)
│   └── validate_outputs.py   # Validación de los outputs generados
├── n8n/workflows/
│   ├── madrid_ingesta.json           # Workflow de ingesta
│   ├── madrid_preprocesamiento.json  # Workflow de preprocesamiento
│   └── madrid_analitica.json         # Workflow de analítica
├── postgres/
│   └── init_postgres.sql     # DDL del esquema analítico (se ejecuta al crear el contenedor)
├── superset/
│   ├── superset_config.py    # Configuración de Superset
│   └── superset_init.sh      # Script de inicialización del admin
├── notebooks/
│   └── analyze_curated_data.ipynb    # Notebook de análisis desde MinIO
├── data/                     # Data Lake local (espejo del bucket MinIO)
│   ├── raw/
│   ├── clean/
│   ├── processed/
│   └── curated/
└── docs/
    ├── ARCHITECTURE.md       # Descripción técnica de la arquitectura (Día 1)
    └── ARCHITECTURE_DIA2.md  # Extensión analítica (Día 2)