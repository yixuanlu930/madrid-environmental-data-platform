#!/bin/bash
set -e
echo ">>> Inicializando base de datos de Superset..."
superset db upgrade
echo ">>> Creando usuario administrador..."
superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname Madrid \
  --email admin@madrid.local \
  --password admin || true
echo ">>> Cargando roles y permisos por defecto..."
superset init
echo ">>> Superset listo."
