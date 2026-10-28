#!/usr/bin/env python3
"""Run fail-closed integration gates against an approved Ezwatek staging origin.

This script never treats a preview or a missing external dependency as staging
success. It checks the live HTTP boundary only; authenticated OIDC, payment,
and notification journeys still require their provider-specific test accounts
and webhook checks in the staging runbook.
"""

from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_REQUIRED_SECURITY_HEADERS = (
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Content-Security-Policy",
    "X-Request-ID",
)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, msg, headers, new_url):
        raise RuntimeError("redirect_not_allowed")


_OPENER = build_opener(_NoRedirectHandler())


def validate_target(base_url: str, allow_remote: bool = False) -> str:
    """Validate and normalize a staging origin without accepting a URL path/query."""
    parsed = urlsplit(base_url.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("--base-url must be an HTTP(S) origin without credentials, path, query, or fragment")
    if parsed.hostname not in _LOCAL_HOSTS and not allow_remote:
        raise ValueError("refusing a remote target without --allow-remote")
    if parsed.hostname not in _LOCAL_HOSTS and parsed.scheme != "https":
        raise ValueError("remote staging targets must use HTTPS")
    return f"{parsed.scheme}://{parsed.netloc}"


def _request(base_url: str, path: str, method: str = "GET") -> tuple[int, object, bytes]:
    request = Request(
        base_url + path,
        method=method,
        headers={"Accept": "application/json", "User-Agent": "Ezwatek-staging-gate/1"},
    )
    try:
        with _OPENER.open(request, timeout=8) as response:  # nosec B310
            return response.status, response.headers, response.read(64 * 1024)
    except HTTPError as error:
        return error.code, error.headers, error.read(64 * 1024)


def _wait_for_health(base_url: str, attempts: int = 20) -> tuple[int, object, bytes]:
    last_status = None
    for _ in range(max(1, attempts)):
        try:
            response = _request(base_url, "/health")
            last_status = response[0]
            if last_status == 200:
                return response
        except (OSError, RuntimeError, URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f"health_not_available:{last_status or 'network'}")


def _json_body(body: bytes) -> dict:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("response_is_not_json") from error
    if not isinstance(value, dict):
        raise ValueError("response_is_not_an_object")
    return value


def _check(checks: dict[str, bool], name: str, value: bool) -> None:
    checks[name] = bool(value)


def run_gate(base_url: str) -> dict[str, object]:
    checks: dict[str, bool] = {}
    failures: list[str] = []

    def capture(name: str, operation) -> object | None:
        try:
            return operation()
        except (OSError, RuntimeError, ValueError, URLError) as error:
            checks[name] = False
            failures.append(f"{name}:{type(error).__name__}")
            return None

    health = capture("health", lambda: _wait_for_health(base_url))
    if health is not None:
        status, headers, body = health
        _check(checks, "health_status", status == 200)
        try:
            _check(checks, "health_json", _json_body(body).get("status") == "ok")
        except ValueError as error:
            checks["health_json"] = False
            failures.append(f"health_json:{type(error).__name__}")
        _check(checks, "security_headers", all(headers.get(key) for key in _REQUIRED_SECURITY_HEADERS))
        _check(checks, "request_id_header", bool(headers.get("X-Request-ID")))
    else:
        return {"checks": checks, "failures": failures, "passed": False}

    readiness = capture("readiness", lambda: _request(base_url, "/ready"))
    if readiness is not None:
        status, headers, body = readiness
        _check(checks, "readiness_status", status == 200)
        try:
            ready_payload = _json_body(body)
            _check(checks, "readiness_json", ready_payload.get("status") == "ready")
            component_checks = ready_payload.get("checks")
            _check(
                checks,
                "readiness_dependencies",
                isinstance(component_checks, dict) and all(component_checks.values()),
            )
        except ValueError as error:
            checks["readiness_json"] = False
            failures.append(f"readiness_json:{type(error).__name__}")
        _check(checks, "staging_hsts", bool(headers.get("Strict-Transport-Security")))

    auth_status = capture("auth_status", lambda: _request(base_url, "/api/auth/status"))
    if auth_status is not None:
        status, _, body = auth_status
        try:
            auth_payload = _json_body(body)
            _check(checks, "oidc_auth_mode", status == 200 and auth_payload.get("auth_mode") == "oidc")
            _check(checks, "anonymous_by_default", auth_payload.get("authenticated") is False)
        except ValueError as error:
            checks["oidc_auth_mode"] = False
            failures.append(f"auth_status_json:{type(error).__name__}")

    oidc_login = capture("oidc_login", lambda: _request(base_url, "/auth/login"))
    if oidc_login is not None:
        status, headers, _ = oidc_login
        location = headers.get("Location", "")
        location_parts = urlsplit(location)
        _check(checks, "oidc_redirect", status == 303 and location_parts.scheme == "https" and bool(location_parts.hostname))

    services = capture("services", lambda: _request(base_url, "/api/services"))
    if services is not None:
        status, _, body = services
        try:
            service_payload = _json_body(body)
            _check(checks, "production_service_catalog", status == 200 and bool(service_payload.get("services")))
        except ValueError as error:
            checks["production_service_catalog"] = False
            failures.append(f"services_json:{type(error).__name__}")

    admin = capture("admin_boundary", lambda: _request(base_url, "/api/admin/overview"))
    if admin is not None:
        _check(checks, "admin_requires_authentication", admin[0] == 401)

    order_write = capture("order_boundary", lambda: _request(base_url, "/api/orders", method="POST"))
    if order_write is not None:
        _check(checks, "order_requires_authentication", order_write[0] == 401)

    unknown = capture("unknown_route", lambda: _request(base_url, "/staging-gate-unknown-route"))
    if unknown is not None:
        _check(checks, "unknown_route_rejected", unknown[0] == 404)

    return {"checks": checks, "failures": failures, "passed": bool(checks) and not failures and all(checks.values())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="approved staging HTTP(S) origin")
    parser.add_argument("--allow-remote", action="store_true", help="required for a non-local approved staging host")
    args = parser.parse_args()
    try:
        base_url = validate_target(args.base_url, allow_remote=args.allow_remote)
    except ValueError as error:
        parser.error(str(error))
    result = run_gate(base_url)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
