from typing import Any

from pydantic import BaseModel, Field


class ReportResponse(BaseModel):
    simulation_id: str
    executive_summary: str
    approval_rates: dict[str, float]
    top_dissenting_demographics: list[dict[str, Any]]
    influential_agents: list[dict[str, Any]]
    key_arguments_for: list[dict[str, Any]]
    key_arguments_against: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]


class ReportChatRequest(BaseModel):
    simulation_id: str
    message: str = Field(min_length=3)


class ReportChatResponse(BaseModel):
    simulation_id: str
    response: str
