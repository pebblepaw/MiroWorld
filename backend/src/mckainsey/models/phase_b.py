from typing import Any

from pydantic import BaseModel, Field


class SimulationRunRequest(BaseModel):
    simulation_id: str
    policy_summary: str
    agent_count: int = Field(default=50, ge=2, le=500)
    rounds: int = Field(default=10, ge=1, le=30)
    min_age: int | None = Field(default=None, ge=0, le=120)
    max_age: int | None = Field(default=None, ge=0, le=120)
    planning_areas: list[str] = Field(default_factory=list)
    income_brackets: list[str] = Field(default_factory=list)


class SimulationRunResponse(BaseModel):
    simulation_id: str
    platform: str
    agent_count: int
    rounds: int
    stage3a_approval_rate: float
    stage3b_approval_rate: float
    net_opinion_shift: float
    sqlite_path: str


class SimulationSnapshotResponse(BaseModel):
    simulation_id: str
    stats: dict[str, Any]
    stage3a_scores: list[float]
    stage3b_scores: list[float]
    top_posts: list[dict[str, Any]]
