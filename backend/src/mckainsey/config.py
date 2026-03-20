from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "McKAInsey API"
    nemotron_dataset: str = "nvidia/Nemotron-Personas-Singapore"
    nemotron_split: str = "train"
    nemotron_cache_dir: str = "data/nemotron"
    nemotron_download_workers: int = 4

    # The repo currently uses GEMINI_API and ZEP_CLOUD key names. We support
    # both legacy and canonical names to avoid breaking existing local setup.
    gemini_api_key: str | None = None
    gemini_api: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_openai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_timeout_seconds: int = 20

    zep_api_key: str | None = None
    zep_cloud: str | None = None

    lightrag_workdir: str = "data/lightrag"
    demo_default_policy_markdown: str = "Sample_Inputs/fy2026_budget_statement.md"

    simulation_db_path: str = "data/simulation.db"
    default_agent_count: int = 50
    default_rounds: int = 10
    simulation_platform: str = "reddit"
    enable_real_oasis: bool = False
    oasis_python_bin: str = ".venv311/bin/python"
    oasis_runner_script: str = "scripts/oasis_reddit_runner.py"
    oasis_db_dir: str = "data/oasis"
    oasis_timeout_seconds: int = 1800
    oasis_run_log_dir: str = "data/oasis/logs"

    datagov_api_key: str | None = None
    planning_area_dataset_id: str = "d_4765db0e87b9c86336792efe8a1f7a66"
    planning_area_geojson_cache_path: str = "data/geo/planning_area_boundaries.geojson"

    frontend_dist_path: str = "../frontend/dist"
    console_demo_output_path: str = "data/demo-output.json"
    console_demo_frontend_output_path: str = "../frontend/public/demo-output.json"
    console_upload_dir: str = "data/uploads"
    simulation_stream_heartbeat_seconds: int = 5
    simulation_stream_replay_limit: int = 500

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        path_fields = [
            "lightrag_workdir",
            "demo_default_policy_markdown",
            "simulation_db_path",
            "oasis_python_bin",
            "oasis_runner_script",
            "oasis_db_dir",
            "oasis_run_log_dir",
            "planning_area_geojson_cache_path",
            "frontend_dist_path",
            "console_demo_output_path",
            "console_demo_frontend_output_path",
            "console_upload_dir",
            "nemotron_cache_dir",
        ]
        for field in path_fields:
            value = getattr(self, field)
            if not value:
                continue
            path = Path(value)
            if not path.is_absolute():
                setattr(self, field, str((BACKEND_DIR / path).resolve()))

    @property
    def resolved_gemini_key(self) -> str | None:
        return self.gemini_api_key or self.gemini_api

    @property
    def resolved_zep_key(self) -> str | None:
        return self.zep_api_key or self.zep_cloud


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
