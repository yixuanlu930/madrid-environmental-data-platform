# Práctica 2 — Infraestructura Big Data ambiental para Madrid con Open-Meteo

Infraestructura de datos para analizar variables ambientales de Madrid usando dos APIs de Open-Meteo, orquestada con n8n, almacenada en MinIO y consumible desde Jupyter Lab.

---

## 1. Objetivo

La infraestructura recupera datos horarios del **día anterior** para Madrid, los almacena sin pérdida en un Data Lake por capas (raw → clean → processed → curated), y produce una tabla final optimizada para análisis desde Jupyter.

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
  │  POST http://etl:8000/run  (diario a las 07:00 Europe/Madrid)
  ▼
Servicio ETL Python (servidor HTTP interno)
  ├── Llama a Historical Weather API → guarda RAW JSON
  ├── Llama a Air Quality API       → guarda RAW JSON
  ├── Transforma a CLEAN CSV por API
  ├── Genera tabla PROCESSED (formato largo)
  └── Genera tablas CURATED (wide + resumen diario)
  │
  │  Sube todos los archivos vía SDK de MinIO
  ▼
MinIO Data Lake (compatible S3)
  ▲
  │  Lee vía endpoint interno minio:9000
Jupyter Lab
```

> El nodo n8n **no llama directamente** a las APIs de Open-Meteo. Delega toda la lógica al servicio ETL Python, que es quien hace las llamadas, las transformaciones y la carga en MinIO.

---

## 4. Componentes

| Componente | Imagen / Build | Función |
|---|---|---|
| `minio` | `minio/minio:latest` | Data Lake persistente tipo S3 |
| `minio-init` | `minio/mc:latest` | Crea el bucket al arrancar (espera healthcheck de MinIO) |
| `etl` | Build local (`Dockerfile`) | Ingesta, transformación y carga |
| `n8n` | `n8nio/n8n:latest` | Orquestación del flujo periódico |
| `n8n-init` | `n8nio/n8n:latest` | Importa el workflow automáticamente al arrancar |
| `jupyter` | Build local (`Dockerfile`) | Entorno de análisis |
| Red `madrid-data-net` | bridge | Comunicación interna entre servicios |
| Volumen `minio_data` | Docker volume | Persistencia del Data Lake |
| Volumen `n8n_data` | Docker volume | Persistencia de workflows y ejecuciones de n8n |

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

## 6. Puesta en marcha

### Prerrequisitos

- Docker y Docker Compose instalados
- Puertos libres: 8000, 5678, 9000, 9001, 8890

### Paso 1 — Configuración del entorno

Copia el fichero de ejemplo y ajusta los valores si es necesario:

```bash
cp .env.example .env
```

Los valores por defecto funcionan sin ningún cambio adicional.

### Paso 2 — Arrancar los servicios

```bash
docker compose up --build
```

Al arrancar ocurre lo siguiente de forma automática:

1. MinIO inicia y expone su endpoint (con healthcheck)
2. `minio-init` espera a que MinIO esté sano y crea el bucket
3. El servicio ETL arranca cuando MinIO está listo
4. n8n arranca y `n8n-init` importa el workflow automáticamente

Verifica que todos los servicios están en marcha:

```bash
docker compose ps
```

---

## 7. URLs de acceso

| Servicio | URL | Credenciales |
|---|---|---|
| ETL healthcheck | `http://localhost:8000/health` | — |
| n8n | `http://localhost:5678` | (ninguna por defecto) |
| MinIO Console | `http://localhost:9001` | `minioadmin / minioadmin` |
| Jupyter Lab | `http://localhost:8890` | (sin token) |

---

## 8. Ejecutar el pipeline manualmente

Por defecto recupera el día anterior según la zona horaria `Europe/Madrid`:

```bash
curl -X POST "http://localhost:8000/run"
```

Para una fecha concreta:

```bash
curl -X POST "http://localhost:8000/run?date=2026-05-05"
```

También puedes lanzarlo desde n8n con el botón **Test workflow** en la interfaz.

---

## 9. Validación de outputs

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

## 10. n8n — workflow

El workflow se importa automáticamente al arrancar gracias al servicio `n8n-init`. Contiene seis nodos:

| Nodo | Tipo | Descripción |
|---|---|---|
| `Daily Schedule 07:00` | `scheduleTrigger` | Se ejecuta cada día a las 07:00 (Europe/Madrid) |
| `Manual Trigger` | `manualTrigger` | Permite lanzar el pipeline a mano desde la UI |
| `Run ETL service` | `httpRequest` | `POST http://etl:8000/run` con timeout de 5 min |
| `Pipeline OK?` | `if` | Evalúa si `status == "success"` en la respuesta |
| `Log success` | `noOp` | Rama OK — registra filas curadas generadas |
| `Log error` | `noOp` | Rama error — registra el fallo y los errores del manifest |

Para ver el workflow abre `http://localhost:5678` y selecciona **Madrid Environmental Daily Pipeline**.

> Si necesitas reimportar el workflow manualmente:
> ```bash
> docker compose exec n8n n8n import:workflow --input=/workflows/madrid_environment_daily.json
> ```

---

## 11. Notebook de análisis (Jupyter)

Abre `http://localhost:8890`. El notebook está en:

```text
notebooks/analyze_curated_data.ipynb
```

Lee directamente desde MinIO usando el endpoint interno `minio:9000` y carga:

```text
curated/hourly_environment_wide/date=YYYY-MM-DD/hourly_environment_wide.csv
```

---

## 12. Comandos útiles

```bash
# Ver estado de los servicios
docker compose ps

# Ver logs en tiempo real
docker compose logs -f etl
docker compose logs -f n8n
docker compose logs -f jupyter

# Ejecutar pipeline para una fecha específica (dentro del contenedor)
docker compose exec etl python src/pipeline.py --date 2026-05-05

# Parar servicios (conserva volúmenes y datos)
docker compose down

# Parar y eliminar todos los datos persistidos
docker compose down -v
```

---

## 13. Estructura del repositorio

```text
.
├── docker-compose.yml        # Definición de todos los servicios
├── Dockerfile                # Imagen compartida por etl y jupyter
├── requirements.txt          # Dependencias Python
├── .env.example              # Plantilla de variables de entorno (copiar a .env)
├── .env                      # Variables de entorno activas (NO subir a git)
├── src/
│   ├── config.py             # Configuración centralizada desde variables de entorno
│   ├── sources.py            # Llamadas HTTP a las APIs de Open-Meteo
│   ├── transform.py          # Transformaciones raw → clean → processed → curated
│   ├── storage.py            # Carga de archivos en MinIO
│   ├── pipeline.py           # Orquestación del flujo completo
│   ├── server.py             # Servidor HTTP que expone /run y /health
│   ├── utils.py              # Utilidades (escritura CSV/JSON, listado de ficheros)
│   └── validate_outputs.py   # Validación de los outputs generados
├── n8n/workflows/
│   └── madrid_environment_daily.json  # Workflow de n8n exportado (se importa solo)
├── notebooks/
│   └── analyze_curated_data.ipynb     # Notebook de análisis desde MinIO
├── data/                     # Data Lake local (espejo del bucket MinIO)
│   ├── raw/
│   ├── clean/
│   ├── processed/
│   └── curated/
└── docs/
    └── ARCHITECTURE.md       # Descripción técnica de la arquitectura
```
