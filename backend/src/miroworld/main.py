from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from miroworld.api.routes_health import router as health_router
from miroworld.api.routes_analytics import router as analytics_router
from miroworld.api.routes_console import compat_router, router as console_router
from miroworld.api.routes_phase_a import router as phase_a_router
from miroworld.api.routes_phase_b import router as phase_b_router
from miroworld.api.routes_phase_c import router as phase_c_router
from miroworld.config import get_settings
from miroworld.services.storage import reset_store_user_context, set_store_user_context

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.middleware("http")
async def clear_store_user_scope(request, call_next):
	token = set_store_user_context(None)
	try:
		return await call_next(request)
	finally:
		reset_store_user_context(token)

app.include_router(health_router)
app.include_router(console_router)
app.include_router(analytics_router)
app.include_router(compat_router)
app.include_router(phase_a_router)
app.include_router(phase_b_router)
app.include_router(phase_c_router)
