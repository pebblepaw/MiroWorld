from fastapi import APIRouter, Depends, HTTPException, Query

from miroworld.api.routes_console import _store_scope, require_hosted_user
from miroworld.config import Settings, get_settings
from miroworld.models.console import (
    V2OpinionFlowResponse,
    V2PolarizationResponse,
)
from miroworld.services.console_service import ConsoleService
from miroworld.services.demo_service import DemoService
from miroworld.services.storage import SimulationStore


router = APIRouter(prefix="/api/v2/console", tags=["analytics"])


def _is_demo_session(session_id: str, settings: Settings) -> bool:
    store = SimulationStore(settings.simulation_db_path)
    session = store.get_console_session(session_id)
    return session is not None and session.get("mode") == "demo"


def _get_demo_service(settings: Settings) -> DemoService:
    return DemoService(settings)


@router.get("/session/{session_id}/analytics/polarization", response_model=V2PolarizationResponse)
def analytics_polarization(
    session_id: str,
    metric_name: str | None = Query(None),
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> V2PolarizationResponse:
    with _store_scope(_user_id):
        if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
            payload = _get_demo_service(settings).get_analytics_polarization(session_id, metric_name=metric_name)
            return V2PolarizationResponse(**payload)

        try:
            payload = ConsoleService(settings).get_analytics_polarization(session_id, metric_name=metric_name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return V2PolarizationResponse(**payload)


@router.get("/session/{session_id}/analytics/opinion-flow", response_model=V2OpinionFlowResponse)
def analytics_opinion_flow(
    session_id: str,
    metric_name: str | None = Query(None),
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> V2OpinionFlowResponse:
    with _store_scope(_user_id):
        if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
            payload = _get_demo_service(settings).get_analytics_opinion_flow(session_id, metric_name=metric_name)
            return V2OpinionFlowResponse(**payload)

        try:
            payload = ConsoleService(settings).get_analytics_opinion_flow(session_id, metric_name=metric_name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return V2OpinionFlowResponse(**payload)


@router.get("/session/{session_id}/analytics/influence", response_model=None)
def analytics_influence(
    session_id: str,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> dict[str, object]:
    with _store_scope(_user_id):
        if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
            payload = _get_demo_service(settings).get_analytics_influence(session_id)
            return payload

        try:
            payload = ConsoleService(settings).get_analytics_influence(session_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return payload


@router.get("/session/{session_id}/analytics/cascades", response_model=None)
def analytics_cascades(
    session_id: str,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> dict[str, object]:
    with _store_scope(_user_id):
        if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
            payload = _get_demo_service(settings).get_analytics_cascades(session_id)
            return payload

        try:
            payload = ConsoleService(settings).get_analytics_cascades(session_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return payload


@router.get("/session/{session_id}/analytics/agent-stances", response_model=None)
def analytics_agent_stances(
    session_id: str,
    metric_name: str | None = Query(None),
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> dict[str, object]:
    with _store_scope(_user_id):
        if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
            payload = _get_demo_service(settings).get_analytics_agent_stances(session_id, metric_name=metric_name)
            return payload

        try:
            payload = ConsoleService(settings).get_agent_stances(session_id, metric_name=metric_name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return payload
