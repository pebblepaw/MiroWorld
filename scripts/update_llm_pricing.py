#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import requests
import yaml
from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "config" / "llm_pricing.yaml"
OPENAI_PRICING_URL = "https://developers.openai.com/api/docs/pricing"
GEMINI_PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"
OPENROUTER_RANKINGS_URL = "https://openrouter.ai/rankings"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
PLAYWRIGHT_MODULE = REPO_ROOT / "frontend" / "node_modules" / "playwright" / "index.mjs"

OPENAI_COMMON_MODELS = (
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.4-pro",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-pro",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-2024-05-13",
    "gpt-4o-mini",
    "gpt-3.5-turbo",
)

GEMINI_COMMON_MODELS = (
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
)

OPENROUTER_EXTRA_MODELS = (
    "openai/gpt-5-mini",
    "meta-llama/llama-3.1-8b-instruct:free",
)

MODEL_ALIASES = OrderedDict(
    {
        "gemini-flash-latest": "gemini-2.5-flash",
        "gemini-flash-lite-latest": "gemini-2.5-flash-lite",
    }
)


@dataclass(frozen=True)
class PricingEntry:
    input: float
    output: float
    cached_input: float | None


def _get(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    response.raise_for_status()
    return response.text


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = str(raw).strip().replace("$", "").replace(",", "")
    if not cleaned or cleaned in {"-", "null", "None", "Not available"}:
        return None
    return float(cleaned)


def _extract_first_price(text: str) -> float | None:
    match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    return float(match.group(1))


def _openai_standard_table_rows(soup: BeautifulSoup) -> dict[str, PricingEntry]:
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("OpenAI pricing page did not expose any pricing tables.")

    rows = OrderedDict()
    for tr in tables[0].find_all("tr")[2:]:
        cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all(["th", "td"])]
        if len(cells) < 4:
            continue
        model = cells[0]
        input_price = _to_float(cells[1])
        cached_input = _to_float(cells[2])
        output_price = _to_float(cells[3])
        if model and input_price is not None and output_price is not None:
            rows[model] = PricingEntry(input=input_price, output=output_price, cached_input=cached_input)
    return rows


def fetch_openai_pricing() -> OrderedDict[str, PricingEntry]:
    html = _get(OPENAI_PRICING_URL)
    soup = BeautifulSoup(html, "html.parser")
    pricing: OrderedDict[str, PricingEntry] = OrderedDict()

    pricing.update(_openai_standard_table_rows(soup))

    pattern = re.compile(
        r'&quot;([a-z0-9.\-]+)&quot;\],\[0,([0-9.]+|null)\],\[0,([0-9.]+|null)\],\[0,([0-9.]+|null)\]'
    )
    for match in pattern.finditer(html):
        model_id = match.group(1)
        if model_id not in OPENAI_COMMON_MODELS or model_id in pricing:
            continue
        input_price = _to_float(match.group(2))
        cached_input = _to_float(match.group(3))
        output_price = _to_float(match.group(4))
        if input_price is None or output_price is None:
            continue
        pricing[model_id] = PricingEntry(
            input=input_price,
            output=output_price,
            cached_input=cached_input,
        )

    missing = [model_id for model_id in OPENAI_COMMON_MODELS if model_id not in pricing]
    if missing:
        raise RuntimeError(f"Missing OpenAI pricing for: {', '.join(missing)}")

    return OrderedDict((model_id, pricing[model_id]) for model_id in OPENAI_COMMON_MODELS)


def fetch_gemini_pricing() -> OrderedDict[str, PricingEntry]:
    html = _get(GEMINI_PRICING_URL)
    soup = BeautifulSoup(html, "html.parser")
    pricing: OrderedDict[str, PricingEntry] = OrderedDict()

    for model_id in GEMINI_COMMON_MODELS:
        code = soup.find("code", string=lambda value: str(value or "").strip() == model_id)
        if code is None:
            raise RuntimeError(f"Gemini pricing page is missing model code '{model_id}'.")
        table = code.find_next("table")
        if table is None:
            raise RuntimeError(f"Gemini pricing page is missing a pricing table for '{model_id}'.")

        input_price = None
        output_price = None
        cached_input = None
        for row in table.find_all("tr"):
            cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all(["th", "td"])]
            if len(cells) < 3:
                continue
            label = cells[0].lower()
            paid_tier = cells[-1]
            if "input price" in label and input_price is None:
                input_price = _extract_first_price(paid_tier)
            elif "output price" in label and output_price is None:
                output_price = _extract_first_price(paid_tier)
            elif "context caching price" in label and cached_input is None:
                cached_input = _extract_first_price(paid_tier)

        if input_price is None or output_price is None:
            raise RuntimeError(f"Gemini pricing page did not expose token prices for '{model_id}'.")

        pricing[model_id] = PricingEntry(
            input=input_price,
            output=output_price,
            cached_input=cached_input,
        )

    return pricing


def fetch_openrouter_top_models(limit: int = 15) -> list[str]:
    if not PLAYWRIGHT_MODULE.exists():
        raise RuntimeError(
            "OpenRouter rankings extraction needs Playwright from frontend/node_modules. "
            "Run 'cd frontend && npm install' first."
        )

    script = f"""
import {{ chromium }} from {json.dumps(PLAYWRIGHT_MODULE.as_posix())};
const browser = await chromium.launch({{ headless: true }});
const page = await browser.newPage({{ viewport: {{ width: 1400, height: 2400 }} }});
await page.goto({json.dumps(OPENROUTER_RANKINGS_URL)}, {{ waitUntil: 'networkidle' }});
const buttons = page.locator('button', {{ hasText: 'Show more' }});
if (await buttons.count()) {{
  await buttons.first().click();
  await page.waitForTimeout(1000);
}}
const links = await page.$$eval('a[href^="/"]', (els) =>
  els.map((el) => el.getAttribute('href')).filter(Boolean)
);
const models = [];
for (const href of links) {{
  const cleaned = href.replace(/^\\//, '');
  if (!/^[a-z0-9_.-]+\\/[a-z0-9_.:-]+$/i.test(cleaned)) continue;
  if (cleaned.startsWith('docs/') || cleaned.startsWith('apps/') || cleaned.startsWith('labs/') || cleaned.startsWith('provider/')) continue;
  if (!models.includes(cleaned)) models.push(cleaned);
}}
console.log(JSON.stringify(models.slice(0, {limit})));
await browser.close();
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    models = json.loads(result.stdout)
    if len(models) < limit:
        raise RuntimeError(f"OpenRouter rankings only returned {len(models)} models, expected {limit}.")
    return [str(model).strip() for model in models if str(model).strip()]


def fetch_openrouter_pricing() -> tuple[list[str], OrderedDict[str, PricingEntry]]:
    top_models = fetch_openrouter_top_models(limit=15)
    wanted_models = list(OrderedDict.fromkeys([*top_models, *OPENROUTER_EXTRA_MODELS]))
    payload = requests.get(OPENROUTER_MODELS_URL, timeout=60).json()
    models_by_id = {str(item.get("id") or "").strip(): item for item in payload.get("data", [])}

    pricing: OrderedDict[str, PricingEntry] = OrderedDict()
    for model_id in wanted_models:
        if model_id == "meta-llama/llama-3.1-8b-instruct:free":
            pricing[model_id] = PricingEntry(input=0.0, output=0.0, cached_input=0.0)
            continue

        model_payload = models_by_id.get(model_id)
        if not isinstance(model_payload, dict):
            raise RuntimeError(f"OpenRouter models API is missing '{model_id}'.")
        raw_pricing = model_payload.get("pricing") or {}
        prompt = float(str(raw_pricing.get("prompt") or "0").strip() or 0.0) * 1_000_000
        completion = float(str(raw_pricing.get("completion") or "0").strip() or 0.0) * 1_000_000
        cached = raw_pricing.get("input_cache_read")
        cached_input = None if cached is None else float(str(cached).strip() or 0.0) * 1_000_000
        pricing[model_id] = PricingEntry(input=prompt, output=completion, cached_input=cached_input)

    return top_models, pricing


def build_payload() -> dict[str, Any]:
    openai_pricing = fetch_openai_pricing()
    gemini_pricing = fetch_gemini_pricing()
    openrouter_top_models, openrouter_pricing = fetch_openrouter_pricing()

    models: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for model_id, entry in openai_pricing.items():
        models[model_id] = {
            "input": round(entry.input, 6),
            "output": round(entry.output, 6),
            "cached_input": None if entry.cached_input is None else round(entry.cached_input, 6),
        }
    for model_id, entry in gemini_pricing.items():
        models[model_id] = {
            "input": round(entry.input, 6),
            "output": round(entry.output, 6),
            "cached_input": None if entry.cached_input is None else round(entry.cached_input, 6),
        }
    for model_id, entry in openrouter_pricing.items():
        models[model_id] = {
            "input": round(entry.input, 6),
            "output": round(entry.output, 6),
            "cached_input": None if entry.cached_input is None else round(entry.cached_input, 6),
        }

    models["ollama"] = {"input": 0.0, "output": 0.0, "cached_input": 0.0}

    return {
        "description": "LLM pricing used for runtime token cost estimates.",
        "pricing_mode": "standard",
        "last_updated": str(date.today()),
        "sources": {
            "openai": OPENAI_PRICING_URL,
            "google": GEMINI_PRICING_URL,
            "openrouter_rankings": OPENROUTER_RANKINGS_URL,
            "openrouter_models_api": OPENROUTER_MODELS_URL,
        },
        "aliases": dict(MODEL_ALIASES),
        "openrouter_top_models": openrouter_top_models,
        "models": models,
    }


def write_payload(payload: dict[str, Any], *, output_path: Path) -> None:
    normalized_payload = json.loads(json.dumps(payload))
    output_path.write_text(
        yaml.safe_dump(normalized_payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main() -> int:
    payload = build_payload()
    write_payload(payload, output_path=OUTPUT_PATH)
    print(f"Updated {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
