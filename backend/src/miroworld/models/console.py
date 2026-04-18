from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConsoleSessionCreateRequest(BaseModel):
    session_id: str | None = None
    mode: Literal["demo", "live"] = "demo"
    model_provider: Literal["google", "openrouter", "openai", "ollama"] | None = None
    model_name: str | None = None
    embed_model_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class ConsoleSessionResponse(BaseModel):
    session_id: str
    mode: Literal["demo", "live"]
    status: str
    model_provider: Literal["google", "openrouter", "openai", "ollama"]
    model_name: str
    embed_model_name: str
    base_url: str
    api_key_configured: bool
    api_key_masked: str | None = None


class ConsoleSessionModelConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_provider: Literal["google", "openrouter", "openai", "ollama"]
    model_name: str
    embed_model_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class ConsoleSessionModelConfigResponse(BaseModel):
    session_id: str
    model_provider: Literal["google", "openrouter", "openai", "ollama"]
    model_name: str
    embed_model_name: str
    base_url: str
    api_key_configured: bool
    api_key_masked: str | None = None


class ConsoleModelProviderResponse(BaseModel):
    id: Literal["google", "openrouter", "openai", "ollama"]
    label: str
    default_model: str
    default_embed_model: str
    default_base_url: str
    requires_api_key: bool


class ConsoleModelProviderCatalogResponse(BaseModel):
    providers: list[ConsoleModelProviderResponse]


class ConsoleModelOptionResponse(BaseModel):
    id: str
    label: str


class ConsoleProviderModelsResponse(BaseModel):
    provider: Literal["google", "openrouter", "openai", "ollama"]
    models: list[ConsoleModelOptionResponse]


class ConsoleKnowledgeProcessRequest(BaseModel):
    document_text: str | None = None
    source_path: str | None = None
    documents: list[dict[str, str | None]] = Field(default_factory=list)
    guiding_prompt: str | None = None
    demographic_focus: str | None = None
    use_default_demo_document: bool = False


class HostedAuthRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class KnowledgeArtifactResponse(BaseModel):
    session_id: str
    document: dict[str, Any]
    summary: str | None = None
    guiding_prompt: str | None = None
    entity_nodes: list[dict[str, Any]]
    relationship_edges: list[dict[str, Any]]
    entity_type_counts: dict[str, int]
    processing_logs: list[str]
    demographic_focus_summary: str | None = None


class PopulationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_count: int = Field(default=50, ge=2, le=500)
    sample_mode: Literal["affected_groups", "population_baseline"] = "affected_groups"
    sampling_instructions: str | None = None
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    planning_areas: list[str] = Field(default_factory=list)
    dynamic_filters: dict[str, Any] = Field(default_factory=dict)


class PopulationArtifactResponse(BaseModel):
    session_id: str
    candidate_count: int
    sample_count: int
    sample_mode: Literal["affected_groups", "population_baseline"]
    sample_seed: int
    parsed_sampling_instructions: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any]
    sampled_personas: list[dict[str, Any]]
    agent_graph: dict[str, Any]
    representativeness: dict[str, Any]
    selection_diagnostics: dict[str, Any] = Field(default_factory=dict)


class SimulationStartRequest(BaseModel):
    subject_summary: str
    rounds: int = Field(default=10, ge=1, le=30)
    controversy_boost: float = Field(default=0.0, ge=0.0, le=1.0)
    mode: Literal["demo", "live"] | None = None


class SimulationQuickStartRequest(BaseModel):
    subject_summary: str | None = None
    rounds: int = Field(default=10, ge=1, le=30)
    controversy_boost: float = Field(default=0.0, ge=0.0, le=1.0)
    mode: Literal["demo", "live"] | None = None


class SimulationStateResponse(BaseModel):
    session_id: str
    status: str
    event_count: int
    last_round: int
    platform: str | None = None
    planned_rounds: int | None = None
    current_round: int | None = None
    elapsed_seconds: int | None = None
    estimated_total_seconds: int | None = None
    estimated_remaining_seconds: int | None = None
    counters: dict[str, Any] = Field(default_factory=dict)
    checkpoint_status: dict[str, Any] = Field(default_factory=dict)
    top_threads: list[dict[str, Any]] = Field(default_factory=list)
    discussion_momentum: dict[str, Any] = Field(default_factory=dict)
    latest_metrics: dict[str, Any] = Field(default_factory=dict)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)


class V2ReportResponse(BaseModel):
    session_id: str
    status: str = "completed"
    generated_at: str | None = None
    executive_summary: str | None = None
    metric_deltas: list[dict[str, Any]] = Field(default_factory=list)
    quick_stats: dict[str, Any] = Field(default_factory=dict)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    insight_blocks: list[dict[str, Any]] = Field(default_factory=list)
    preset_sections: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class V2GroupChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment: Literal["supporter", "neutral", "dissenter", "engaged"]
    message: str = Field(min_length=3)
    top_n: int = Field(default=5, ge=1, le=20)
    metric_name: str | None = None


class V2GroupChatResponse(BaseModel):
    session_id: str
    segment: str
    responses: list[dict[str, Any]] = Field(default_factory=list)


class V2GroupChatAgentsResponse(BaseModel):
    session_id: str
    segment: str
    metric_name: str | None = None
    score_field: str
    agents: list[dict[str, Any]] = Field(default_factory=list)


class V2AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=3)


class V2AgentChatResponse(BaseModel):
    session_id: str
    agent_id: str
    response: str
    memory_used: bool
    model_provider: str
    model_name: str
    gemini_model: str | None = None
    zep_context_used: bool = False
    graphiti_context_used: bool = False
    memory_backend: str | None = None


class V2PolarizationResponse(BaseModel):
    session_id: str
    metric_name: str | None = None
    series: list[dict[str, Any]] = Field(default_factory=list)


class V2OpinionFlowResponse(BaseModel):
    session_id: str
    metric_name: str | None = None
    initial: dict[str, int] = Field(default_factory=dict)
    final: dict[str, int] = Field(default_factory=dict)
    flows: list[dict[str, Any]] = Field(default_factory=list)


class V2InfluenceResponse(BaseModel):
    session_id: str
    top_influencers: list[dict[str, Any]] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0


class V2CascadeResponse(BaseModel):
    session_id: str
    post_id: str | None = None
    tree_size: int = 0
    total_engagement: int = 0
    mean_opinion_delta: float = 0.0
    engaged_agents: list[str] = Field(default_factory=list)


class V2CountryResponse(BaseModel):
    name: str
    code: str
    flag_emoji: str
    dataset_path: str
    available: bool = True
    dataset_ready: bool = False
    download_required: bool = False
    download_status: str = "missing"
    download_error: str | None = None
    missing_dependency: str | None = None


class CountryDatasetStatusResponse(BaseModel):
    country: str
    dataset_ready: bool = False
    download_required: bool = False
    download_status: str = "missing"
    download_error: str | None = None
    missing_dependency: str | None = None
    resolved_dataset_path: str | None = None


class V2ProviderResponse(BaseModel):
    name: Literal["gemini", "openrouter", "openai", "ollama"]
    models: list[str] = Field(default_factory=list)
    requires_api_key: bool


class V2SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str
    provider: Literal["gemini", "google", "openrouter", "openai", "ollama"]
    model: str
    api_key: str | None = None
    use_case: str
    mode: Literal["demo", "live"] = "live"
    session_id: str | None = None


class V2SessionCreateResponse(BaseModel):
    session_id: str


class V2SessionConfigPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str | None = None
    use_case: str | None = None
    provider: Literal["gemini", "google", "openrouter", "openai", "ollama"] | None = None
    model: str | None = None
    api_key: str | None = None
    guiding_prompt: str | None = None
    analysis_questions: list[dict[str, Any]] | None = None


class V2SessionConfigResponse(BaseModel):
    session_id: str
    country: str | None = None
    use_case: str | None = None
    provider: Literal["gemini", "google", "openrouter", "openai", "ollama"] | None = None
    model: str | None = None
    api_key_configured: bool = False
    guiding_prompt: str | None = None
    analysis_questions: list[dict[str, Any]] = Field(default_factory=list)


class ConsoleScrapeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str


class ConsoleScrapeResponse(BaseModel):
    url: str
    title: str
    text: str
    length: int


class ConsoleDynamicFilterFieldResponse(BaseModel):
    field: str
    type: str
    label: str
    options: list[str] = Field(default_factory=list)
    min: int | float | None = None
    max: int | float | None = None
    default_min: int | float | None = None
    default_max: int | float | None = None
    default: str | list[str] | None = None


class ConsoleDynamicFiltersResponse(BaseModel):
    session_id: str
    country: str
    use_case: str | None = None
    filters: list[ConsoleDynamicFilterFieldResponse] = Field(default_factory=list)


class TokenUsageEstimateResponse(BaseModel):
    with_caching_usd: float
    without_caching_usd: float
    savings_pct: float
    model: str


class TokenUsageRuntimeResponse(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    estimated_cost_usd: float
    cost_without_caching_usd: float
    caching_savings_usd: float
    caching_savings_pct: float
    model: str
