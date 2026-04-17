import json
from io import BytesIO
import time
from typing import Any

import requests
from fastapi import APIRouter, Body, Cookie, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from miroworld.config import Settings, get_settings
from miroworld.models.console import (
    CountryDatasetStatusResponse,
    ConsoleDynamicFiltersResponse,
    ConsoleKnowledgeProcessRequest,
    ConsoleModelProviderCatalogResponse,
    ConsoleProviderModelsResponse,
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
    KnowledgeArtifactResponse,
    PopulationArtifactResponse,
    PopulationPreviewRequest,
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
from miroworld.services.config_service import ConfigService
from miroworld.services.console_service import ConsoleService
from miroworld.services.country_dataset_service import CountryDatasetService
from miroworld.services.demo_service import DemoService
from miroworld.services.knowledge_stream_service import KnowledgeStreamService
from miroworld.services.scrape_service import ScrapeService
from miroworld.services.simulation_stream_service import SimulationStreamService
from miroworld.services.storage import SimulationStore, reset_store_user_context, set_store_user_context


router = APIRouter(prefix="/api/v2/console", tags=["console"])
compat_router = APIRouter(prefix="/api/v2", tags=["console-compat"])
HOSTED_AUTH_COOKIE = "miroworld_hosted_auth"
AUTH_CACHE_TTL_SECONDS = 60
_AUTH_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _is_demo_session(session_id: str, settings: Settings) -> bool:
    """Check if session is in demo mode."""
    store = SimulationStore(settings.simulation_db_path)
    session = store.get_console_session(session_id)
    return session is not None and session.get("mode") == "demo"


def _get_demo_service(settings: Settings) -> DemoService:
    """Get demo service instance."""
    return DemoService(settings)


def _request_has_explicit_live_knowledge_input(req: ConsoleKnowledgeProcessRequest) -> bool:
    if str(req.document_text or "").strip():
        return True
    if str(req.source_path or "").strip():
        return True
    return any(
        isinstance(item, dict)
        and (str(item.get("document_text") or "").strip() or str(item.get("source_path") or "").strip())
        for item in (req.documents or [])
    )


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


def _extract_bearer_token(authorization: str | None) -> str | None:
    value = str(authorization or "").strip()
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer":
        return None
    cleaned = token.strip()
    return cleaned or None


def _verify_supabase_user(token: str, settings: Settings) -> dict[str, Any]:
    cached = _AUTH_CACHE.get(token)
    now = time.time()
    if cached and cached[0] > now:
        return dict(cached[1])

    base_url = str(settings.supabase_url or "").rstrip("/")
    api_key = str(settings.supabase_publishable_key or settings.supabase_service_role_key or "").strip()
    if not base_url or not api_key:
        raise HTTPException(status_code=503, detail="Hosted auth is enabled but Supabase auth settings are incomplete.")

    response = requests.get(
        f"{base_url}/auth/v1/user",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {token}",
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Supabase authentication failed.")

    payload = response.json()
    _AUTH_CACHE[token] = (now + AUTH_CACHE_TTL_SECONDS, payload)
    return payload


def _require_known_session(session_id: str, settings: Settings) -> None:
    session = SimulationStore(settings.simulation_db_path).get_console_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")


def require_hosted_user(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
    hosted_auth_cookie: str | None = Cookie(default=None, alias=HOSTED_AUTH_COOKIE),
):
    if not settings.hosted_auth_enabled:
        yield None
        return

    token = _extract_bearer_token(authorization) or str(hosted_auth_cookie or "").strip() or None
    if not token:
        response.delete_cookie(HOSTED_AUTH_COOKIE, path="/")
        raise HTTPException(status_code=401, detail="Hosted auth requires a valid Supabase bearer token.")

    payload = _verify_supabase_user(token, settings)
    user_id = str(payload.get("id") or payload.get("sub") or "").strip()
    if not user_id:
        response.delete_cookie(HOSTED_AUTH_COOKIE, path="/")
        raise HTTPException(status_code=401, detail="Supabase authentication did not return a user id.")

    response.set_cookie(
        HOSTED_AUTH_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
        max_age=3600,
    )
    token_ctx = set_store_user_context(user_id)
    try:
        yield user_id
    finally:
        try:
            reset_store_user_context(token_ctx)
        except ValueError:
            # FastAPI may finalize sync generator dependencies in a different
            # worker context. The request middleware still clears the scope.
            pass


@compat_router.get("/countries", response_model=list[V2CountryResponse])
def v2_countries(settings: Settings = Depends(get_settings)) -> list[V2CountryResponse]:
    config_service = ConfigService(settings)
    dataset_service = CountryDatasetService(settings)
    rows = []
    for country in config_service.list_countries():
        code = str(country.get("code", "")).strip().lower()
        status = dataset_service.country_status(code) if code else {}
        rows.append(
            V2CountryResponse(
                name=str(country.get("name", "")),
                code=code,
                flag_emoji=str(country.get("flag_emoji", "")),
                dataset_path=str(country.get("dataset_path", "")),
                available=bool(country.get("available", True)),
                dataset_ready=bool(status.get("dataset_ready", False)),
                download_required=bool(status.get("download_required", False)),
                download_status=str(status.get("download_status", "missing")),
                download_error=status.get("download_error"),
                missing_dependency=status.get("missing_dependency"),
            )
        )
    return rows


@compat_router.get("/countries/{country}/ui-config")
def v2_country_ui_config(
    country: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    config_service = ConfigService(settings)
    try:
        payload = config_service.get_country(country)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Country not found: {country}")
    return dict(payload.get("ui") or {})


@compat_router.post("/countries/{country}/download", response_model=CountryDatasetStatusResponse)
def v2_country_download(
    country: str,
    settings: Settings = Depends(get_settings),
) -> CountryDatasetStatusResponse:
    payload = CountryDatasetService(settings).start_download(country)
    return CountryDatasetStatusResponse(country=country, **payload)


@compat_router.get("/countries/{country}/download-status", response_model=CountryDatasetStatusResponse)
def v2_country_download_status(
    country: str,
    settings: Settings = Depends(get_settings),
) -> CountryDatasetStatusResponse:
    payload = CountryDatasetService(settings).download_status(country)
    return CountryDatasetStatusResponse(country=country, **payload)


@compat_router.get("/providers", response_model=list[V2ProviderResponse])
def v2_providers(settings: Settings = Depends(get_settings)) -> list[V2ProviderResponse]:
    payload = ConsoleService(settings).v2_provider_catalog()
    return [V2ProviderResponse(**row) for row in payload]


@compat_router.post("/session/create", response_model=V2SessionCreateResponse)
def v2_session_create(
    req: V2SessionCreateRequest,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
) -> ConsoleSessionModelConfigResponse:
    payload = ConsoleService(settings).get_session_model_config(session_id)
    return ConsoleSessionModelConfigResponse(**payload)


@router.put("/session/{session_id}/model", response_model=ConsoleSessionModelConfigResponse)
def update_session_model(
    session_id: str,
    req: ConsoleSessionModelConfigRequest,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
) -> KnowledgeArtifactResponse:
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
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


@router.get("/session/{session_id}/knowledge/stream")
def knowledge_stream(
    session_id: str,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> StreamingResponse:
    _require_known_session(session_id, settings)
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        knowledge = demo_service.get_knowledge_artifact(session_id) or {}

        def demo_sse_iter():
            yield (
                "event: knowledge_completed\n"
                f"data: {json.dumps({'session_id': session_id, 'document_count': 1, 'total_nodes': len(knowledge.get('entity_nodes', [])), 'total_edges': len(knowledge.get('relationship_edges', []))}, ensure_ascii=False)}\n\n"
            )

        return StreamingResponse(demo_sse_iter(), media_type="text/event-stream")

    stream = KnowledgeStreamService(settings).sse_iter(session_id)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.put("/session/{session_id}/knowledge")
def inject_knowledge(
    session_id: str,
    artifact: dict[str, Any] = Body(...),
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> KnowledgeArtifactResponse:
    """Inject a pre-built knowledge artifact into a session (for cache replay)."""
    _require_known_session(session_id, settings)
    store = SimulationStore(settings.simulation_db_path)
    artifact["session_id"] = session_id
    store.save_knowledge_artifact(session_id, artifact)
    return KnowledgeArtifactResponse(**artifact)


@router.post("/session/{session_id}/scrape", response_model=ConsoleScrapeResponse)
def scrape_document(
    session_id: str,
    req: ConsoleScrapeRequest,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> ConsoleScrapeResponse:
    _require_known_session(session_id, settings)
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
) -> TokenUsageRuntimeResponse:
    payload = ConsoleService(settings).get_runtime_token_usage(session_id)
    return TokenUsageRuntimeResponse(**payload)


@router.post("/session/{session_id}/sampling/preview", response_model=PopulationArtifactResponse)
def preview_population(
    session_id: str,
    req: PopulationPreviewRequest,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
        subject_summary=req.subject_summary,
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
    _user_id: str | None = Depends(require_hosted_user),
) -> SimulationStateResponse:
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)

    service = ConsoleService(settings)
    subject_summary = str(req.subject_summary or "").strip()
    if not subject_summary:
        knowledge = service.store.get_knowledge_artifact(session_id)
        if knowledge:
            subject_summary = str(knowledge.get("summary") or "").strip()
    if not subject_summary:
        raise HTTPException(status_code=422, detail="Subject summary is required to start a simulation.")

    payload = service.start_simulation(
        session_id,
        subject_summary=subject_summary,
        rounds=req.rounds,
        controversy_boost=req.controversy_boost,
        mode=req.mode,
    )
    return SimulationStateResponse(**payload)


@router.get("/session/{session_id}/simulation/stream")
def simulation_stream(
    session_id: str,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> StreamingResponse:
    _require_known_session(session_id, settings)
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
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
    _user_id: str | None = Depends(require_hosted_user),
) -> V2AgentChatResponse:
    try:
        payload = ConsoleService(settings).agent_chat_v2(session_id, agent_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2AgentChatResponse(**payload)


@router.post("/session/{session_id}/report/generate", response_model=V2ReportResponse)
def report_generate(
    session_id: str,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> V2ReportResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return V2ReportResponse(**report)

    return V2ReportResponse(**ConsoleService(settings).generate_v2_report(session_id))


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
        from miroworld.services.question_metadata_service import QuestionMetadataService
        service = QuestionMetadataService(settings)
        metadata = service.generate_metric_metadata_sync(question)
        return metadata
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@compat_router.get("/session/{session_id}/analysis-questions")
def get_analysis_questions(
    session_id: str,
    settings: Settings = Depends(get_settings),
    _user_id: str | None = Depends(require_hosted_user),
) -> dict[str, Any]:
    """Get the analysis questions configured for a session's use case."""
    return ConsoleService(settings).get_session_analysis_questions(session_id)
