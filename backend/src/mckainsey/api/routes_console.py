import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from mckainsey.config import Settings, get_settings
from mckainsey.models.console import (
    ConsoleAgentChatRequest,
    ConsoleAgentChatResponse,
    ConsoleKnowledgeProcessRequest,
    ConsoleModelProviderCatalogResponse,
    ConsoleProviderModelsResponse,
    ConsoleReportChatRequest,
    ConsoleReportChatResponse,
    ConsoleSessionModelConfigRequest,
    ConsoleSessionModelConfigResponse,
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
from mckainsey.services.demo_service import DemoService
from mckainsey.services.simulation_stream_service import SimulationStreamService


router = APIRouter(prefix="/api/v2/console", tags=["console"])


def _is_demo_session(session_id: str, settings: Settings) -> bool:
    """Check if session is in demo mode."""
    from mckainsey.services.storage import SimulationStore
    store = SimulationStore(settings.simulation_db_path)
    session = store.get_console_session(session_id)
    return session is not None and session.get("mode") == "demo"


def _get_demo_service(settings: Settings) -> DemoService:
    """Get demo service instance."""
    return DemoService(settings)


@router.post("/session", response_model=ConsoleSessionResponse)
def create_session(
    req: ConsoleSessionCreateRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionResponse:
    payload = ConsoleService(settings).create_session(
        req.session_id,
        req.mode,
        model_provider=req.model_provider,
        model_name=req.model_name,
        embed_model_name=req.embed_model_name,
        api_key=req.api_key,
        base_url=req.base_url,
    )
    return ConsoleSessionResponse(**payload)


@router.get("/model/providers", response_model=ConsoleModelProviderCatalogResponse)
def model_providers(settings: Settings = Depends(get_settings)) -> ConsoleModelProviderCatalogResponse:
    payload = ConsoleService(settings).model_provider_catalog()
    return ConsoleModelProviderCatalogResponse(**payload)


@router.get("/model/providers/{provider}/models", response_model=ConsoleProviderModelsResponse)
def provider_models(
    provider: str,
    api_key: str | None = Query(default=None),
    base_url: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> ConsoleProviderModelsResponse:
    payload = ConsoleService(settings).list_provider_models(
        provider,
        api_key=api_key,
        base_url=base_url,
    )
    return ConsoleProviderModelsResponse(**payload)


@router.get("/session/{session_id}/model", response_model=ConsoleSessionModelConfigResponse)
def get_session_model(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionModelConfigResponse:
    payload = ConsoleService(settings).get_session_model_config(session_id)
    return ConsoleSessionModelConfigResponse(**payload)


@router.put("/session/{session_id}/model", response_model=ConsoleSessionModelConfigResponse)
def update_session_model(
    session_id: str,
    req: ConsoleSessionModelConfigRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionModelConfigResponse:
    payload = ConsoleService(settings).update_session_model_config(
        session_id,
        model_provider=req.model_provider,
        model_name=req.model_name,
        embed_model_name=req.embed_model_name,
        api_key=req.api_key,
        base_url=req.base_url,
    )
    return ConsoleSessionModelConfigResponse(**payload)


@router.post("/session/{session_id}/knowledge/process", response_model=KnowledgeArtifactResponse)
async def process_knowledge(
    session_id: str,
    req: ConsoleKnowledgeProcessRequest,
    settings: Settings = Depends(get_settings),
) -> KnowledgeArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached knowledge for demo
        demo_service = _get_demo_service(settings)
        knowledge = demo_service.get_knowledge_artifact(session_id)
        if knowledge:
            return KnowledgeArtifactResponse(**knowledge)
    
    payload = await ConsoleService(settings).process_knowledge(
        session_id,
        document_text=req.document_text,
        source_path=req.source_path,
        guiding_prompt=req.guiding_prompt,
        demographic_focus=req.demographic_focus,
        use_default_demo_document=req.use_default_demo_document,
    )
    return KnowledgeArtifactResponse(**payload)


@router.post("/session/{session_id}/knowledge/upload", response_model=KnowledgeArtifactResponse)
async def upload_knowledge(
    session_id: str,
    file: UploadFile = File(...),
    guiding_prompt: str | None = Form(default=None),
    demographic_focus: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
) -> KnowledgeArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached knowledge for demo
        demo_service = _get_demo_service(settings)
        knowledge = demo_service.get_knowledge_artifact(session_id)
        if knowledge:
            return KnowledgeArtifactResponse(**knowledge)
    
    payload = await ConsoleService(settings).process_uploaded_knowledge(
        session_id,
        upload=file,
        guiding_prompt=guiding_prompt,
        demographic_focus=demographic_focus,
    )
    return KnowledgeArtifactResponse(**payload)


@router.post("/session/{session_id}/sampling/preview", response_model=PopulationArtifactResponse)
def preview_population(
    session_id: str,
    req: PopulationPreviewRequest,
    settings: Settings = Depends(get_settings),
) -> PopulationArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached population for demo
        demo_service = _get_demo_service(settings)
        population = demo_service.get_population_artifact(session_id)
        if population:
            return PopulationArtifactResponse(**population)
    
    payload = ConsoleService(settings).preview_population(session_id, req)
    return PopulationArtifactResponse(**payload)


@router.get("/session/{session_id}/simulation/state", response_model=SimulationStateResponse)
def simulation_state(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached simulation state for demo
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)
    
    payload = SimulationStreamService(settings).get_state(session_id)
    return SimulationStateResponse(**payload)


@router.post("/session/{session_id}/simulation/start", response_model=SimulationStateResponse)
def simulation_start(
    session_id: str,
    req: SimulationStartRequest,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached simulation state for demo (already completed)
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)
    
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
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached events from demo cache
        demo_service = _get_demo_service(settings)
        cache = demo_service._load_demo_cache()
        if cache and "simulationState" in cache:
            # Create a stream from cached events
            sim_state = cache["simulationState"]
            recent_events = sim_state.get("recent_events", [])
            
            def demo_sse_iter():
                # Send all cached events
                for event in recent_events:
                    event_type = event.get("event_type", "event")
                    data = json.dumps(event)
                    yield f"event: {event_type}\ndata: {data}\n\n"
                # Send completion
                yield f"event: completed\ndata: {json.dumps({'session_id': session_id, 'status': 'completed'})}\n\n"
            
            return StreamingResponse(demo_sse_iter(), media_type="text/event-stream")
    
    stream = SimulationStreamService(settings).sse_iter(session_id)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.get("/session/{session_id}/report/full", response_model=ReportFullResponse)
def report_full(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return ReportFullResponse(**report)
    
    return ReportFullResponse(**ConsoleService(settings).get_report_full(session_id))


@router.post("/session/{session_id}/report/generate", response_model=ReportFullResponse)
def report_generate(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return ReportFullResponse(**report)
    
    return ReportFullResponse(**ConsoleService(settings).generate_report(session_id))


@router.get("/session/{session_id}/report/opinions", response_model=ReportOpinionsResponse)
def report_opinions(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportOpinionsResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        opinions = demo_service.get_report_opinions(session_id)
        return ReportOpinionsResponse(**opinions)
    
    return ReportOpinionsResponse(**ConsoleService(settings).get_report_opinions(session_id))


@router.get("/session/{session_id}/report/friction-map", response_model=ReportFrictionMapResponse)
def report_friction_map(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFrictionMapResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        friction = demo_service.get_friction_map(session_id)
        return ReportFrictionMapResponse(**friction)
    
    return ReportFrictionMapResponse(**ConsoleService(settings).get_report_friction_map(session_id))


@router.get("/session/{session_id}/interaction-hub", response_model=InteractionHubResponse)
def interaction_hub(
    session_id: str,
    agent_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> InteractionHubResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        hub = demo_service.get_interaction_hub(session_id, agent_id)
        return InteractionHubResponse(**hub)
    
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
