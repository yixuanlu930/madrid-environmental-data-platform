
# Arquitectura

La infraestructura usa únicamente Open-Meteo como plataforma de datos abiertos, pero con dos APIs distintas:

1. Historical Weather API.
2. Air Quality API.

Ambas consultas se realizan para Madrid:

- latitude = 40.4168
- longitude = -3.7038
- timezone = Europe/Madrid

## Flujo

```text
n8n
  │ POST http://etl:8000/run
  ▼
ETL Python
  ├── llama a Historical Weather API
  ├── llama a Air Quality API
  ├── guarda RAW JSON
  ├── transforma a CLEAN CSV
  ├── genera PROCESSED long table
  └── genera CURATED wide table + summary
  ▼
MinIO Data Lake
  ▲
  │
Jupyter conectado a la misma red Docker
```

## Zonas del Data Lake

- `raw`: respuestas JSON originales de cada API.
- `clean`: una tabla horaria limpia por API. Cada API devuelve 24 filas para el día anterior.
- `processed`: tabla larga unificada con 96 observaciones: 24 horas × 4 variables.
- `curated`: tabla ancha optimizada para análisis con 24 filas y columnas analíticas.

## Variables

Historical Weather API:

- `temperature_2m`
- `precipitation`

Air Quality API:

- `ozone`
- `carbon_dioxide`

## Jupyter

El servicio `jupyter` está en la misma red Docker que `minio` y `etl`, por lo que puede leer directamente del bucket `madrid-openmeteo-environment` usando el endpoint interno `minio:9000`.
