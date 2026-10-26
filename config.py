"""Fail-closed production configuration checks for Ezwatek."""

from __future__ import annotations

from os import environ
from urllib.parse import urlsplit


_PLACEHOLDER_MARKERS = (
    "replace-me",
    "change-me",
    "example.com",
    "example.jo",
    "localhost",
    "127.0.0.1",
    "::1",
)


def _value(env: dict[str, str], name: str) -> str:
    return str(env.get(name, "")).strip()


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return not value or any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _https_url(value: str, field: str, issues: list[str], allow_path: bool = True) -> None:
    if any(char in value for char in "\r\n"):
        issues.append(f"{field} contains invalid control characters")
        return
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        issues.append(f"{field} must be an https URL without embedded credentials")
        return
    if not allow_path and parsed.path not in ("", "/"):
        issues.append(f"{field} must not contain a path")
    if _is_placeholder(parsed.hostname):
        issues.append(f"{field} contains a placeholder host")


def validate_production_env(env: dict[str, str] | None = None) -> list[str]:
    """Return non-secret configuration errors; return no errors outside production."""
    values = dict(environ if env is None else env)
    if _value(values, "APP_ENV").lower() != "production":
        return []

    issues: list[str] = []
    if _value(values, "ENABLE_HSTS") != "1":
        issues.append("ENABLE_HSTS must be 1 in production")
    if _value(values, "IAM_MODE").lower() != "oidc":
        issues.append("IAM_MODE must be oidc in production; local IAM is not an accepted production identity provider")

    public_origin = _value(values, "PUBLIC_ORIGIN")
    _https_url(public_origin, "PUBLIC_ORIGIN", issues, allow_path=False)

    issuer = _value(values, "OIDC_ISSUER_URL")
    _https_url(issuer, "OIDC_ISSUER_URL", issues)
    if _is_placeholder(_value(values, "OIDC_CLIENT_ID")):
        issues.append("OIDC_CLIENT_ID must be supplied by the identity provider")
    required_amr = {item.strip().lower() for item in _value(values, "OIDC_REQUIRED_AMR").split(",") if item.strip()}
    if not required_amr or not required_amr.intersection({"webauthn", "fido2"}) or "otp" not in required_amr:
        issues.append("OIDC_REQUIRED_AMR must include a passkey value (webauthn or fido2) and otp")
    redirect_uri = _value(values, "OIDC_REDIRECT_URI")
    _https_url(redirect_uri, "OIDC_REDIRECT_URI", issues)
    if public_origin and redirect_uri and not redirect_uri.startswith(public_origin.rstrip("/") + "/"):
        issues.append("OIDC_REDIRECT_URI must belong to PUBLIC_ORIGIN")
    if redirect_uri and urlsplit(redirect_uri).path != "/auth/callback":
        issues.append("OIDC_REDIRECT_URI must use /auth/callback")

    if _value(values, "SESSION_STORE").lower() != "redis":
        issues.append("SESSION_STORE must be redis in production")
    if _value(values, "RATE_LIMIT_STORE").lower() != "redis":
        issues.append("RATE_LIMIT_STORE must be redis in production")
    redis_url = _value(values, "REDIS_URL")
    if not redis_url.startswith("rediss://") or _is_placeholder(redis_url):
        issues.append("REDIS_URL must use rediss:// and a non-placeholder host in production")

    if _value(values, "DATA_BACKEND").lower() != "postgres":
        issues.append("DATA_BACKEND must be postgres in production")
    database_url = _value(values, "DATABASE_URL")
    if not database_url.startswith(("postgresql://", "postgres://")) or _is_placeholder(database_url):
        issues.append("DATABASE_URL must target a non-placeholder PostgreSQL endpoint in production")
    if _value(values, "WAF_MODE").lower() != "managed":
        issues.append("WAF_MODE must be managed in production")
    return issues
