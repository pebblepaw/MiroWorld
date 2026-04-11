from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_RUNNER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "oasis_reddit_runner.py"
_SPEC = importlib.util.spec_from_file_location("oasis_reddit_runner", _RUNNER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
_extract_title = _MODULE._extract_title


def test_extract_title_removes_first_person_lead_in_and_surfaces_core_topic() -> None:
    content = (
        "I think the childcare subsidy will help working parents in Tampines, "
        "but the rollout still feels confusing for part-time caregivers."
    )

    title = _extract_title(content)

    assert "childcare subsidy" in title.lower()
    assert "working parents" in title.lower()
    assert not title.lower().startswith("i think")
    assert len(title.split()) <= 8
