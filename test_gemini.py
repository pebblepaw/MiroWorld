#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_CHAT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_EMBED_MODEL = "gemini-embedding-001"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def resolve_api_key() -> str | None:
    for key_name in ("GEMINI_API_KEY", "GEMINI_API", "GOOGLE_API_KEY", "LLM_API_KEY"):
        value = os.getenv(key_name)
        if value and value.strip():
            return value.strip()
    return None


def parse_retry_delay(message: str, details: Any) -> str | None:
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict):
                retry_delay = item.get("retryDelay")
                if retry_delay:
                    return str(retry_delay)
    match = re.search(r"retry in ([0-9.]+s)", message, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def request_json(url: str, api_key: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            return resp.status, body if isinstance(body, dict) else {"raw": body}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"raw": raw}
        if isinstance(body, dict):
            body.setdefault("status_code", exc.code)
        else:
            body = {"raw": raw, "status_code": exc.code}
        return exc.code, body
    except URLError as exc:
        return -1, {"raw": f"Network error: {exc.reason}"}


def summarize_result(name: str, status: int, body: dict[str, Any]) -> tuple[str, int]:
    if 200 <= status < 300:
        return f"{name}: OK", 0

    error = body.get("error") if isinstance(body, dict) else None
    message = ""
    details: Any = None
    error_status = ""
    if isinstance(error, dict):
        message = str(error.get("message") or "").strip()
        details = error.get("details")
        error_status = str(error.get("status") or "").strip()
    else:
        message = str(body.get("raw") or "").strip()

    if status == 429 or error_status.upper() == "RESOURCE_EXHAUSTED":
        retry_delay = parse_retry_delay(message, details)
        suffix = f" (retry in {retry_delay})" if retry_delay else ""
        return f"{name}: RATE LIMITED{suffix}", 2

    if status in {401, 403}:
        return f"{name}: AUTH ERROR ({status})", 3

    if message:
        return f"{name}: HTTP {status} - {message[:140]}", 3
    return f"{name}: HTTP {status}", 3


def main() -> int:
    load_env_file(Path(__file__).resolve().with_name(".env"))

    api_key = resolve_api_key()
    if not api_key:
        print("Gemini check: MISSING API KEY")
        print("Set one of: GEMINI_API, GEMINI_API_KEY, GOOGLE_API_KEY, LLM_API_KEY")
        return 1

    base_url = os.getenv("GEMINI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    chat_model = os.getenv("GEMINI_MODEL", DEFAULT_CHAT_MODEL)
    embed_model = os.getenv("GEMINI_EMBED_MODEL", DEFAULT_EMBED_MODEL)

    checks = [
        (
            "chat/completions",
            f"{base_url}/chat/completions",
            {
                "model": chat_model,
                "messages": [{"role": "user", "content": "Reply with OK."}],
                "max_tokens": 1,
                "temperature": 0,
            },
        ),
        (
            "embeddings",
            f"{base_url}/embeddings",
            {
                "model": embed_model,
                "input": "ping",
            },
        ),
    ]

    lines: list[str] = []
    exit_code = 0

    for name, url, payload in checks:
        started = time.perf_counter()
        status, body = request_json(url, api_key, payload)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        line, code = summarize_result(name, status, body)
        lines.append(f"{line} [{elapsed_ms}ms]")
        exit_code = max(exit_code, code)

    print("Gemini check")
    print(f"chat model:  {chat_model}")
    print(f"embed model: {embed_model}")
    for line in lines:
        print(line)

    if exit_code == 0:
        print("Overall: OK")
    elif exit_code == 2:
        print("Overall: RATE LIMITED")
    else:
        print("Overall: FAILED")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
