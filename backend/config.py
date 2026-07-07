"""Application configuration — replace hardcoded values with env/DB in production."""
import os

# --- MySQL connection settings ---
# Override any of these via environment variables in production.
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "hpc_app")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "pari123")
DB_NAME = os.environ.get("DB_NAME", "hpc_portal")

# Allowed email domain for registration (Phase 2)
ALLOWED_EMAIL_DOMAIN = "@iiserpune.ac.in"
SECRET_KEY = "hpc-portal-secret-key-change-in-prod"

CORS_ORIGINS = ["http://localhost:5173","http://127.0.0.1:5173",]

USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
    },
    
}

# Temporary hardcoded cluster registry — move to DB later
CLUSTERS = {
    "fortytwo": {
        "host": "192.168.1.152",
        "port": 22,
        "display_name": "Fortytwo Cluster",
    },
}

DEFAULT_UTILIZATION_START = "2025-10-01"
DEFAULT_UTILIZATION_END = "2025-12-31"
