from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from miroworld.config import Settings
from miroworld.services.country_metadata_service import CountryMetadataService


def _make_settings(tmp_path: Path) -> Settings:
    countries_dir = tmp_path / "countries"
    countries_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        config_countries_dir=str(countries_dir),
    )


def _write_country(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def test_normalize_geography_values_uses_yaml_state_aliases(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _write_country(
        Path(settings.config_countries_dir) / "usa.yaml",
        """
        name: "United States"
        code: "usa"
        dataset:
          local_paths: ["backend/data/nemotron/usa/data/train-*.parquet"]
          repo_id: "nvidia/Nemotron-Personas-USA"
          download_dir: "backend/data/nemotron/usa"
          required_columns: ["state"]
          country_values: ["usa", "us", "united states"]
        geography:
          field: "state"
          label: "State"
          values:
            - code: "WA"
              label: "Washington"
              aliases: ["washington", "wa", "washington state"]
            - code: "CA"
              label: "California"
              aliases: ["california", "ca"]
        filterable_columns:
          - field: "state"
            type: "categorical"
        """,
    )

    service = CountryMetadataService(settings)

    assert service.geography_field("usa") == "state"
    assert service.normalize_geography_values("usa", ["Washington", "wa"]) == ["WA"]
    assert service.display_geography_value("usa", "WA") == "Washington"


def test_normalize_geography_values_expands_yaml_groups_for_singapore(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _write_country(
        Path(settings.config_countries_dir) / "singapore.yaml",
        """
        name: "Singapore"
        code: "sg"
        dataset:
          local_paths: ["backend/data/nemotron/singapore/data/train-*.parquet"]
          repo_id: "nvidia/Nemotron-Personas-Singapore"
          download_dir: "backend/data/nemotron/singapore"
          required_columns: ["planning_area"]
          country_values: ["singapore", "sg"]
        geography:
          field: "planning_area"
          label: "Planning Area"
          values:
            - code: "Hougang"
              label: "Hougang"
              aliases: ["hougang"]
            - code: "Sengkang"
              label: "Sengkang"
              aliases: ["sengkang"]
          groups:
            - code: "north-east"
              label: "North-East"
              aliases: ["north-east", "north east", "northeast"]
              members: ["Hougang", "Sengkang"]
        filterable_columns:
          - field: "planning_area"
            type: "categorical"
        """,
    )

    service = CountryMetadataService(settings)

    assert service.geography_field("singapore") == "planning_area"
    assert service.normalize_geography_values("singapore", ["north east"]) == ["Hougang", "Sengkang"]
    assert service.display_geography_value("singapore", "Hougang") == "Hougang"
