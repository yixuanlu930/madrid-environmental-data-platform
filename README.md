# Práctica 2 — Infraestructura Big Data ambiental para Madrid

Infraestructura completa de datos ambientales para el Ayuntamiento de Madrid. Recoge datos horarios de Open-Meteo, los almacena en un Data Lake por capas (MinIO), los orquesta con n8n y RabbitMQ, los carga en PostgreSQL y los visualiza con Apache Superset.

---

## 1. Objetivo

El sistema recupera datos del **día anterior** para Madrid (coordenadas `40.4168, -3.7038`), los almacena sin pérdida en un Data Lake por zonas, proporciona acceso SQL a través de PostgreSQL y expone dashboards accesibles para usuarios no técnicos mediante Apache Superset.

---

## 2. Arquitectura

```
Open-Meteo APIs (Weather + Air Quality)
         │
         ▼
  n8n — Madrid 1 - Ingesta (Schedule 07:00)
         │  Descarga datos, sube RAW a MinIO
         │  Publica 24 mensajes horarios en RabbitMQ
         ▼
  n8n — Madrid 2 - Preprocesamiento (RabbitMQ Trigger)
         │  Genera CSV clean (1 fila/hora) y processed (4 filas/hora)
         │  Sube a MinIO con estructura YYYY/MM/DD/
         ▼
  n8n — Madrid 3 - Analítica (Schedule 08:00)
         │  Lee 24 archivos de processed/ con Get many files (S3)
         │  Los agrupa en 1 CSV diario y sube a curated/
         ▼
  MinIO Data Lake (raw/ clean/ processed/ curated/)
         │
         ▼
  ETL Python — db_loader.py
         │  Carga datos de MinIO en PostgreSQL
         ▼
  PostgreSQL (esquema madrid_environment)
         │
         ▼
  Apache Superset (dashboards)

  Jupyter Lab (análisis exploratorio vía Python)
```

---

## 3. Componentes

| Componente | Imagen | Puerto | Función |
|---|---|---|---|
| `minio` | `minio/minio:latest` | 9000, 9001 | Data Lake compatible S3 |
| `minio-init` | `minio/mc:latest` | — | Crea el bucket al arrancar |
| `rabbitmq` | `rabbitmq:3-management` | 5672, 15672 | Cola de mensajes entre workflows |
| `etl` | Build local | 8000 | Ingesta Python, transformación y carga en PostgreSQL |
| `n8n` | `n8nio/n8n:latest` | 5678 | Orquestación de los 3 workflows |
| `n8n-init` | `n8nio/n8n:latest` | — | Importa los workflows automáticamente |
| `jupyter` | Build local | 8890 | Análisis exploratorio con Python |
| `postgres` | `postgres:16` | 5432 | Base de datos analítica con SQL |
| `superset` | `apache/superset:3.1.0` | 8088 | Dashboards para usuarios no técnicos |
| `superset-init` | `apache/superset:3.1.0` | — | Inicializa Superset y crea el usuario admin |
| Red `madrid-data-net` | bridge | — | Comunicación interna entre servicios |

---

## 4. Estructura del Data Lake (MinIO)

```
madrid-openmeteo-environment/
├── raw/
│   └── ingesta/date=YYYY-MM-DD/
│       └── raw_YYYY-MM-DD.json          ← JSON original de ambas APIs
├── clean/
│   └── environment_clean/YYYY/MM/DD/
│       └── HH_YYYYMMDD.csv              ← 1 fila por hora (formato wide)
├── processed/
│   └── environment_observations_long/YYYY/MM/DD/
│       └── HH_YYYYMMDD.csv              ← 4 filas por hora (formato largo)
└── curated/
    └── YYYY/MM/DD/
        └── YYYY_MM_DD.csv               ← 1 CSV diario con todas las horas
```

La organización por `YYYY/MM/DD/` permite operar a nivel de año, mes o día en los workflows de analítica.

---

## 5. Esquema PostgreSQL

Base de datos `madrid_env`, esquema `madrid_environment`:

| Tabla | Descripción | Filas/día |
|---|---|---|
| `environment_observations_long` | Observaciones horarias en formato largo (1 fila por variable/hora) | 96 |
| `hourly_environment_wide` | Tabla horaria wide con todas las variables en columnas | 24 |
| `daily_variable_summary` | Resumen diario con min/avg/max por variable | 4 |

---

## 6. Workflows de n8n

### Madrid 1 — Ingesta (Schedule 07:00)

```
Schedule Trigger + Manual Trigger
    → Code JS (calcula fecha de ayer, construye URLs)
    → HTTP Request Weather + HTTP Request Air Quality (en paralelo)
    → Merge
    → Code JS1 (empaqueta ambas respuestas)
    → Convert to File → Upload raw/ (MinIO)
    → Code JS3 (divide en 24 items horarios)
    → Code JS2 (prepara mensaje con records[])
    → RabbitMQ → cola madrid.preprocesamiento
```

### Madrid 2 — Preprocesamiento (RabbitMQ Trigger)

```
RabbitMQ Trigger (cola madrid.preprocesamiento)
    → Code JS (parsea mensaje, expande 24 records)
    → Build Clean CSV (1 hora → 1 fila wide) + Build Processed CSV (1 hora → 4 filas largo)
    → Upload Clean (clean/YYYY/MM/DD/HH_YYYYMMDD.csv)
    → Upload Processed (processed/YYYY/MM/DD/HH_YYYYMMDD.csv)
```

### Madrid 3 — Analítica (Schedule 08:00)

```
Schedule Trigger + Manual Trigger
    → Build Download URLs (calcula fecha de ayer, construye prefix)
    → Get many files S3 (lista 24 archivos de processed/YYYY/MM/DD/)
    → Download a file S3 (descarga cada archivo)
    → Merge and Build Curated (agrupa 24 CSVs en 1 tabla diaria)
    → Upload Curated to MinIO (curated/YYYY/MM/DD/YYYY_MM_DD.csv)
```

---

## 7. Puesta en marcha

### Prerrequisitos

- Docker y Docker Compose instalados
- Puertos libres: 8000, 5432, 5672, 5678, 8088, 8890, 9000, 9001, 15672

### Paso 1 — Configuración del entorno

```bash
cp .env.example .env
```

Los valores por defecto funcionan sin ningún cambio adicional.

### Paso 2 — Arrancar todos los servicios

```bash
docker compose up --build
```

Al arrancar ocurre automáticamente:
1. MinIO inicia con healthcheck
2. `minio-init` crea el bucket `madrid-openmeteo-environment`
3. RabbitMQ inicia con healthcheck
4. PostgreSQL inicia y ejecuta `init_postgres.sql` (crea esquema y tablas)
5. El servicio ETL arranca
6. n8n arranca y `n8n-init` importa los 3 workflows
7. Superset inicia y `superset-init` crea el usuario admin

Verifica que todos los servicios están en marcha:

```bash
docker compose ps
```

### Paso 3 — Crear colas en RabbitMQ ⚠️ PASO MANUAL

Abre `http://localhost:15672` → credenciales `admin / admin` → **Queues** → **Add a new queue**:

- Nombre: `madrid.preprocesamiento` → **Add queue**
- Nombre: `madrid.analitica` → **Add queue**

### Paso 4 — Configurar credenciales en n8n ⚠️ PASO MANUAL

Abre `http://localhost:5678` → **Credentials** → **Add credential**:

**Credencial S3 (MinIO):**
```
Name:             S3 account
Endpoint:         http://minio:9000
Region:           us-east-1
Access Key ID:    minioadmin
Secret Access Key: minioadmin
Force Path Style: ✅ activado
```

**Credencial RabbitMQ:**
```
Name:      RabbitMQ account
Hostname:  rabbitmq
Port:      5672
Username:  admin
Password:  admin
Vhost:     /
```

Asigna la credencial S3 a todos los nodos S3 de los 3 workflows, y la credencial RabbitMQ a los nodos RabbitMQ.

### Paso 5 — Publicar y activar los workflows ⚠️ PASO MANUAL

En n8n (`http://localhost:5678`), para cada workflow:
1. Abre el workflow
2. Pulsa **Publish** (botón azul arriba a la derecha)
3. Activa el toggle **Active**

### Paso 6 — Conectar Superset a PostgreSQL ⚠️ PASO MANUAL

1. Abre `http://localhost:8088` → credenciales `admin / admin`
2. Ve a **Settings** → **Database Connections** → **+ Database**
3. Selecciona **PostgreSQL** y rellena:
```
Host:     postgres
Port:     5432
Database: madrid_env
Username: madrid
Password: madrid
```
4. Pulsa **Test Connection** y luego **Connect**

---

## 8. URLs de acceso

| Servicio | URL | Credenciales |
|---|---|---|
| ETL healthcheck | `http://localhost:8000/health` | — |
| MinIO Console | `http://localhost:9001` | `minioadmin / minioadmin` |
| RabbitMQ Management | `http://localhost:15672` | `admin / admin` |
| n8n | `http://localhost:5678` | (crear en primer acceso) |
| Jupyter Lab | `http://localhost:8890` | (sin token) |
| PostgreSQL | `localhost:5432` | `madrid / madrid` |
| Superset | `http://localhost:8088` | `admin / admin` |

---

## 9. Ejecutar el pipeline manualmente

### Opción A — desde n8n

Abre `http://localhost:5678` → **Madrid 1 - Ingesta** → pulsa **Test workflow**.

El flujo completo encadenado es:
1. Ingesta descarga las APIs → sube a `raw/` → publica en RabbitMQ
2. Preprocesamiento se dispara automáticamente → sube 24 archivos a `clean/` y `processed/`
3. A las 08:00 (o manualmente) Analítica lee `processed/` → genera `curated/`

### Opción B — desde el ETL Python

```bash
# Ejecuta el pipeline completo para ayer
curl -X POST "http://localhost:8000/run"

# Para una fecha específica
curl -X POST "http://localhost:8000/run?date=2026-05-12"
```

### Cargar datos en PostgreSQL

```bash
docker compose exec etl python src/db_loader.py
```

---

## 10. Validación de outputs

```bash
docker compose exec etl python src/validate_outputs.py
```

Salida esperada:
```
[OK] raw/.../raw_YYYY-MM-DD.json
[OK] clean/.../weather_hourly.csv rows=24
[OK] clean/.../air_quality_hourly.csv rows=24
[OK] processed/.../environment_observations_long.csv rows=96
[OK] curated/.../hourly_environment_wide.csv rows=24
[OK] curated/.../daily_variable_summary.csv rows=4
```

---

## 11. Análisis en Jupyter

Abre `http://localhost:8890` y ejecuta el notebook `notebooks/analyze_curated_data.ipynb`.

Lee directamente desde MinIO los datos de `curated/` y permite:
- Visualización de series temporales
- Análisis de correlación entre variables ambientales
- Consultas SQL contra PostgreSQL

---

## 12. Comandos útiles

```bash
# Ver estado de los servicios
docker compose ps

# Ver logs en tiempo real
docker compose logs -f etl
docker compose logs -f n8n
docker compose logs -f rabbitmq

# Parar servicios (conserva datos)
docker compose down

# Parar y eliminar todos los datos persistidos
docker compose down -v

# Reimportar workflows de n8n
docker compose exec n8n n8n import:workflow --input=/workflows/madrid_ingesta.json
docker compose exec n8n n8n import:workflow --input=/workflows/madrid_preprocesamiento.json
docker compose exec n8n n8n import:workflow --input=/workflows/madrid_analitica.json
```

---

## 13. Estructura del repositorio

```
.
├── docker-compose.yml              # Definición de todos los servicios
├── Dockerfile                      # Imagen compartida por etl y jupyter
├── requirements.txt                # Dependencias Python
├── .env.example                    # Plantilla de variables de entorno
├── .env                            # Variables activas (NO subir a git)
├── src/
│   ├── config.py                   # Configuración centralizada
│   ├── sources.py                  # Llamadas a las APIs de Open-Meteo
│   ├── transform.py                # Transformaciones raw → clean → processed → curated
│   ├── storage.py                  # Carga de archivos en MinIO
│   ├── pipeline.py                 # Orquestación del flujo ETL Python
│   ├── server.py                   # Servidor HTTP (/run, /health, /ingest, /preprocess, /analytics)
│   ├── db_loader.py                # Carga de datos de MinIO a PostgreSQL
│   ├── utils.py                    # Utilidades (CSV, JSON, lectura de ficheros)
│   └── validate_outputs.py         # Validación de outputs generados
├── n8n/workflows/
│   ├── madrid_ingesta.json         # Workflow 1: descarga APIs → RAW → RabbitMQ
│   ├── madrid_preprocesamiento.json # Workflow 2: RabbitMQ → clean/ + processed/
│   └── madrid_analitica.json       # Workflow 3: processed/ → curated/
├── postgres/
│   └── init_postgres.sql           # Esquema y tablas (se ejecuta automáticamente)
├── superset/
│   ├── superset_config.py          # Configuración de Superset
│   └── superset_init.sh            # Script de inicialización (usuario admin)
├── notebooks/
│   └── analyze_curated_data.ipynb  # Notebook de análisis exploratorio
├── data/                           # Data Lake local (espejo de MinIO)
│   ├── raw/
│   ├── clean/
│   ├── processed/
│   └── curated/
└── docs/
    ├── ARCHITECTURE.md             # Arquitectura del Día 1
    └── ARCHITECTURE_DIA2.md        # Arquitectura del Día 2
```