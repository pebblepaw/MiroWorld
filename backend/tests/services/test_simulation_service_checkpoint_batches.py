from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.simulation_service import SimulationService


def test_non_ollama_checkpoint_batches_default_to_ten(tmp_path: Path) -> None:
    service = SimulationService(Settings(simulation_db_path=str(tmp_path / "simulation.db"), llm_provider="google"))

    assert service._resolve_checkpoint_batch_size(total_agents=50) == 10


def test_ollama_checkpoint_batches_stay_small(tmp_path: Path) -> None:
    service = SimulationService(Settings(simulation_db_path=str(tmp_path / "simulation.db"), llm_provider="ollama"))

    assert service._resolve_checkpoint_batch_size(total_agents=50) == 3