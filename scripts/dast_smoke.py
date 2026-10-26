#!/usr/bin/env python3
"""Run dependency-free defensive HTTP checks against a local/staging app."""

from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def request(base_url: str, path: str, method: str = "GET"):
    req = Request(base_url.rstrip("/") + path, method=method)
    try:
        with urlopen(req, timeout=3) as response:  # nosec B310
            return response.status, response.headers, response.read(4096)
    except HTTPError as error:
        return error.code, error.headers, error.read(4096)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        parser.error("--base-url must be an HTTP(S) URL")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} and not args.allow_remote:
        parser.error("refusing a remote target without --allow-remote")

    last_error = None
    for _ in range(20):
        try:
            status, _, _ = request(args.base_url, "/health")
            if status == 200:
                break
        except (OSError, URLError) as error:
            last_error = error
        time.sleep(0.25)
    else:
        raise SystemExit(f"health endpoint did not become available: {last_error}")

    checks = []
    status, headers, _ = request(args.base_url, "/health")
    checks.append(("health", status == 200))
    checks.append(("security_headers", all(headers.get(key) for key in ("X-Content-Type-Options", "Referrer-Policy", "Content-Security-Policy", "X-Request-ID"))))
    status, _, _ = request(args.base_url, "/does-not-exist")
    checks.append(("unknown_route_rejected", status == 404))
    status, _, _ = request(args.base_url, "/%2e%2e/%2e%2e/etc/passwd")
    checks.append(("encoded_traversal_rejected", status in {400, 404}))
    status, headers, _ = request(args.base_url, "/", method="POST")
    checks.append(("unexpected_state_change_rejected", status == 405 and headers.get("Allow")))
    status, _, _ = request(args.base_url, "/api/admin/overview")
    checks.append(("admin_requires_authentication", status == 401))
    result = {"checks": {name: bool(ok) for name, ok in checks}, "passed": all(ok for _, ok in checks)}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
