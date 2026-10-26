#!/usr/bin/env python3
"""Validate production-only settings before starting the web service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import validate_production_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit machine-readable output")
    args = parser.parse_args()
    issues = validate_production_env()
    if args.as_json:
        print(json.dumps({"valid": not issues, "issues": issues}, ensure_ascii=False))
    elif issues:
        print("Production configuration rejected:")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("Production configuration is valid, or APP_ENV is not production.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
