"""Service for generating metric metadata for user-defined analysis questions.

When a user adds or edits a custom analysis question on Screen 1,
this service calls the LLM to infer a type, metric_name, metric_label,
metric_unit, threshold, report_title, and tooltip.
"""
from __future__ import annotations

import json
from typing import Any

from mckainsey.config import Settings
from mckainsey.services.llm_client import GeminiChatClient


_METADATA_PROMPT_TEMPLATE = """\
Given this analysis question that will be asked to simulated agents:
"{question}"

Generate the following metadata as JSON:
- type: "scale" if the question asks for a 1-10 rating, "yes-no" if it asks yes/no, "open-ended" otherwise
- metric_name: a snake_case identifier (e.g., "approval_rate")
- metric_label: a short human-readable label (e.g., "Approval Rate")
- metric_unit: "%" if measuring a percentage of agents, "/10" if measuring a mean score, "text" if qualitative
- threshold: if type is "scale" and metric_unit is "%", suggest a reasonable threshold (usually 7)
- threshold_direction: "gte" (default)
- report_title: a concise section title for the report
- tooltip: a one-sentence explanation of how this metric is computed

Return valid JSON only.
"""


class QuestionMetadataService:
    """Generates metric metadata for user-defined analysis questions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = GeminiChatClient(settings)

    async def generate_metric_metadata(self, question_text: str) -> dict[str, Any]:
        """Calls LLM to generate type, metric_name, metric_label, etc."""
        prompt = _METADATA_PROMPT_TEMPLATE.format(question=question_text.strip())
        try:
            raw = self.llm.complete_required(
                prompt,
                system_prompt=(
                    "You are a metric schema designer. Return valid JSON only "
                    "with the exact keys requested. No markdown fences."
                ),
            )
            parsed = _parse_json_object(raw)
        except Exception:  # noqa: BLE001
            # Fallback: return an open-ended metadata stub
            parsed = self._fallback_metadata(question_text)
        return self._normalize(parsed, question_text)

    def generate_metric_metadata_sync(self, question_text: str) -> dict[str, Any]:
        """Synchronous variant of generate_metric_metadata."""
        prompt = _METADATA_PROMPT_TEMPLATE.format(question=question_text.strip())
        try:
            raw = self.llm.complete_required(
                prompt,
                system_prompt=(
                    "You are a metric schema designer. Return valid JSON only "
                    "with the exact keys requested. No markdown fences."
                ),
            )
            parsed = _parse_json_object(raw)
        except Exception:  # noqa: BLE001
            parsed = self._fallback_metadata(question_text)
        return self._normalize(parsed, question_text)

    def validate_question(self, question: dict[str, Any]) -> bool:
        """Validates that a question has all required fields."""
        required = {"question", "type", "metric_name", "report_title"}
        return all(question.get(key) for key in required)

    def _fallback_metadata(self, question_text: str) -> dict[str, Any]:
        slug = question_text[:40].strip().lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        metric_name = "_".join(slug.split()[:4]) or "custom_metric"
        return {
            "type": "open-ended",
            "metric_name": metric_name,
            "metric_label": "",
            "metric_unit": "text",
            "report_title": question_text[:60],
            "tooltip": f"Qualitative analysis based on: {question_text[:80]}",
        }

    def _normalize(self, parsed: dict[str, Any], question_text: str) -> dict[str, Any]:
        q_type = str(parsed.get("type", "open-ended")).strip().lower()
        if q_type not in {"scale", "yes-no", "open-ended"}:
            q_type = "open-ended"

        result: dict[str, Any] = {
            "question": question_text.strip(),
            "type": q_type,
            "metric_name": str(parsed.get("metric_name", "custom_metric")).strip(),
            "report_title": str(parsed.get("report_title", question_text[:60])).strip(),
            "tooltip": str(parsed.get("tooltip", "")).strip(),
        }

        # Only include metric fields for quantitative types
        if q_type in {"scale", "yes-no"}:
            result["metric_label"] = str(parsed.get("metric_label", "")).strip()
            result["metric_unit"] = str(parsed.get("metric_unit", "/10")).strip()
            if q_type == "scale" and result["metric_unit"] == "%":
                try:
                    result["threshold"] = int(parsed.get("threshold", 7))
                except (TypeError, ValueError):
                    result["threshold"] = 7
                result["threshold_direction"] = str(parsed.get("threshold_direction", "gte")).strip()

        return result


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data
