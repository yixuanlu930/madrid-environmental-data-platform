# Práctica 2 — Infraestructura Big Data ambiental para Madrid

Infraestructura de datos para analizar variables ambientales de Madrid usando dos APIs de Open-Meteo, orquestada con **n8n**, almacenada en **MinIO** (Data Lake por capas), con colas de mensajes en **RabbitMQ**, consultable mediante **PostgreSQL** y visualizable desde **Apache Superset** y **Jupyter Lab**.

---

## 1. Objetivo

La infraestructura recupera datos horarios del **día anterior** para Madrid, los almacena en un Data Lake organizado por capas y fechas (raw → clean → processed → curated), y produce tablas agregadas optimizadas para análisis.

Coordenadas usadas:
```
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

Cada API se consulta para el día anterior con resolución horaria (24 registros por variable).

---

## 3. Arquitectura

```
                    ┌─────────────────────────────────────┐
                    │         n8n (orquestador)            │
                    │                                     │
                    │  Madrid 1 - Ingesta  (07:00)        │
                    │  Madrid 2 - Preprocesamiento        │
                    │  Madrid 3 - Analítica   (08:00)     │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
      Open-Meteo APIs        RabbitMQ               MinIO
    (Weather + Air Quality)  (cola mensajes)     (Data Lake S3)
```

### Flujo de datos

```
Ingesta ──→ llama a 2 APIs ──→ guarda JSON RAW en MinIO
        ──→ publica 1 mensaje en RabbitMQ (con 24 registros horarios)

Preprocesamiento ──→ consume mensaje de RabbitMQ
                 ──→ genera 24 CSVs clean  (YYYY/MM/DD/HH_YYYYMMDD.csv)
                 ──→ genera 24 CSVs processed en formato largo
                 ──→ sube todos a MinIO

Analítica ──→ descarga los 24 CSVs processed del día anterior
          ──→ los une en un único CSV curated con todas las medidas
          ──→ sube el CSV curated a MinIO
```

---

## 4. Estructura del Data Lake en MinIO

```
madrid-openmeteo-environment/
│
├── raw/
│   ├── open_meteo_historical_weather/
│   │   └── YYYY/MM/DD/
│   │       └── weather_YYYY-MM-DD.json        ← respuesta original de la API
│   └── open_meteo_air_quality/
│       └── YYYY/MM/DD/
│           └── air_quality_YYYY-MM-DD.json    ← respuesta original de la API
│
├── clean/
│   └── environment_clean/
│       └── YYYY/MM/DD/
│           ├── 00_YYYYMMDD.csv                ← hora 00 (1 fila, campos seleccionados)
│           ├── 01_YYYYMMDD.csv
│           └── ...  (24 ficheros por día)
│
├── processed/
│   └── environment_observations_long/
│       └── YYYY/MM/DD/
│           ├── 00_YYYYMMDD.csv                ← hora 00 (4 filas, formato largo)
│           └── ...  (24 ficheros por día)
│
└── curated/
    └── daily_summary/
        └── YYYY/MM/DD/
            └── YYYY_MM_DD.csv                 ← todas las medidas del día (96 filas)
```

---

## 5. Componentes

| Componente | Imagen | Función |
|---|---|---|
| `minio` | `minio/minio:latest` | Data Lake persistente tipo S3 |
| `minio-init` | `minio/mc:latest` | Crea el bucket al arrancar |
| `rabbitmq` | `rabbitmq:3-management` | Cola de mensajes entre Ingesta y Preprocesamiento |
| `n8n` | `n8nio/n8n:latest` | Orquestación de los tres workflows |
| `n8n-init` | `n8nio/n8n:latest` | Importa los workflows automáticamente al arrancar |
| `postgres` | `postgres:16` | Base de datos relacional |
| `superset` | `apache/superset:3.1.0` | Dashboards e interfaz BI |
| `jupyter` | Build local | Entorno de análisis Python |

---

## 6. Puesta en marcha

### Prerrequisitos

- Docker y Docker Compose instalados
- Puertos libres: 5432, 5672, 5678, 8088, 8890, 9000, 9001, 15672

### Paso 1 — Configuración del entorno

```bash
cp .env.example .env
```

Los valores por defecto funcionan sin ningún cambio adicional.

### Paso 2 — Arrancar los servicios

```bash
docker compose up -d
```

Verifica que todos los contenedores están corriendo:

```bash
docker compose ps
```

Espera a que MinIO, RabbitMQ y PostgreSQL aparezcan como `healthy` (puede tardar 1-2 minutos).

### Paso 3 — Importar los workflows en n8n

```bash
docker exec madrid-n8n n8n import:workflow --input=/workflows/madrid_ingesta.json
docker exec madrid-n8n n8n import:workflow --input=/workflows/madrid_preprocesamiento.json
docker exec madrid-n8n n8n import:workflow --input=/workflows/madrid_analitica.json
```

### Paso 4 — Configurar credenciales en n8n

Abre **http://localhost:5678/credentials** y crea las siguientes credenciales:

**S3 account** (MinIO):
- Type: S3
- Region: `us-east-1`
- Access Key ID: `minioadmin`
- Secret Access Key: `minioadmin`
- Endpoint: `http://minio:9000`
- Force path style: `true`

**RabbitMQ account**:
- Type: RabbitMQ
- Hostname: `rabbitmq`
- Port: `5672`
- Username: `admin`
- Password: `admin`

### Paso 5 — Crear la cola en RabbitMQ

Abre **http://localhost:15672** (admin/admin) → pestaña **Queues** → **Add a new queue**:
- Name: `madrid.preprocesamiento`
- El resto por defecto → **Add queue**

### Paso 6 — Actualizar IDs de credenciales en los workflows

Obtén los IDs de las credenciales que acabas de crear:

```bash
docker exec madrid-n8n n8n export:credentials --all
```

Anota el `id` de cada credencial y actualiza los workflows (sustituye `<ID_S3>` y `<ID_RABBITMQ>` por los valores reales):

```bash
# Actualizar ID de S3 en todos los workflows
sed -i 's/pN1COipp7gzYPtMJ/<ID_S3>/g' n8n/workflows/madrid_ingesta.json
sed -i 's/pN1COipp7gzYPtMJ/<ID_S3>/g' n8n/workflows/madrid_analitica.json
sed -i 's/qGDH8h0N1oyPecQp/<ID_S3>/g' n8n/workflows/madrid_preprocesamiento.json

# Actualizar ID de RabbitMQ
sed -i 's/vKJqd216F9wwwBZ7/<ID_RABBITMQ>/g' n8n/workflows/madrid_ingesta.json
sed -i 's/D3oqUhSY9y9HTByc/<ID_RABBITMQ>/g' n8n/workflows/madrid_preprocesamiento.json

# Reimportar los workflows actualizados
docker exec madrid-n8n n8n import:workflow --input=/workflows/madrid_ingesta.json
docker exec madrid-n8n n8n import:workflow --input=/workflows/madrid_preprocesamiento.json
docker exec madrid-n8n n8n import:workflow --input=/workflows/madrid_analitica.json
```

---

## 7. Ejecución del pipeline

Ejecuta los workflows en este orden desde **http://localhost:5678**:

### 1. Madrid 1 - Ingesta
- Abre el workflow → botón **Execute workflow**
- Llama a las dos APIs de Open-Meteo
- Guarda los JSONs originales en MinIO (`raw/`)
- Publica 1 mensaje en RabbitMQ con los 24 registros horarios

**Verificar:** En RabbitMQ (http://localhost:15672) → Queues → `madrid.preprocesamiento` debe mostrar **1 mensaje**.

### 2. Madrid 2 - Preprocesamiento
- Abre el workflow → botón **Execute workflow**
- Consume el mensaje de RabbitMQ
- Genera 24 ficheros CSV clean y 24 processed (uno por hora)
- Los sube a MinIO con la estructura `YYYY/MM/DD/HH_YYYYMMDD.csv`

**Verificar:** En MinIO (http://localhost:9001 — minioadmin/minioadmin) deben aparecer 24 ficheros en `clean/environment_clean/YYYY/MM/DD/` y otros 24 en `processed/environment_observations_long/YYYY/MM/DD/`.

### 3. Madrid 3 - Analítica
- Abre el workflow → botón **Execute workflow**
- Descarga los 24 CSVs processed del día anterior
- Los une en un único CSV curated (96 filas: 24h × 4 variables)
- Sube el CSV a MinIO

**Verificar:** En MinIO debe aparecer el fichero `curated/daily_summary/YYYY/MM/DD/YYYY_MM_DD.csv` con 97 líneas (1 cabecera + 96 datos).

---

## 8. URLs de acceso

| Servicio | URL | Credenciales |
|---|---|---|
| n8n | http://localhost:5678 | (ninguna por defecto) |
| MinIO Console | http://localhost:9001 | `minioadmin / minioadmin` |
| RabbitMQ Management | http://localhost:15672 | `admin / admin` |
| Jupyter Lab | http://localhost:8890 | (sin token) |
| PostgreSQL | localhost:5432 | `madrid / madrid` |
| Superset | http://localhost:8088 | `admin / admin` |

---

## 9. Workflows n8n

| Workflow | Trigger | Descripción |
|---|---|---|
| `Madrid 1 - Ingesta` | Schedule 07:00 / manual | Llama a APIs, guarda RAW, publica en RabbitMQ |
| `Madrid 2 - Preprocesamiento` | RabbitMQ Trigger / manual | Genera 24 CSVs clean y 24 processed por día |
| `Madrid 3 - Analítica` | Schedule 08:00 / manual | Agrupa los 24 CSVs en un único curated diario |

---

## 10. Comandos útiles

```bash
# Ver estado de los servicios
docker compose ps

# Ver logs en tiempo real
docker compose logs -f n8n
docker compose logs -f rabbitmq

# Listar ficheros generados en MinIO
docker exec madrid-minio mc ls --recursive local/madrid-openmeteo-environment/

# Listar ficheros por zona
docker exec madrid-minio mc ls --recursive local/madrid-openmeteo-environment/raw/
docker exec madrid-minio mc ls --recursive local/madrid-openmeteo-environment/clean/
docker exec madrid-minio mc ls --recursive local/madrid-openmeteo-environment/processed/
docker exec madrid-minio mc ls --recursive local/madrid-openmeteo-environment/curated/

# Ver contenido de un fichero CSV en MinIO
docker exec madrid-minio mc cat "local/madrid-openmeteo-environment/curated/daily_summary/YYYY/MM/DD/YYYY_MM_DD.csv"

# Parar servicios (conserva volúmenes y datos)
docker compose down

# Parar y eliminar todos los datos persistidos
docker compose down -v
```

---

## 11. Estructura del repositorio

```
.
├── docker-compose.yml                # Definición de todos los servicios
├── Dockerfile                        # Imagen compartida por etl y jupyter
├── requirements.txt                  # Dependencias Python
├── .env.example                      # Plantilla de variables de entorno
├── .env                              # Variables de entorno activas (NO subir a git)
├── n8n/workflows/
│   ├── madrid_ingesta.json           # Workflow de ingesta
│   ├── madrid_preprocesamiento.json  # Workflow de preprocesamiento
│   └── madrid_analitica.json         # Workflow de analítica
├── postgres/
│   └── init_postgres.sql             # DDL del esquema
├── superset/
│   ├── superset_config.py
│   └── superset_init.sh
├── notebooks/
│   └── analyze_curated_data.ipynb   # Notebook de análisis
├── data/                            # Data Lake local
│   ├── raw/
│   ├── clean/
│   ├── processed/
│   └── curated/
└── docs/
    ├── ARCHITECTURE.md
    └── ARCHITECTURE_DIA2.md
```
