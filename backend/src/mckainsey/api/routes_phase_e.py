from fastapi import APIRouter, Depends

from mckainsey.config import Settings, get_settings
from mckainsey.services.geo_service import PlanningAreaGeoService
from mckainsey.services.report_service import ReportService
from mckainsey.services.simulation_service import SimulationService
from mckainsey.services.storage import SimulationStore

router = APIRouter(prefix="/api/v1/phase-e", tags=["phase-e"])


@router.get("/dashboard/{simulation_id}")
def dashboard_payload(
    simulation_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    snapshot = SimulationService(settings).snapshot(simulation_id)
    report = ReportService(settings).build_report(simulation_id)
    store = SimulationStore(settings.simulation_db_path)
    agents = store.get_agents(simulation_id)

    by_area: dict[str, list[float]] = {}
    for agent in agents:
        area = str(agent["persona"].get("planning_area", "Unknown"))
        by_area.setdefault(area, []).append(float(agent.get("opinion_post", 0)))

    heatmap_matrix = []
    for area, scores in sorted(by_area.items()):
        avg_score = sum(scores) / max(len(scores), 1)
        heatmap_matrix.append(
            {
                "planning_area": area,
                "friction": round(1 - (avg_score / 10.0), 4),
                "avg_post_opinion": round(avg_score, 4),
                "cohort_size": len(scores),
            }
        )

    friction_map = [
        {
            "planning_area": item["planning_area"],
            "friction": item["friction"],
        }
        for item in heatmap_matrix
    ]

    def bucket(score: float) -> str:
        if score <= 3:
            return "Strongly Oppose"
        if score <= 5:
            return "Oppose"
        if score <= 6:
            return "Neutral"
        if score <= 8:
            return "Support"
        return "Strongly Support"

    links_count: dict[tuple[str, str], int] = {}
    for pre, post in zip(snapshot["stage3a_scores"], snapshot["stage3b_scores"]):
        key = (f"Stage3a {bucket(float(pre))}", f"Stage3b {bucket(float(post))}")
        links_count[key] = links_count.get(key, 0) + 1

    buckets = ["Strongly Oppose", "Oppose", "Neutral", "Support", "Strongly Support"]
    nodes = [{"name": f"Stage3a {name}"} for name in buckets] + [{"name": f"Stage3b {name}"} for name in buckets]
    opinion_flow = {
        "nodes": nodes,
        "links": [
            {"source": src, "target": dst, "value": count}
            for (src, dst), count in sorted(links_count.items(), key=lambda x: x[1], reverse=True)
        ],
    }

    return {
        "simulation": snapshot,
        "report": report,
        "friction_map": friction_map,
        "heatmap_matrix": heatmap_matrix,
        "opinion_flow": opinion_flow,
    }


@router.get("/geo/planning-areas")
def planning_area_geojson(
    force_refresh: bool = False,
    settings: Settings = Depends(get_settings),
) -> dict:
    return PlanningAreaGeoService(settings).get_geojson(force_refresh=force_refresh)
