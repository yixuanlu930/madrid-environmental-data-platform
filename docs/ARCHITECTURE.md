# Arquitectura

```text
Fuentes externas
├── Open-Meteo Historical Weather API
└── Portal de datos abiertos del Ayuntamiento de Madrid
        │
        ▼
n8n ──HTTP──► ETL service Python
        │          │
        │          ├── RAW: datos originales
        │          ├── CLEAN: datos tabulares por fuente
        │          ├── PROCESSED: dataset unificado
        │          └── CURATED: resumen diario para análisis
        │
        ▼
MinIO / S3 compatible object storage
```

## Decisión de diseño

La práctica se resuelve con un Data Lake por zonas:

- `raw`: conserva la respuesta original de las fuentes, sin pérdida.
- `clean`: normaliza cada fuente a CSV tabular.
- `processed`: integra observaciones ambientales de varias fuentes en un único esquema.
- `curated`: genera tablas finales resumidas para análisis desde Python, notebooks o BI.

La automatización se realiza con n8n. El workflow contiene:
- un disparador manual para pruebas;
- un disparador programado diario a las 07:00;
- una petición HTTP al servicio ETL (`http://etl:8000/run`).

Docker Compose garantiza:
- persistencia mediante volúmenes (`minio_data`, `n8n_data`) y bind mount `./data`;
- comunicación mediante la red `madrid-data-net`;
- aislamiento mediante servicios separados (`minio`, `etl`, `n8n`).
