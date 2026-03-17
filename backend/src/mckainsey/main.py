from fastapi import FastAPI

from mckainsey.api.routes_health import router as health_router
from mckainsey.api.routes_phase_a import router as phase_a_router
from mckainsey.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(phase_a_router)
