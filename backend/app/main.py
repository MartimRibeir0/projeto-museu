from fastapi import APIRouter, FastAPI

from . import config
from .routers import devices, exhibitions, photos

app = FastAPI(title="Museu Virtual Pessoal API", version="0.1.0")

api = APIRouter(prefix=config.API_PREFIX)


@api.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


api.include_router(photos.router)
api.include_router(exhibitions.router)
api.include_router(devices.router)
app.include_router(api)
