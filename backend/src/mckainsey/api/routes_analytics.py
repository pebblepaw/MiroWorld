from fastapi import APIRouter, Depends, HTTPException

from mckainsey.config import Settings, get_settings
from mckainsey.models.console import (
    V2OpinionFlowResponse,
    V2PolarizationResponse,
)
from mckainsey.services.console_service import ConsoleService


router = APIRouter(prefix="/api/v2/console", tags=["analytics"])


@router.get("/session/{session_id}/analytics/polarization", response_model=V2PolarizationResponse)
def analytics_polarization(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> V2PolarizationResponse:
    try:
        payload = ConsoleService(settings).get_analytics_polarization(session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2PolarizationResponse(**payload)


@router.get("/session/{session_id}/analytics/opinion-flow", response_model=V2OpinionFlowResponse)
def analytics_opinion_flow(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> V2OpinionFlowResponse:
    try:
        payload = ConsoleService(settings).get_analytics_opinion_flow(session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2OpinionFlowResponse(**payload)


@router.get("/session/{session_id}/analytics/influence", response_model=None)
def analytics_influence(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        payload = ConsoleService(settings).get_analytics_influence(session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return payload


@router.get("/session/{session_id}/analytics/cascades", response_model=None)
def analytics_cascades(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        payload = ConsoleService(settings).get_analytics_cascades(session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return payload
