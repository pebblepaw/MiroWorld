from fastapi import APIRouter, Depends, HTTPException

from miroworld.config import Settings, get_settings
from miroworld.models.phase_b import (
    SimulationRunRequest,
    SimulationRunResponse,
    SimulationSnapshotResponse,
)
from miroworld.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/v1/phase-b", tags=["phase-b"])


@router.post("/simulations/run", response_model=SimulationRunResponse)
def run_simulation(
    req: SimulationRunRequest,
    settings: Settings = Depends(get_settings),
) -> SimulationRunResponse:
    try:
        payload = SimulationService(settings).run(req)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SimulationRunResponse(**payload)


@router.get("/simulations/{simulation_id}", response_model=SimulationSnapshotResponse)
def get_snapshot(
    simulation_id: str,
    settings: Settings = Depends(get_settings),
) -> SimulationSnapshotResponse:
    try:
        payload = SimulationService(settings).snapshot(simulation_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SimulationSnapshotResponse(**payload)
