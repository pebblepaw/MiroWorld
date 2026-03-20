from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConsoleSessionCreateRequest(BaseModel):
    session_id: str | None = None
    mode: Literal["demo", "live"] = "demo"


class ConsoleSessionResponse(BaseModel):
    session_id: str
    mode: Literal["demo", "live"]
    status: str


class ConsoleKnowledgeProcessRequest(BaseModel):
    document_text: str | None = None
    source_path: str | None = None
    guiding_prompt: str | None = None
    demographic_focus: str | None = None
    use_default_demo_document: bool = False


class KnowledgeArtifactResponse(BaseModel):
    session_id: str
    document: dict[str, Any]
    summary: str
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
    policy_summary: str
    rounds: int = Field(default=10, ge=1, le=30)
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


class ReportFullResponse(BaseModel):
    session_id: str
    status: str
    generated_at: str | None = None
    executive_summary: str | None = None
    insight_cards: list[dict[str, Any]] = Field(default_factory=list)
    support_themes: list[dict[str, Any]] = Field(default_factory=list)
    dissent_themes: list[dict[str, Any]] = Field(default_factory=list)
    demographic_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    influential_content: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ReportOpinionsResponse(BaseModel):
    session_id: str
    feed: list[dict[str, Any]]
    influential_agents: list[dict[str, Any]]


class ReportFrictionMapResponse(BaseModel):
    session_id: str
    map_metrics: list[dict[str, Any]]
    anomaly_summary: str


class InteractionHubResponse(BaseModel):
    session_id: str
    selected_agent_id: str | None = None
    report_agent: dict[str, Any]
    influential_agents: list[dict[str, Any]]
    selected_agent: dict[str, Any] | None = None


class ConsoleReportChatRequest(BaseModel):
    message: str = Field(min_length=3)


class ConsoleReportChatResponse(BaseModel):
    session_id: str
    response: str
    gemini_model: str
    zep_context_used: bool


class ConsoleAgentChatRequest(BaseModel):
    agent_id: str
    message: str = Field(min_length=3)


class ConsoleAgentChatResponse(BaseModel):
    session_id: str
    agent_id: str
    response: str
    memory_used: bool
    gemini_model: str
    zep_context_used: bool
