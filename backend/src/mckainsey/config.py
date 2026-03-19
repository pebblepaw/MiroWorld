from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "McKAInsey API"
    nemotron_dataset: str = "nvidia/Nemotron-Personas-Singapore"
    nemotron_split: str = "train"

    # The repo currently uses GEMINI_API and ZEP_CLOUD key names. We support
    # both legacy and canonical names to avoid breaking existing local setup.
    gemini_api_key: str | None = None
    gemini_api: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_openai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

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

    @property
    def resolved_gemini_key(self) -> str | None:
        return self.gemini_api_key or self.gemini_api

    @property
    def resolved_zep_key(self) -> str | None:
        return self.zep_api_key or self.zep_cloud


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
