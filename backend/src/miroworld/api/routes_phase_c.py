from fastapi import APIRouter, Depends, HTTPException

from miroworld.config import Settings, get_settings
from miroworld.models.phase_c import (
    AgentChatRequest,
    AgentChatResponse,
    AgentMemoryResponse,
    SyncMemoryRequest,
    SyncMemoryResponse,
)
from miroworld.services.memory_service import MemoryService

router = APIRouter(prefix="/api/v1/phase-c", tags=["phase-c"])


@router.post("/memory/sync", response_model=SyncMemoryResponse)
def sync_memory(
    req: SyncMemoryRequest,
    settings: Settings = Depends(get_settings),
) -> SyncMemoryResponse:
    result = MemoryService(settings).sync_simulation(req.simulation_id)
    return SyncMemoryResponse(**result)


@router.get("/memory/{simulation_id}/{agent_id}", response_model=AgentMemoryResponse)
def get_agent_memory(
    simulation_id: str,
    agent_id: str,
    settings: Settings = Depends(get_settings),
) -> AgentMemoryResponse:
    episodes = MemoryService(settings).get_agent_memory(simulation_id, agent_id)
    return AgentMemoryResponse(simulation_id=simulation_id, agent_id=agent_id, episodes=episodes)


@router.post("/chat/agent", response_model=AgentChatResponse)
def agent_chat(
    req: AgentChatRequest,
    settings: Settings = Depends(get_settings),
) -> AgentChatResponse:
    try:
        result = MemoryService(settings).agent_chat(req.simulation_id, req.agent_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AgentChatResponse(**result)
