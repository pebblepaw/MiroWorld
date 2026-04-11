from fastapi import APIRouter, Depends, HTTPException

from miroworld.config import Settings, get_settings
from miroworld.models.phase_d import ReportChatRequest, ReportChatResponse, ReportResponse
from miroworld.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/phase-d", tags=["phase-d"])


@router.get("/report/{simulation_id}", response_model=ReportResponse)
def get_report(
    simulation_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportResponse:
    try:
        report = ReportService(settings).build_report(simulation_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReportResponse(**report)


@router.post("/report/chat", response_model=ReportChatResponse)
def report_chat(
    req: ReportChatRequest,
    settings: Settings = Depends(get_settings),
) -> ReportChatResponse:
    try:
        response = ReportService(settings).report_chat(req.simulation_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReportChatResponse(simulation_id=req.simulation_id, response=response)
