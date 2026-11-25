import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage")).resolve()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
THUMB_SIZE = 400
API_PREFIX = "/api/v1"
MQTT_HOST = os.getenv("MQTT_HOST", "")  # vazio = ponte MQTT desligada
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
