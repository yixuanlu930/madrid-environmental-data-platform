# Madrid Environmental Data Platform

An end-to-end **environmental data engineering platform for Madrid** that automatically ingests weather and air-quality data, processes it through a layered Data Lake, loads analytical datasets into PostgreSQL, and exposes them through Jupyter Lab and Apache Superset.

The platform combines **Python, Open-Meteo, MinIO, n8n, RabbitMQ, PostgreSQL, Apache Superset, Jupyter, and Docker Compose** in a reproducible Big Data infrastructure.

## Overview

The objective of the project is to build a complete data pipeline capable of retrieving environmental information for Madrid, transforming it into analysis-ready datasets, storing it in multiple formats, and exposing it to both technical and non-technical users.

The system retrieves hourly data for the previous day using two Open-Meteo APIs:

* Historical Weather API
* Air Quality API

The data is processed through four Data Lake layers:

```text
RAW → CLEAN → PROCESSED → CURATED
```

The final datasets are also loaded into PostgreSQL for SQL analysis and visualization through Apache Superset.

---

## Architecture

```text
                ┌──────────────────────────┐
                │      Open-Meteo APIs     │
                │                          │
                │ Historical Weather       │
                │ Air Quality              │
                └────────────┬─────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │       n8n       │
                    │  Orchestration  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Python ETL    │
                    │    Service      │
                    └───────┬─────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
     ┌──────────────────┐       ┌──────────────────┐
     │      MinIO       │       │    PostgreSQL    │
     │    Data Lake     │       │ Analytical Layer │
     │                  │       │                  │
     │ raw              │       │ Long table       │
     │ clean            │       │ Hourly wide      │
     │ processed        │       │ Daily summary    │
     │ curated          │       │                  │
     └────────┬─────────┘       └────────┬─────────┘
              │                          │
              ▼                          ▼
        ┌────────────┐             ┌───────────────┐
        │  Jupyter   │             │    Superset   │
        │    Lab     │             │      BI       │
        └────────────┘             └───────────────┘

              RabbitMQ
                  │
                  ▼
       Event-based communication
```

All services run inside the same Docker network.

---

## Data Sources

The platform uses two Open-Meteo APIs.

### Historical Weather API

Variables:

```text
temperature_2m
precipitation
```

### Air Quality API

Variables:

```text
ozone
carbon_dioxide
```

The default geographic configuration corresponds to Madrid:

```text
Latitude:  40.4168
Longitude: -3.7038
Timezone:  Europe/Madrid
```

The pipeline retrieves data with hourly resolution.

For each day, the expected output includes:

```text
24 weather observations
24 air-quality observations
96 long-format observations
24 rows in the analytical wide table
4 daily variable summaries
```

---

# Data Lake Architecture

MinIO provides an S3-compatible Data Lake organized into four logical layers.

```text
madrid-openmeteo-environment/
│
├── raw/
│
├── clean/
│
├── processed/
│
└── curated/
```

## RAW

Stores the original API responses without modification.

Example:

```text
raw/
├── open_meteo_historical_weather/
│   └── date=YYYY-MM-DD/
│       └── weather.json
│
└── open_meteo_air_quality/
    └── date=YYYY-MM-DD/
        └── air_quality.json
```

The RAW layer preserves the original source data and makes the pipeline reproducible.

---

## CLEAN

Stores normalized hourly CSV datasets.

```text
clean/
├── historical_weather_hourly/
│   └── date=YYYY-MM-DD/
│       └── weather_hourly.csv
│
└── air_quality_hourly/
    └── date=YYYY-MM-DD/
        └── air_quality_hourly.csv
```

Each dataset contains approximately:

```text
24 rows/day
```

---

## PROCESSED

The two sources are unified into a long analytical format.

```text
processed/
└── environment_observations_long/
    └── date=YYYY-MM-DD/
        └── environment_observations_long.csv
```

Each row represents:

```text
one variable
×
one hour
```

With four monitored variables and 24 hours:

```text
24 × 4 = 96 observations/day
```

The project also generates processing manifests that record pipeline execution and output information.

---

## CURATED

The curated layer contains datasets optimized for analysis.

### Hourly Wide Table

```text
curated/
└── hourly_environment_wide/
    └── date=YYYY-MM-DD/
        └── hourly_environment_wide.csv
```

The table contains one row per hour with columns such as:

```text
time
temperature_2m
precipitation
ozone
carbon_dioxide
```

### Daily Variable Summary

```text
curated/
└── daily_variable_summary/
    └── date=YYYY-MM-DD/
        └── daily_variable_summary.csv
```

For each variable, the system calculates:

* Number of observations
* Minimum
* Average
* Maximum

---

# Hive-Style Partitioning

Datasets are organized using date-based partitions such as:

```text
date=2026-05-12
```

This organization improves maintainability and makes it easier to query or process data by date.

---

# ETL Pipeline

The Python ETL service contains three main stages.

## Stage 1 — Ingestion

The ingestion process:

1. Calls the Open-Meteo Historical Weather API.
2. Calls the Open-Meteo Air Quality API.
3. Retrieves hourly environmental data.
4. Preserves the raw JSON responses.
5. Stores the results in MinIO.

Endpoint:

```http
POST /ingest
```

---

## Stage 2 — Preprocessing

The preprocessing stage:

1. Reads RAW data.
2. Converts API responses into normalized CSV files.
3. Builds clean weather and air-quality datasets.
4. Converts the data into a unified long representation.
5. Stores CLEAN and PROCESSED data in MinIO.
6. Loads processed observations into PostgreSQL.

Endpoint:

```http
POST /preprocess
```

---

## Stage 3 — Analytics

The analytical stage:

1. Reads curated intermediate data.
2. Converts long-format observations into a wide table.
3. Calculates daily summary statistics.
4. Stores CURATED datasets in MinIO.
5. Loads analytical datasets into PostgreSQL.

Endpoint:

```http
POST /analytics
```

---

## Full Pipeline

All stages can also be executed sequentially:

```http
POST /run
```

---

# PostgreSQL Analytical Layer

The PostgreSQL database uses the schema:

```text
madrid_environment
```

It contains three analytical tables.

## `environment_observations_long`

Long-format environmental observations.

Typical volume:

```text
96 rows/day
```

Useful for:

* Variable filtering
* Exploratory analysis
* Flexible aggregations

---

## `hourly_environment_wide`

Wide analytical table containing:

```text
temperature_2m
precipitation
ozone
carbon_dioxide
```

Typical volume:

```text
24 rows/day
```

This table is optimized for time-series analysis.

---

## `daily_variable_summary`

Contains daily statistics for every environmental variable.

Fields include:

```text
date
source
dataset
variable
unit
observations
min_value
avg_value
max_value
```

This table is particularly suitable for BI dashboards.

---

# Workflow Orchestration with n8n

The project includes three n8n workflows:

```text
madrid_ingesta
madrid_preprocesamiento
madrid_analitica
```

They are stored in:

```text
n8n/workflows/
```

n8n is responsible for orchestrating the different stages of the environmental data pipeline.

The workflows can be imported automatically when the infrastructure starts.

---

# RabbitMQ

RabbitMQ is included as the message broker for event-driven communication between components.

The management interface can be used to inspect:

* Queues
* Messages
* Connections
* Exchanges

RabbitMQ provides a foundation for decoupling pipeline stages and supporting more scalable asynchronous processing.

---

# Apache Superset

Apache Superset provides the Business Intelligence layer.

It connects directly to PostgreSQL and can be used to create dashboards for:

* Environmental trends
* Daily averages
* Maximum and minimum values
* Air-quality evolution
* Temperature analysis
* Precipitation analysis

This allows non-technical users to explore the processed datasets through interactive dashboards.

---

# Jupyter Lab

Jupyter Lab is included for exploratory data analysis.

The repository contains:

```text
notebooks/analyze_curated_data.ipynb
```

The notebook can:

* Read curated data
* Access MinIO
* Query PostgreSQL
* Analyze time series
* Study correlations between environmental variables
* Produce exploratory visualizations

---

# Infrastructure Components

| Component       | Purpose                      |
| --------------- | ---------------------------- |
| Open-Meteo      | Environmental data source    |
| Python ETL      | Ingestion and transformation |
| MinIO           | S3-compatible Data Lake      |
| n8n             | Workflow orchestration       |
| RabbitMQ        | Message broker               |
| PostgreSQL      | Analytical SQL database      |
| Apache Superset | BI dashboards                |
| Jupyter Lab     | Exploratory data analysis    |
| Docker          | Containerization             |
| Docker Compose  | Multi-service orchestration  |

---

# Project Structure

```text
madrid-environmental-data-platform/
│
├── src/
│   ├── server.py
│   ├── pipeline.py
│   ├── transform.py
│   ├── sources.py
│   ├── storage.py
│   ├── db_loader.py
│   ├── validate_outputs.py
│   ├── config.py
│   └── utils.py
│
├── n8n/
│   └── workflows/
│       ├── madrid_ingesta.json
│       ├── madrid_preprocesamiento.json
│       └── madrid_analitica.json
│
├── postgres/
│   └── init_postgres.sql
│
├── superset/
│   ├── superset_config.py
│   └── superset_init.sh
│
├── notebooks/
│   └── analyze_curated_data.ipynb
│
├── data/
│   ├── raw/
│   ├── clean/
│   ├── processed/
│   └── curated/
│
├── docs/
│   ├── ARCHITECTURE.md
│   └── ARCHITECTURE_DIA2.md
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# Running the Platform

## Requirements

Install:

* Docker
* Docker Compose

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/madrid-environmental-data-platform.git
cd madrid-environmental-data-platform
```

---

## Configure Environment Variables

Create the local environment file:

```bash
cp .env.example .env
```

The default development configuration contains settings for:

* Madrid coordinates
* Open-Meteo endpoints
* MinIO
* RabbitMQ
* PostgreSQL
* Superset

Never commit `.env` files containing production credentials.

---

## Start the Infrastructure

Run:

```bash
docker compose up --build
```

To run in the background:

```bash
docker compose up --build -d
```

Check all services:

```bash
docker compose ps
```

---

# Service URLs

| Service             | URL                      |
| ------------------- | ------------------------ |
| ETL API             | `http://localhost:8000`  |
| n8n                 | `http://localhost:5678`  |
| MinIO Console       | `http://localhost:9001`  |
| RabbitMQ Management | `http://localhost:15672` |
| Jupyter Lab         | `http://localhost:8890`  |
| Apache Superset     | `http://localhost:8088`  |
| PostgreSQL          | `localhost:5432`         |

---

# Running the Pipeline Manually

Execute all stages:

```bash
curl -X POST "http://localhost:8000/run"
```

For a specific date:

```bash
curl -X POST "http://localhost:8000/run?date=2026-05-12"
```

Individual stages can also be executed:

```bash
curl -X POST "http://localhost:8000/ingest"
curl -X POST "http://localhost:8000/preprocess"
curl -X POST "http://localhost:8000/analytics"
```

---

# Validate Pipeline Outputs

Run:

```bash
docker compose exec etl python src/validate_outputs.py
```

The validation process checks that the expected RAW, CLEAN, PROCESSED and CURATED files were generated correctly.

---

# Useful Docker Commands

Check service status:

```bash
docker compose ps
```

Follow ETL logs:

```bash
docker compose logs -f etl
```

Follow n8n logs:

```bash
docker compose logs -f n8n
```

Follow RabbitMQ logs:

```bash
docker compose logs -f rabbitmq
```

Stop the infrastructure:

```bash
docker compose down
```

Remove containers and persistent volumes:

```bash
docker compose down -v
```

---

# Technologies

## Data Engineering

* Python
* Pandas
* ETL pipelines
* Data Lake architecture
* Hive-style partitioning

## Data Storage

* MinIO
* PostgreSQL
* S3-compatible object storage

## Workflow & Messaging

* n8n
* RabbitMQ

## Analytics

* Jupyter Lab
* Apache Superset

## Infrastructure

* Docker
* Docker Compose

## Data Source

* Open-Meteo Historical Weather API
* Open-Meteo Air Quality API

---

# Key Concepts

This project demonstrates concepts including:

* Big Data infrastructure
* Data engineering
* ETL
* Data Lakes
* Layered data architectures
* RAW / CLEAN / PROCESSED / CURATED pipelines
* Object storage
* Workflow orchestration
* Event-driven architectures
* Message brokers
* Relational analytical databases
* Data validation
* SQL analytics
* Business Intelligence
* Containerized infrastructures

---

# Potential Extensions

Possible future improvements include:

* Apache Airflow orchestration
* Apache Spark processing
* Kafka-based event streaming
* Additional environmental APIs
* Historical trend analysis
* Automated anomaly detection
* Data quality monitoring
* Alerting systems
* Additional Madrid environmental variables
* Cloud deployment
* Infrastructure-as-Code
* Automated Superset dashboard provisioning

---

# Academic Context

This project was developed as part of a **Big Data Infrastructures** laboratory project.

Its purpose is to demonstrate the design and deployment of an end-to-end data engineering architecture combining ingestion, storage, processing, orchestration, messaging, analytical databases, and visualization.

---

# License

See the repository license for applicable terms.




## Spanish Translation
## Infraestructura Big Data ambiental para Madrid

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
