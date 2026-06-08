"""Application configuration — replace hardcoded values with env/DB in production."""

SECRET_KEY = "hpc-portal-secret-key-change-in-prod"

CORS_ORIGINS = ["http://localhost:5173"]

USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
    },
    "test": {
        "password": "test123",
        "role": "user",
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
