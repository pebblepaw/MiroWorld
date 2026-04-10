from typing import Any

from pydantic import BaseModel, Field


class SyncMemoryRequest(BaseModel):
    simulation_id: str


class SyncMemoryResponse(BaseModel):
    simulation_id: str
    synced_events: int
    zep_enabled: bool
    external_sync_enabled: bool = False
    memory_backend: str = "sqlite"


class AgentMemoryResponse(BaseModel):
    simulation_id: str
    agent_id: str
    episodes: list[dict[str, Any]]


class AgentChatRequest(BaseModel):
    simulation_id: str
    agent_id: str
    message: str = Field(min_length=3)


class AgentChatResponse(BaseModel):
    simulation_id: str
    agent_id: str
    response: str
    memory_used: bool
