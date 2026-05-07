
# Práctica 2 — Infraestructura Big Data ambiental para Madrid con Open-Meteo

Esta práctica implementa una infraestructura de datos para analizar variables ambientales de Madrid usando únicamente APIs de Open-Meteo.

## 1. Objetivo

La infraestructura recupera datos horarios del día anterior para Madrid, los almacena sin pérdida, genera versiones transformadas y produce una versión final preparada para análisis desde Jupyter.

Coordenadas usadas:

```text
latitude=40.4168
longitude=-3.7038
timezone=Europe/Madrid
```

## 2. Fuentes de datos

Se usan dos fuentes de datos distintas, entendidas como dos APIs distintas de Open-Meteo:

| Fuente | URL base | Variables |
|---|---|---|
| Historical Weather API | `https://archive-api.open-meteo.com/v1/archive` | `temperature_2m`, `precipitation` |
| Air Quality API | `https://air-quality-api.open-meteo.com/v1/air-quality` | `ozone`, `carbon_dioxide` |

Cada API se consulta para el día anterior con resolución horaria. La salida esperada es:

- 24 filas horarias de meteorología.
- 24 filas horarias de calidad del aire.
- 96 observaciones en formato largo: 24 horas × 4 variables.
- 24 filas en la tabla analítica final.

## 3. Arquitectura

```text
n8n
  │
  │ POST http://etl:8000/run
  ▼
Servicio ETL Python
  ├── Historical Weather API
  ├── Air Quality API
  ├── RAW: JSON originales
  ├── CLEAN: CSV limpios por API
  ├── PROCESSED: tabla larga unificada
  └── CURATED: tabla ancha optimizada para análisis
  │
  ▼
MinIO Data Lake
  ▲
  │
Jupyter conectado a la red Docker
```

Importante: en n8n el nodo `HTTP Request` llama al servicio interno:

```text
http://etl:8000/run
```

No se ponen directamente las URLs de Open-Meteo en n8n, porque el ETL Python se encarga de llamar a las APIs, guardar RAW/CLEAN/PROCESSED/CURATED y subir los resultados a MinIO.

## 4. Componentes

| Componente | Función |
|---|---|
| Docker Compose | Despliegue completo |
| n8n | Orquestación del flujo periódico |
| ETL Python | Ingesta, transformación y carga |
| MinIO | Data Lake persistente tipo S3 |
| Jupyter Lab | Entorno de programación conectado a la red Docker |
| Docker network | Comunicación interna entre servicios |
| Docker volumes | Persistencia de MinIO y n8n |

## 5. Estructura del Data Lake

```text
data/
├── raw/
│   ├── open_meteo_historical_weather/
│   └── open_meteo_air_quality/
├── clean/
│   ├── historical_weather_hourly/
│   └── air_quality_hourly/
├── processed/
│   ├── environment_observations_long/
│   └── manifests/
└── curated/
    ├── hourly_environment_wide/
    └── daily_variable_summary/
```

## 6. Puesta en marcha

```bash
cp .env.example .env
docker compose up --build
```

Servicios:

```text
ETL:        http://localhost:8000/health
n8n:        http://localhost:5678
MinIO:      http://localhost:9001
Jupyter:    http://localhost:8888
```

Credenciales de MinIO:

```text
minioadmin / minioadmin
```

## 7. Ejecutar el pipeline

Por defecto recupera el día anterior según la zona horaria de Madrid:

```bash
curl -X POST "http://localhost:8000/run"
```

Para una fecha concreta:

```bash
curl -X POST "http://localhost:8000/run?date=2026-05-05"
```

## 8. Validación

```bash
docker compose exec etl python src/validate_outputs.py --date 2026-05-05
```

Salida esperada:

```text
[OK] raw/open_meteo_historical_weather/.../weather.json
[OK] raw/open_meteo_air_quality/.../air_quality.json
[OK] clean/historical_weather_hourly/... rows=24
[OK] clean/air_quality_hourly/... rows=24
[OK] processed/environment_observations_long/... rows=96
[OK] curated/hourly_environment_wide/... rows=24
[OK] curated/daily_variable_summary/... rows=4
[OK] processed/manifests/.../manifest.json
```

## 9. n8n

Importar workflow:

```bash
docker compose exec n8n n8n import:workflow --input=/workflows/madrid_environment_daily.json
```

Abrir n8n:

```text
http://localhost:5678
```

El workflow contiene tres nodos:

- `Daily Schedule 07:00`
- `Manual Trigger`
- `Run ETL service`

El nodo `Run ETL service` hace:

```text
POST http://etl:8000/run
```

## 10. Jupyter

Abrir:

```text
http://localhost:8888
```

Notebook incluido:

```text
notebooks/analyze_curated_data.ipynb
```

Este notebook lee desde MinIO usando el endpoint interno:

```text
minio:9000
```

y carga la tabla final:

```text
curated/hourly_environment_wide/date=YYYY-MM-DD/hourly_environment_wide.csv
```

Esa tabla es la versión preparada y optimizada para procesamiento analítico desde entornos de programación.

## 11. Comandos útiles

Ver servicios:

```bash
docker compose ps
```

Ver logs:

```bash
docker compose logs -f etl
docker compose logs -f n8n
docker compose logs -f jupyter
```

Parar:

```bash
docker compose down
```

Parar y borrar volúmenes:

```bash
docker compose down -v
```
