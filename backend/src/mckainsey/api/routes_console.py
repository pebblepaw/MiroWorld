from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from mckainsey.config import Settings, get_settings
from mckainsey.models.console import (
    ConsoleAgentChatRequest,
    ConsoleAgentChatResponse,
    ConsoleKnowledgeProcessRequest,
    ConsoleReportChatRequest,
    ConsoleReportChatResponse,
    ConsoleSessionCreateRequest,
    ConsoleSessionResponse,
    InteractionHubResponse,
    KnowledgeArtifactResponse,
    PopulationArtifactResponse,
    PopulationPreviewRequest,
    ReportFrictionMapResponse,
    ReportFullResponse,
    ReportOpinionsResponse,
    SimulationStartRequest,
    SimulationStateResponse,
)
from mckainsey.services.console_service import ConsoleService
from mckainsey.services.simulation_stream_service import SimulationStreamService


router = APIRouter(prefix="/api/v2/console", tags=["console"])


@router.post("/session", response_model=ConsoleSessionResponse)
def create_session(
    req: ConsoleSessionCreateRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionResponse:
    payload = ConsoleService(settings).create_session(req.session_id, req.mode)
    return ConsoleSessionResponse(**payload)


@router.post("/session/{session_id}/knowledge/process", response_model=KnowledgeArtifactResponse)
async def process_knowledge(
    session_id: str,
    req: ConsoleKnowledgeProcessRequest,
    settings: Settings = Depends(get_settings),
) -> KnowledgeArtifactResponse:
    payload = await ConsoleService(settings).process_knowledge(
        session_id,
        document_text=req.document_text,
        source_path=req.source_path,
        demographic_focus=req.demographic_focus,
        use_default_demo_document=req.use_default_demo_document,
    )
    return KnowledgeArtifactResponse(**payload)


@router.post("/session/{session_id}/knowledge/upload", response_model=KnowledgeArtifactResponse)
async def upload_knowledge(
    session_id: str,
    file: UploadFile = File(...),
    demographic_focus: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
) -> KnowledgeArtifactResponse:
    payload = await ConsoleService(settings).process_uploaded_knowledge(
        session_id,
        upload=file,
        demographic_focus=demographic_focus,
    )
    return KnowledgeArtifactResponse(**payload)


@router.post("/session/{session_id}/sampling/preview", response_model=PopulationArtifactResponse)
def preview_population(
    session_id: str,
    req: PopulationPreviewRequest,
    settings: Settings = Depends(get_settings),
) -> PopulationArtifactResponse:
    payload = ConsoleService(settings).preview_population(session_id, req)
    return PopulationArtifactResponse(**payload)


@router.get("/session/{session_id}/simulation/state", response_model=SimulationStateResponse)
def simulation_state(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    payload = SimulationStreamService(settings).get_state(session_id)
    return SimulationStateResponse(**payload)


@router.post("/session/{session_id}/simulation/start", response_model=SimulationStateResponse)
def simulation_start(
    session_id: str,
    req: SimulationStartRequest,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    payload = ConsoleService(settings).start_simulation(
        session_id,
        policy_summary=req.policy_summary,
        rounds=req.rounds,
        mode=req.mode,
    )
    return SimulationStateResponse(**payload)


@router.get("/session/{session_id}/simulation/stream")
def simulation_stream(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    stream = SimulationStreamService(settings).sse_iter(session_id)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.get("/session/{session_id}/report/full", response_model=ReportFullResponse)
def report_full(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    return ReportFullResponse(**ConsoleService(settings).get_report_full(session_id))


@router.get("/session/{session_id}/report/opinions", response_model=ReportOpinionsResponse)
def report_opinions(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportOpinionsResponse:
    return ReportOpinionsResponse(**ConsoleService(settings).get_report_opinions(session_id))


@router.get("/session/{session_id}/report/friction-map", response_model=ReportFrictionMapResponse)
def report_friction_map(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFrictionMapResponse:
    return ReportFrictionMapResponse(**ConsoleService(settings).get_report_friction_map(session_id))


@router.get("/session/{session_id}/interaction-hub", response_model=InteractionHubResponse)
def interaction_hub(
    session_id: str,
    agent_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> InteractionHubResponse:
    return InteractionHubResponse(**ConsoleService(settings).get_interaction_hub(session_id, agent_id=agent_id))


@router.post("/session/{session_id}/interaction-hub/report-chat", response_model=ConsoleReportChatResponse)
def interaction_hub_report_chat(
    session_id: str,
    req: ConsoleReportChatRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleReportChatResponse:
    try:
        payload = ConsoleService(settings).report_chat(session_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConsoleReportChatResponse(**payload)


@router.post("/session/{session_id}/interaction-hub/agent-chat", response_model=ConsoleAgentChatResponse)
def interaction_hub_agent_chat(
    session_id: str,
    req: ConsoleAgentChatRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleAgentChatResponse:
    try:
        payload = ConsoleService(settings).agent_chat(session_id, req.agent_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConsoleAgentChatResponse(**payload)
