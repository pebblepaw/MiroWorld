from __future__ import annotations

import importlib
import sys


REQUIRED_MODULES = ("numpy", "pyarrow", "sklearn", "transformers", "camel", "oasis")


def main() -> int:
    missing: list[str] = []
    versions: dict[str, str] = {}
    for module_name in REQUIRED_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{module_name}: {exc!r}")
            continue
        versions[module_name] = getattr(module, "__version__", "unknown")

    if missing:
        print("OASIS runtime validation failed:", file=sys.stderr)
        for item in missing:
            print(f" - {item}", file=sys.stderr)
        return 1

    for module_name in REQUIRED_MODULES:
        print(f"{module_name}={versions[module_name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
