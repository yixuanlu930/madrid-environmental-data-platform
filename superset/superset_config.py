# superset_config.py
import os

SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "madrid_superset_secret_change_in_prod")

# Superset guarda su propia metadata en SQLite.
# Los datos ambientales se consultan desde PostgreSQL (conexión configurada en la UI).
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"

WTF_CSRF_ENABLED = False
SESSION_COOKIE_SAMESITE = "Lax"
SUPERSET_LOAD_EXAMPLES = False
SUPERSET_WEBSERVER_TIMEOUT = 300
