"""
db_loader.py
Carga las zonas PROCESSED y CURATED del data lake en PostgreSQL.
Se llama al final de run_preprocess() y run_analytics() respectivamente.

Tablas destino (esquema madrid_environment):
  - environment_observations_long  ← zona processed (formato largo)
  - hourly_environment_wide        ← zona curated (formato wide horario)
  - daily_variable_summary         ← zona curated (resumen diario)
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import psycopg2
import psycopg2.extras

from src.config import settings
from src.utils import safe_float

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------

def get_connection():
    return psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        dbname=settings.pg_db,
        user=settings.pg_user,
        password=settings.pg_password,
    )


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _to_ts(val: Any) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _to_date(val: Any) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------
# 1. Observaciones horarias en formato largo (zona PROCESSED)
# ---------------------------------------------------------------

_INSERT_LONG = """
INSERT INTO madrid_environment.environment_observations_long
    (source, dataset, date, time, latitude, longitude, variable, value, unit)
VALUES %s
ON CONFLICT DO NOTHING
"""

def load_observations_long(rows: list[dict[str, Any]], day: date) -> int:
    """Inserta las filas de environment_observations_long en PostgreSQL."""
    if not rows:
        return 0

    tuples = [
        (
            str(row.get("source", "")),
            str(row.get("dataset", "")),
            day,
            _to_ts(row.get("time")),
            safe_float(row.get("latitude")),
            safe_float(row.get("longitude")),
            str(row.get("variable", "")),
            safe_float(row.get("value")),
            str(row.get("unit", "")) or None,
        )
        for row in rows
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, _INSERT_LONG, tuples, page_size=500)
        conn.commit()

    logger.info("environment_observations_long → PostgreSQL: %d filas para %s", len(tuples), day)
    return len(tuples)


# ---------------------------------------------------------------
# 2. Tabla hourly wide (zona CURATED)
# ---------------------------------------------------------------

_UPSERT_WIDE = """
INSERT INTO madrid_environment.hourly_environment_wide
    (date, time, latitude, longitude,
     temperature_2m, precipitation, ozone, carbon_dioxide)
VALUES %s
ON CONFLICT (date, time) DO UPDATE SET
    latitude       = EXCLUDED.latitude,
    longitude      = EXCLUDED.longitude,
    temperature_2m = EXCLUDED.temperature_2m,
    precipitation  = EXCLUDED.precipitation,
    ozone          = EXCLUDED.ozone,
    carbon_dioxide = EXCLUDED.carbon_dioxide
"""

def load_hourly_wide(rows: list[dict[str, Any]], day: date) -> int:
    """Upsert de la tabla horaria wide."""
    if not rows:
        return 0

    tuples = [
        (
            day,
            _to_ts(row.get("time")),
            safe_float(row.get("latitude")),
            safe_float(row.get("longitude")),
            safe_float(row.get("temperature_2m")),
            safe_float(row.get("precipitation")),
            safe_float(row.get("ozone")),
            safe_float(row.get("carbon_dioxide")),
        )
        for row in rows
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, _UPSERT_WIDE, tuples, page_size=500)
        conn.commit()

    logger.info("hourly_environment_wide → PostgreSQL: %d filas para %s", len(tuples), day)
    return len(tuples)


# ---------------------------------------------------------------
# 3. Resumen diario (zona CURATED)
# ---------------------------------------------------------------

_UPSERT_SUMMARY = """
INSERT INTO madrid_environment.daily_variable_summary
    (date, source, dataset, variable, unit,
     observations, min_value, avg_value, max_value)
VALUES %s
ON CONFLICT (date, source, dataset, variable) DO UPDATE SET
    unit         = EXCLUDED.unit,
    observations = EXCLUDED.observations,
    min_value    = EXCLUDED.min_value,
    avg_value    = EXCLUDED.avg_value,
    max_value    = EXCLUDED.max_value
"""

def load_daily_summary(rows: list[dict[str, Any]]) -> int:
    """Upsert del resumen diario."""
    if not rows:
        return 0

    tuples = [
        (
            _to_date(row.get("date")),
            str(row.get("source", "")),
            str(row.get("dataset", "")),
            str(row.get("variable", "")),
            str(row.get("unit", "")) or None,
            int(row["observations"]) if row.get("observations") is not None else None,
            safe_float(row.get("min_value")),
            safe_float(row.get("avg_value")),
            safe_float(row.get("max_value")),
        )
        for row in rows
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, _UPSERT_SUMMARY, tuples, page_size=200)
        conn.commit()

    logger.info("daily_variable_summary → PostgreSQL: %d filas", len(tuples))
    return len(tuples)
