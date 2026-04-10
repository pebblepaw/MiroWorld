from __future__ import annotations

from pathlib import Path

from mckainsey.config import Settings
from mckainsey.services.simulation_service import SimulationService


class _Response:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload


def test_run_oasis_with_inputs_uses_sidecar_jobs_when_configured(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        llm_provider="google",
        llm_model="gemini-2.5-flash-lite",
        llm_embed_model="gemini-embedding-001",
        llm_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        gemini_api_key="test-gemini-key",
        enable_real_oasis=True,
        oasis_runner_script=str(tmp_path / "missing-runner.py"),
        oasis_python_bin=str(tmp_path / "missing-python"),
        oasis_db_dir=str(tmp_path / "oasis"),
        oasis_run_log_dir=str(tmp_path / "logs"),
        simulation_db_path=str(tmp_path / "simulation.db"),
        oasis_sidecar_host="oasis-sidecar",
        oasis_sidecar_port=8001,
    )

    post_calls: list[tuple[str, dict[str, object], int]] = []
    get_calls: list[tuple[str, int]] = []
    delete_calls: list[tuple[str, int]] = []
    poll_responses = iter(
        [
            _Response(200, {"job_id": "job-123", "status": "running"}),
            _Response(
                200,
                {
                    "job_id": "job-123",
                    "status": "completed",
                    "result": {
                        "simulation_id": "sim-sidecar",
                        "agents": [],
                        "interactions": [],
                        "stage3a_approval_rate": 0.0,
                        "stage3b_approval_rate": 0.0,
                        "net_opinion_shift": 0.0,
                        "runtime": "oasis",
                    },
                },
            ),
        ]
    )

    def fake_post(url: str, json: dict[str, object], timeout: int) -> _Response:
        post_calls.append((url, json, timeout))
        return _Response(202, {"job_id": "job-123", "status": "running"})

    def fake_get(url: str, timeout: int) -> _Response:
        get_calls.append((url, timeout))
        return next(poll_responses)

    def fake_delete(url: str, timeout: int) -> _Response:
        delete_calls.append((url, timeout))
        return _Response(200, {"job_id": "job-123", "status": "cancelled"})

    monkeypatch.setattr("mckainsey.services.simulation_service.requests.post", fake_post)
    monkeypatch.setattr("mckainsey.services.simulation_service.requests.get", fake_get)
    monkeypatch.setattr("mckainsey.services.simulation_service.requests.delete", fake_delete)
    monkeypatch.setattr("mckainsey.services.simulation_service.time.sleep", lambda _: None)

    service = object.__new__(SimulationService)
    service.settings = settings

    result = service._run_oasis_with_inputs(
        simulation_id="sim-sidecar",
        policy_summary="AI strategy policy summary",
        rounds=1,
        personas=[{"agent_id": "agent-0001", "planning_area": "Yishun"}],
        events_path=None,
    )

    assert result["simulation_id"] == "sim-sidecar"
    assert result["runtime"] == "oasis"
    assert delete_calls == []
    assert post_calls[0][0] == "http://oasis-sidecar:8001/jobs"
    assert get_calls[-1][0] == "http://oasis-sidecar:8001/jobs/job-123"