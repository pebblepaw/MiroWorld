from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mckainsey.api.routes_health import router as health_router
from mckainsey.api.routes_analytics import router as analytics_router
from mckainsey.api.routes_console import compat_router, router as console_router
from mckainsey.api.routes_phase_a import router as phase_a_router
from mckainsey.api.routes_phase_b import router as phase_b_router
from mckainsey.api.routes_phase_c import router as phase_c_router
from mckainsey.api.routes_phase_d import router as phase_d_router
from mckainsey.api.routes_phase_e import router as phase_e_router
from mckainsey.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(console_router)
app.include_router(analytics_router)
app.include_router(compat_router)
app.include_router(phase_a_router)
app.include_router(phase_b_router)
app.include_router(phase_c_router)
app.include_router(phase_d_router)
app.include_router(phase_e_router)
