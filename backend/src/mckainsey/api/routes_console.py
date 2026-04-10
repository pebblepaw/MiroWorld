import json
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from mckainsey.config import Settings, get_settings
from mckainsey.models.console import (
    ConsoleAgentChatRequest,
    ConsoleAgentChatResponse,
    ConsoleDynamicFiltersResponse,
    ConsoleKnowledgeProcessRequest,
    ConsoleModelProviderCatalogResponse,
    ConsoleProviderModelsResponse,
    ConsoleReportChatRequest,
    ConsoleReportChatResponse,
    ConsoleScrapeRequest,
    ConsoleScrapeResponse,
    ConsoleSessionModelConfigRequest,
    ConsoleSessionModelConfigResponse,
    ConsoleSessionCreateRequest,
    ConsoleSessionResponse,
    V2AgentChatRequest,
    V2AgentChatResponse,
    V2GroupChatAgentsResponse,
    V2GroupChatRequest,
    V2GroupChatResponse,
    InteractionHubResponse,
    KnowledgeArtifactResponse,
    PopulationArtifactResponse,
    PopulationPreviewRequest,
    ReportFrictionMapResponse,
    ReportOpinionsResponse,
    SimulationStartRequest,
    SimulationQuickStartRequest,
    SimulationStateResponse,
    TokenUsageEstimateResponse,
    TokenUsageRuntimeResponse,
    V2CountryResponse,
    V2ProviderResponse,
    V2ReportResponse,
    V2SessionConfigPatchRequest,
    V2SessionConfigResponse,
    V2SessionCreateRequest,
    V2SessionCreateResponse,
)
from mckainsey.services.config_service import ConfigService
from mckainsey.services.console_service import ConsoleService
from mckainsey.services.demo_service import DemoService
from mckainsey.services.scrape_service import ScrapeService
from mckainsey.services.simulation_stream_service import SimulationStreamService


router = APIRouter(prefix="/api/v2/console", tags=["console"])
compat_router = APIRouter(prefix="/api/v2", tags=["console-compat"])


def _is_demo_session(session_id: str, settings: Settings) -> bool:
    """Check if session is in demo mode."""
    from mckainsey.services.storage import SimulationStore
    store = SimulationStore(settings.simulation_db_path)
    session = store.get_console_session(session_id)
    return session is not None and session.get("mode") == "demo"


def _get_demo_service(settings: Settings) -> DemoService:
    """Get demo service instance."""
    return DemoService(settings)


def _normalize_group_chat_segment(segment: Any) -> str:
    segment_key = str(segment or "").strip().lower()
    alias_map = {
        "supporters": "supporter",
        "dissenters": "dissenter",
    }
    return alias_map.get(segment_key, segment_key)


def _parse_group_chat_request(body: dict[str, Any]) -> V2GroupChatRequest:
    normalized = dict(body or {})
    normalized["segment"] = _normalize_group_chat_segment(normalized.get("segment"))
    try:
        return V2GroupChatRequest(**normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@compat_router.get("/countries", response_model=list[V2CountryResponse])
def v2_countries(settings: Settings = Depends(get_settings)) -> list[V2CountryResponse]:
    service = ConfigService(settings)
    rows = []
    for country in service.list_countries():
        rows.append(
            V2CountryResponse(
                name=str(country.get("name", "")),
                code=str(country.get("code", "")).lower(),
                flag_emoji=str(country.get("flag_emoji", "")),
                dataset_path=str(country.get("dataset_path", "")),
                available=bool(country.get("available", True)),
            )
        )
    return rows


@compat_router.get("/providers", response_model=list[V2ProviderResponse])
def v2_providers(settings: Settings = Depends(get_settings)) -> list[V2ProviderResponse]:
    payload = ConsoleService(settings).v2_provider_catalog()
    return [V2ProviderResponse(**row) for row in payload]


@compat_router.post("/session/create", response_model=V2SessionCreateResponse)
def v2_session_create(
    req: V2SessionCreateRequest,
    settings: Settings = Depends(get_settings),
) -> V2SessionCreateResponse:
    provider = "google" if req.provider == "gemini" else req.provider
    try:
        payload = ConsoleService(settings).create_v2_session(
            country=req.country,
            use_case=req.use_case,
            provider=provider,
            model=req.model,
            api_key=req.api_key,
            mode=req.mode,
            session_id=req.session_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return V2SessionCreateResponse(**payload)


@compat_router.patch("/session/{session_id}/config", response_model=V2SessionConfigResponse)
@router.patch("/session/{session_id}/config", response_model=V2SessionConfigResponse)
def v2_session_update_config(
    session_id: str,
    req: V2SessionConfigPatchRequest,
    settings: Settings = Depends(get_settings),
) -> V2SessionConfigResponse:
    try:
        normalized_use_case = req.use_case
        if req.use_case is not None:
            normalized_use_case = str(
                ConfigService(settings).get_use_case(req.use_case).get("code", req.use_case)
            ).strip().lower()
        payload = ConsoleService(settings).update_v2_session_config(
            session_id,
            country=req.country,
            use_case=normalized_use_case,
            provider=req.provider,
            model=req.model,
            api_key=req.api_key,
            guiding_prompt=req.guiding_prompt,
            analysis_questions=req.analysis_questions,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return V2SessionConfigResponse(**payload)


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
        documents=req.documents,
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


@router.post("/session/{session_id}/scrape", response_model=ConsoleScrapeResponse)
def scrape_document(
    session_id: str,
    req: ConsoleScrapeRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleScrapeResponse:
    del session_id
    del settings
    scraper = ScrapeService()
    try:
        payload = scraper.scrape(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to scrape URL: {exc}") from exc
    return ConsoleScrapeResponse(**payload)


@router.get("/session/{session_id}/filters", response_model=ConsoleDynamicFiltersResponse)
def session_filters(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ConsoleDynamicFiltersResponse:
    try:
        payload = ConsoleService(settings).get_dynamic_filters(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConsoleDynamicFiltersResponse(**payload)


@compat_router.get("/token-usage/{session_id}/estimate", response_model=TokenUsageEstimateResponse)
def token_usage_estimate(
    session_id: str,
    agents: int = Query(default=250, ge=1, le=2000),
    rounds: int = Query(default=5, ge=1, le=100),
    settings: Settings = Depends(get_settings),
) -> TokenUsageEstimateResponse:
    payload = ConsoleService(settings).estimate_token_usage(
        session_id,
        agents=agents,
        rounds=rounds,
    )
    return TokenUsageEstimateResponse(**payload)


@compat_router.get("/token-usage/{session_id}", response_model=TokenUsageRuntimeResponse)
def token_usage_runtime(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> TokenUsageRuntimeResponse:
    payload = ConsoleService(settings).get_runtime_token_usage(session_id)
    return TokenUsageRuntimeResponse(**payload)


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
    
    payload = ConsoleService(settings).get_simulation_state(session_id)
    return SimulationStateResponse(**payload)


@router.get("/session/{session_id}/simulation/metrics", response_model=SimulationStateResponse)
def simulation_metrics(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)

    payload = ConsoleService(settings).get_simulation_state(session_id)
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
        controversy_boost=req.controversy_boost,
        mode=req.mode,
    )
    return SimulationStateResponse(**payload)


@router.post("/session/{session_id}/simulate", response_model=SimulationStateResponse)
def simulate(
    session_id: str,
    req: SimulationQuickStartRequest,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)

    service = ConsoleService(settings)
    policy_summary = str(req.policy_summary or "").strip()
    if not policy_summary:
        knowledge = service.store.get_knowledge_artifact(session_id)
        if knowledge:
            policy_summary = str(knowledge.get("summary") or "").strip()
    if not policy_summary:
        raise HTTPException(status_code=422, detail="Policy summary is required to start a simulation.")

    payload = service.start_simulation(
        session_id,
        policy_summary=policy_summary,
        rounds=req.rounds,
        controversy_boost=req.controversy_boost,
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
        replay_events = demo_service.get_simulation_stream_events(session_id)

        def demo_sse_iter():
            for event in replay_events:
                if not isinstance(event, dict):
                    continue
                payload = dict(event)
                payload["session_id"] = session_id
                event_type = str(payload.get("event_type") or "event")
                data = json.dumps(payload)
                yield f"event: {event_type}\ndata: {data}\n\n"
            # Keep compatibility with existing demo stream terminator.
            yield f"event: completed\ndata: {json.dumps({'session_id': session_id, 'status': 'completed'})}\n\n"

        return StreamingResponse(demo_sse_iter(), media_type="text/event-stream")
    
    stream = SimulationStreamService(settings).sse_iter(session_id)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.get("/session/{session_id}/report", response_model=V2ReportResponse)
def v2_report(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> V2ReportResponse:
    try:
        payload = ConsoleService(settings).get_v2_report(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2ReportResponse(**payload)


@router.get("/session/{session_id}/report/export")
def v2_report_export(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    try:
        filename, payload = ConsoleService(settings).export_v2_report_docx(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@router.post("/session/{session_id}/chat/group", response_model=V2GroupChatResponse)
def v2_group_chat(
    session_id: str,
    req: dict[str, Any] = Body(...),
    settings: Settings = Depends(get_settings),
) -> V2GroupChatResponse:
    try:
        parsed = _parse_group_chat_request(req)
        payload = ConsoleService(settings).group_chat(
            session_id,
            segment=parsed.segment,
            message=parsed.message,
            top_n=parsed.top_n,
            metric_name=parsed.metric_name,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2GroupChatResponse(**payload)


@router.get("/session/{session_id}/chat/group/agents", response_model=V2GroupChatAgentsResponse)
def v2_group_chat_agents(
    session_id: str,
    segment: str = Query(...),
    top_n: int = Query(default=5, ge=1, le=20),
    metric_name: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> V2GroupChatAgentsResponse:
    try:
        payload = ConsoleService(settings).get_group_chat_candidates(
            session_id,
            segment=segment,
            top_n=top_n,
            metric_name=metric_name,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2GroupChatAgentsResponse(**payload)


@router.post("/session/{session_id}/chat/agent/{agent_id}", response_model=V2AgentChatResponse)
def v2_agent_chat(
    session_id: str,
    agent_id: str,
    req: V2AgentChatRequest,
    settings: Settings = Depends(get_settings),
) -> V2AgentChatResponse:
    try:
        payload = ConsoleService(settings).agent_chat_v2(session_id, agent_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2AgentChatResponse(**payload)


@router.get("/session/{session_id}/report/full", response_model=V2ReportResponse)
def report_full(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> V2ReportResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return V2ReportResponse(**report)

    return V2ReportResponse(**ConsoleService(settings).get_v2_report(session_id))


@router.post("/session/{session_id}/report/generate", response_model=V2ReportResponse)
def report_generate(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> V2ReportResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return V2ReportResponse(**report)

    return V2ReportResponse(**ConsoleService(settings).generate_v2_report(session_id))


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


@compat_router.post("/questions/generate-metadata")
def generate_question_metadata(
    req: dict[str, Any] = Body(...),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Generate metric metadata for a custom analysis question using LLM."""
    question = str(req.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=422, detail="'question' field is required.")
    try:
        from mckainsey.services.question_metadata_service import QuestionMetadataService
        service = QuestionMetadataService(settings)
        metadata = service.generate_metric_metadata_sync(question)
        return metadata
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@compat_router.get("/session/{session_id}/analysis-questions")
def get_analysis_questions(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get the analysis questions configured for a session's use case."""
    return ConsoleService(settings).get_session_analysis_questions(session_id)
