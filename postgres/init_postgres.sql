-- =============================================================
-- init_postgres.sql
-- Crea el esquema analítico en PostgreSQL.
-- Se ejecuta automáticamente al arrancar el contenedor postgres
-- gracias al mecanismo de initdb de la imagen oficial
-- (ficheros en /docker-entrypoint-initdb.d/ se ejecutan una sola vez).
-- =============================================================

-- ---------------------------------------------------------------
-- Esquema dedicado al proyecto
-- ---------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS madrid_environment;

-- ---------------------------------------------------------------
-- Tabla 1: observaciones horarias en formato largo (zona PROCESSED)
-- Fuente: processed/environment_observations_long/
-- Una fila por fuente/variable/hora.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS madrid_environment.environment_observations_long (
    id          SERIAL PRIMARY KEY,
    source      VARCHAR(64)  NOT NULL,
    dataset     VARCHAR(128) NOT NULL,
    date        DATE         NOT NULL,
    time        TIMESTAMP,
    latitude    DOUBLE PRECISION,
    longitude   DOUBLE PRECISION,
    variable    VARCHAR(64)  NOT NULL,
    value       DOUBLE PRECISION,
    unit        VARCHAR(32)
);

CREATE INDEX IF NOT EXISTS idx_long_date     ON madrid_environment.environment_observations_long (date);
CREATE INDEX IF NOT EXISTS idx_long_var      ON madrid_environment.environment_observations_long (variable);
CREATE INDEX IF NOT EXISTS idx_long_date_var ON madrid_environment.environment_observations_long (date, variable);

-- ---------------------------------------------------------------
-- Tabla 2: tabla horaria wide con todas las variables (zona CURATED)
-- Fuente: curated/hourly_environment_wide/
-- Una fila por hora, columnas = variables ambientales.
-- Óptima para series temporales en dashboards.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS madrid_environment.hourly_environment_wide (
    id             SERIAL PRIMARY KEY,
    date           DATE             NOT NULL,
    time           TIMESTAMP        NOT NULL,
    latitude       DOUBLE PRECISION,
    longitude      DOUBLE PRECISION,
    temperature_2m DOUBLE PRECISION,
    precipitation  DOUBLE PRECISION,
    ozone          DOUBLE PRECISION,
    carbon_dioxide DOUBLE PRECISION,
    UNIQUE (date, time)
);

CREATE INDEX IF NOT EXISTS idx_wide_date ON madrid_environment.hourly_environment_wide (date);

-- ---------------------------------------------------------------
-- Tabla 3: resumen diario por variable (zona CURATED)
-- Fuente: curated/daily_variable_summary/
-- Una fila por día/fuente/dataset/variable.
-- Principal tabla para dashboards de responsables políticos.
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS madrid_environment.daily_variable_summary (
    id           SERIAL PRIMARY KEY,
    date         DATE         NOT NULL,
    source       VARCHAR(64)  NOT NULL,
    dataset      VARCHAR(128) NOT NULL,
    variable     VARCHAR(64)  NOT NULL,
    unit         VARCHAR(32),
    observations INTEGER,
    min_value    DOUBLE PRECISION,
    avg_value    DOUBLE PRECISION,
    max_value    DOUBLE PRECISION,
    UNIQUE (date, source, dataset, variable)
);

CREATE INDEX IF NOT EXISTS idx_sum_date ON madrid_environment.daily_variable_summary (date);
CREATE INDEX IF NOT EXISTS idx_sum_var  ON madrid_environment.daily_variable_summary (variable);
