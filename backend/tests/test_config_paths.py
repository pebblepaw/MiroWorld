from pathlib import Path

from mckainsey.config import Settings


def test_settings_resolve_relative_paths_from_backend_dir(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    expected_db_path = backend_dir / "data" / "simulation.db"
    expected_lightrag = backend_dir / "data" / "lightrag"
    expected_demo = backend_dir / "data" / "demo-output.json"

    monkeypatch.chdir(repo_root)
    root_settings = Settings()

    monkeypatch.chdir(backend_dir)
    backend_settings = Settings()

    assert Path(root_settings.simulation_db_path) == expected_db_path
    assert Path(backend_settings.simulation_db_path) == expected_db_path
    assert Path(root_settings.lightrag_workdir) == expected_lightrag
    assert Path(backend_settings.lightrag_workdir) == expected_lightrag
    assert Path(root_settings.console_demo_output_path) == expected_demo
    assert Path(backend_settings.console_demo_output_path) == expected_demo
