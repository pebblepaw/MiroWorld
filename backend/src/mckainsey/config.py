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

    # Provider-aware LLM settings.
    llm_provider: str = "ollama"
    llm_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    llm_embed_model: str = "nomic-embed-text"
    llm_api_key: str | None = None
    llm_base_url: str = "http://127.0.0.1:11434/v1/"
    llm_timeout_seconds: int = 20
    ollama_llm_timeout_seconds: int = 120
    llm_auto_pull_ollama_models: bool = True

    # Provider defaults used by the runtime model selector.
    ollama_default_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    ollama_default_embed_model: str = "nomic-embed-text"
    ollama_default_base_url: str = "http://127.0.0.1:11434/v1/"

    google_default_model: str = "gemini-2.5-flash-lite"
    google_default_embed_model: str = "gemini-embedding-001"
    google_default_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    openai_default_model: str = "gpt-5-mini"
    openai_default_embed_model: str = "text-embedding-3-small"
    openai_default_base_url: str = "https://api.openai.com/v1/"

    openrouter_default_model: str = "openai/gpt-5-mini"
    openrouter_default_embed_model: str = "openai/text-embedding-3-small"
    openrouter_default_base_url: str = "https://openrouter.ai/api/v1/"

    # Legacy and provider-specific key aliases.
    openai_api_key: str | None = None
    openai_api: str | None = None
    openrouter_api_key: str | None = None

    # The repo historically used GEMINI_API key names. We keep compatibility
    # aliases to avoid breaking existing local setup.
    gemini_api_key: str | None = None
    gemini_api: str | None = None
    gemini_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    gemini_embed_model: str = "nomic-embed-text"
    gemini_openai_base_url: str = "http://127.0.0.1:11434/v1/"
    gemini_timeout_seconds: int = 20

    lightrag_workdir: str = "data/lightrag"
    demo_default_policy_markdown: str = "Sample_Inputs/singapore_budget_ai_strategic_advantage.md"

    simulation_db_path: str = "data/simulation.db"
    default_agent_count: int = 50
    default_rounds: int = 10
    simulation_platform: str = "reddit"
    enable_real_oasis: bool = False
    oasis_python_bin: str = ".venv311/bin/python"
    oasis_runner_script: str = "scripts/oasis_reddit_runner.py"
    oasis_db_dir: str = "data/oasis"
    oasis_timeout_seconds: int = 1800
    oasis_ollama_timeout_per_agent_round_seconds: int = 12
    oasis_default_timeout_per_agent_round_seconds: int = 3
    oasis_ollama_semaphore: int = 12
    oasis_default_semaphore: int = 64
    oasis_sidecar_host: str | None = None
    oasis_sidecar_port: int = 8001
    ollama_checkpoint_batch_size: int = 3
    default_checkpoint_batch_size: int = 25
    oasis_run_log_dir: str = "data/oasis/logs"

    datagov_api_key: str | None = None
    planning_area_dataset_id: str = "d_4765db0e87b9c86336792efe8a1f7a66"
    planning_area_geojson_cache_path: str = "data/geo/planning_area_boundaries.geojson"
    config_countries_dir: str = "../config/countries"
    config_prompts_dir: str = "../config/prompts"

    frontend_dist_path: str = "../frontend/dist"
    console_demo_output_path: str = "data/demo-output.json"
    console_demo_frontend_output_path: str = "../frontend/public/demo-output.json"
    console_upload_dir: str = "data/uploads"
    simulation_stream_heartbeat_seconds: int = 5
    simulation_stream_replay_limit: int = 500

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        self.llm_provider = self._normalize_provider(self.llm_provider)
        self.llm_timeout_seconds = max(5, int(self.llm_timeout_seconds))
        self.ollama_llm_timeout_seconds = max(5, int(self.ollama_llm_timeout_seconds))
        self.oasis_timeout_seconds = max(120, int(self.oasis_timeout_seconds))
        self.oasis_ollama_timeout_per_agent_round_seconds = max(4, int(self.oasis_ollama_timeout_per_agent_round_seconds))
        self.oasis_default_timeout_per_agent_round_seconds = max(1, int(self.oasis_default_timeout_per_agent_round_seconds))
        self.oasis_ollama_semaphore = max(1, int(self.oasis_ollama_semaphore))
        self.oasis_default_semaphore = max(1, int(self.oasis_default_semaphore))
        self.oasis_sidecar_port = max(1, int(self.oasis_sidecar_port))
        self.ollama_checkpoint_batch_size = max(1, int(self.ollama_checkpoint_batch_size))
        self.default_checkpoint_batch_size = max(1, int(self.default_checkpoint_batch_size))

        # Keep legacy Gemini-named fields in sync so existing services continue
        # working while we roll out provider-aware runtime switching.
        self.gemini_model = self.llm_model
        self.gemini_embed_model = self.llm_embed_model
        self.gemini_openai_base_url = self._normalize_base_url(self.llm_base_url)
        self.gemini_timeout_seconds = self.llm_timeout_seconds

        if not self.gemini_api_key and self.llm_provider == "google":
            self.gemini_api_key = self.llm_api_key

        path_fields = [
            "lightrag_workdir",
            "demo_default_policy_markdown",
            "simulation_db_path",
            "oasis_python_bin",
            "oasis_runner_script",
            "oasis_db_dir",
            "oasis_run_log_dir",
            "planning_area_geojson_cache_path",
            "config_countries_dir",
            "config_prompts_dir",
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

    def _normalize_provider(self, provider: str | None) -> str:
        normalized = str(provider or "ollama").strip().lower()
        if normalized in {"gemini", "google-gemini"}:
            return "google"
        if normalized not in {"google", "openai", "openrouter", "ollama"}:
            return "ollama"
        return normalized

    def _normalize_base_url(self, base_url: str) -> str:
        cleaned = base_url.strip()
        if not cleaned.endswith("/"):
            cleaned = f"{cleaned}/"
        return cleaned

    def default_model_for_provider(self, provider: str) -> str:
        normalized = self._normalize_provider(provider)
        if normalized == "google":
            return self.google_default_model
        if normalized == "openai":
            return self.openai_default_model
        if normalized == "openrouter":
            return self.openrouter_default_model
        return self.ollama_default_model

    def default_embed_model_for_provider(self, provider: str) -> str:
        normalized = self._normalize_provider(provider)
        if normalized == "google":
            return self.google_default_embed_model
        if normalized == "openai":
            return self.openai_default_embed_model
        if normalized == "openrouter":
            return self.openrouter_default_embed_model
        return self.ollama_default_embed_model

    def default_base_url_for_provider(self, provider: str) -> str:
        normalized = self._normalize_provider(provider)
        if normalized == "google":
            return self._normalize_base_url(self.google_default_base_url)
        if normalized == "openai":
            return self._normalize_base_url(self.openai_default_base_url)
        if normalized == "openrouter":
            return self._normalize_base_url(self.openrouter_default_base_url)
        return self._normalize_base_url(self.ollama_default_base_url)

    def resolved_key_for_provider(self, provider: str) -> str | None:
        normalized = self._normalize_provider(provider)
        if normalized == "google":
            return self.gemini_api_key or self.gemini_api or self.llm_api_key
        if normalized == "openai":
            return self.openai_api_key or self.openai_api
        if normalized == "openrouter":
            return self.openrouter_api_key
        return self.llm_api_key or "ollama"

    @property
    def resolved_gemini_key(self) -> str | None:
        return self.resolved_key_for_provider(self.llm_provider)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
