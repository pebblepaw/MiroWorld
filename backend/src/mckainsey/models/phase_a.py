from typing import Any

from pydantic import BaseModel, Field


class PersonaFilterRequest(BaseModel):
    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    planning_areas: list[str] = Field(default_factory=list)
    income_brackets: list[str] = Field(default_factory=list)
    limit: int = Field(default=200, ge=1, le=1000)
    mode: str = Field(default="stream", description="stream|duckdb")


class PersonaSampleResponse(BaseModel):
    mode: str
    count: int
    personas: list[dict[str, Any]]


class KnowledgeProcessRequest(BaseModel):
    simulation_id: str
    document_text: str | None = None
    source_path: str | None = None
    demographic_focus: str | None = None
    use_default_demo_document: bool = False


class KnowledgeProcessResponse(BaseModel):
    simulation_id: str
    document_id: str
    summary: str
    demographic_context: str | None = None
