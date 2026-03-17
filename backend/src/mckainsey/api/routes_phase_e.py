from fastapi import APIRouter, Depends

from mckainsey.config import Settings, get_settings
from mckainsey.services.report_service import ReportService
from mckainsey.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/v1/phase-e", tags=["phase-e"])


@router.get("/dashboard/{simulation_id}")
def dashboard_payload(
    simulation_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    snapshot = SimulationService(settings).snapshot(simulation_id)
    report = ReportService(settings).build_report(simulation_id)

    friction_map = [
        {
            "planning_area": item["planning_area"],
            "friction": round((1 - item["avg_post_opinion"] / 10.0), 4),
        }
        for item in report["top_dissenting_demographics"]
    ]

    return {
        "simulation": snapshot,
        "report": report,
        "friction_map": friction_map,
    }
