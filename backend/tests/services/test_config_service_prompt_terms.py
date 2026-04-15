from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.config_service import ConfigService


def test_render_prompt_template_uses_prompt_terms_from_use_case_yaml(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "system").mkdir(exist_ok=True)
    (prompts_dir / "my-custom-case.yaml").write_text(
        """
name: "Custom Case"
code: "my-custom-case"
prompt_terms:
  summary_label: "Campaign brief"
  summary_subject: "campaign concept"
  subject_components: "messages and claims"
  audience_label: "target audiences"
  evaluation_target: "the campaign concept"
""".strip()
    )

    service = ConfigService(
        Settings(
            simulation_db_path=str(tmp_path / "simulation.db"),
            config_prompts_dir=str(prompts_dir),
        )
    )

    rendered = service.render_prompt_template(
        "{summary_label} | {summary_subject} | {subject_components} | {audience_label} | {evaluation_target}",
        use_case_id="my-custom-case",
    )

    assert rendered == (
        "Campaign brief | campaign concept | messages and claims | "
        "target audiences | the campaign concept"
    )
