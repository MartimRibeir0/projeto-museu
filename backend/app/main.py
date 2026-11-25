from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from . import config, mqtt
from .db import SessionLocal
from .routers import devices, exhibitions, photos


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if config.MQTT_HOST:
        with SessionLocal() as db:
            mqtt.seed_devices(db)
    mqtt.start()
    yield
    mqtt.stop()


app = FastAPI(title="Museu Virtual Pessoal API", version="0.1.0", lifespan=lifespan)

api = APIRouter(prefix=config.API_PREFIX)


@api.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


api.include_router(photos.router)
api.include_router(exhibitions.router)
api.include_router(devices.router)
app.include_router(api)
