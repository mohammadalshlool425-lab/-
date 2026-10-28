"""Fail-closed production configuration checks for Ezwatek."""

from __future__ import annotations

import base64
import binascii
from os import environ
from urllib.parse import parse_qs, urlsplit


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


def _postgres_url(value: str, env: dict[str, str], issues: list[str]) -> None:
    if any(char in value for char in "\r\n"):
        issues.append("DATABASE_URL contains invalid control characters")
        return
    parsed = urlsplit(value)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname or parsed.fragment:
        issues.append("DATABASE_URL must target a PostgreSQL endpoint with a hostname")
        return
    query = parse_qs(parsed.query, keep_blank_values=True)
    configured_sslmodes = query.get("sslmode", [])
    if len(configured_sslmodes) > 1:
        issues.append("DATABASE_URL must contain only one sslmode value")
        return
    sslmode = (configured_sslmodes[0] if configured_sslmodes else _value(env, "PGSSLMODE")).strip().lower()
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        issues.append("DATABASE_URL or PGSSLMODE must require PostgreSQL TLS (require, verify-ca, or verify-full)")


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
    scopes = set(_value(values, "OIDC_SCOPES").split())
    if scopes and "openid" not in scopes:
        issues.append("OIDC_SCOPES must include openid when explicitly configured")
    role_map_text = _value(values, "OIDC_ROLE_MAP")
    if not role_map_text:
        issues.append("OIDC_ROLE_MAP must be explicitly configured in production")
    else:
        valid_roles = {"customer", "owner", "ops_manager", "security_auditor", "support_lead"}
        mappings = []
        for item in role_map_text.split(","):
            parts = item.split("=", 1)
            mappings.append((parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("", ""))
        mapped_roles = [app_role for app_role, _ in mappings]
        if not mappings or any(app_role not in valid_roles or not provider_group for app_role, provider_group in mappings):
            issues.append("OIDC_ROLE_MAP contains an invalid application-role mapping")
        elif len(mapped_roles) != len(set(mapped_roles)):
            issues.append("OIDC_ROLE_MAP contains duplicate application roles")
        else:
            mapped_role_set = set(mapped_roles)
            if "customer" not in mapped_role_set:
                issues.append("OIDC_ROLE_MAP must include a customer role for order creation")
            if not mapped_role_set.intersection({"owner", "ops_manager"}):
                issues.append("OIDC_ROLE_MAP must include owner or ops_manager for administration")
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
    else:
        _postgres_url(database_url, values, issues)
    if _value(values, "WAF_MODE").lower() != "managed":
        issues.append("WAF_MODE must be managed in production")
    address_key = _value(values, "ORDER_ADDRESS_ENCRYPTION_KEY")
    try:
        decoded_key = base64.b64decode(
            address_key + "=" * (-len(address_key) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError, TypeError):
        decoded_key = b""
    if len(decoded_key) != 32:
        issues.append("ORDER_ADDRESS_ENCRYPTION_KEY must be a base64url-encoded 32-byte key")
    return issues
