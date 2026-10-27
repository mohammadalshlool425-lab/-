"""OIDC Authorization Code + PKCE support for the Ezwatek admin boundary.

The client performs discovery only against the configured HTTPS issuer, validates
RS256 ID tokens against the issuer JWKS, and uses a one-time state value to bind
the callback to the browser that started it. Provider credentials are read from
the environment; they are never written to logs or job payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
import binascii
import hashlib
import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from security import Identity, ROLE_PERMISSIONS


DISCOVERY_TTL_SECONDS = 300
JWKS_TTL_SECONDS = 300
STATE_TTL_SECONDS = 300
MAX_RESPONSE_BYTES = 512 * 1024
_REDIS_GETDEL_SCRIPT = """
local value = redis.call('GET', KEYS[1])
if value then
  redis.call('DEL', KEYS[1])
end
return value
"""


class OIDCError(RuntimeError):
    """Raised for a safe, non-sensitive OIDC failure."""


class _NoRedirectHandler(HTTPRedirectHandler):
    """Do not let provider metadata redirect server-side HTTP requests."""

    def redirect_request(self, request, file, code, msg, headers, new_url):
        raise OIDCError("OIDC redirects are not allowed")


_OIDC_OPENER = build_opener(_NoRedirectHandler())


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str
    client_id: str
    redirect_uri: str
    client_secret: str | None = None
    scopes: tuple[str, ...] = ("openid", "profile", "email", "groups")
    role_map: tuple[tuple[str, str], ...] = ()
    required_amr: tuple[str, ...] = ("webauthn", "fido2", "otp")


class MemoryStateStore:
    """Single-instance state store for development and tests."""

    def __init__(self, ttl_seconds: int = STATE_TTL_SECONDS, max_entries: int = 5000):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._values: dict[str, tuple[dict, float]] = {}
        self._lock = threading.RLock()

    def put(self, state: str, value: dict) -> None:
        now = time.time()
        with self._lock:
            self._purge(now)
            if len(self._values) >= self.max_entries:
                oldest = min(self._values, key=lambda key: self._values[key][1])
                self._values.pop(oldest, None)
            self._values[state] = (dict(value), now + self.ttl_seconds)

    def pop(self, state: str) -> dict | None:
        now = time.time()
        with self._lock:
            item = self._values.pop(state, None)
            if not item or item[1] <= now:
                return None
            return item[0]

    def _purge(self, now: float) -> None:
        for key, (_, expires_at) in list(self._values.items()):
            if expires_at <= now:
                self._values.pop(key, None)


class RedisStateStore:
    """One-time state store shared by all web instances."""

    def __init__(self, url: str | None = None, ttl_seconds: int = STATE_TTL_SECONDS, client=None):
        self.ttl_seconds = ttl_seconds
        self.prefix = "ezwatek:oidc:state:"
        if client is not None:
            self.client = client
            return
        if not url:
            raise OIDCError("REDIS_URL is required for OIDC state")
        try:
            import redis
        except ImportError as error:
            raise OIDCError("Install requirements-production.txt for OIDC state") from error
        if not url.startswith("rediss://"):
            raise OIDCError("OIDC state requires a TLS Redis URL")
        self.client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=5,
            health_check_interval=30,
            ssl_cert_reqs="required",
        )
        self.client.ping()

    def put(self, state: str, value: dict) -> None:
        self.client.setex(self.prefix + state, self.ttl_seconds, json.dumps(value, separators=(",", ":")))

    def pop(self, state: str) -> dict | None:
        key = self.prefix + state
        getdel = getattr(self.client, "getdel", None)
        if callable(getdel):
            value = getdel(key)
        else:
            evaluator = getattr(self.client, "eval", None)
            if callable(evaluator):
                value = evaluator(_REDIS_GETDEL_SCRIPT, 1, key)
            else:
                value = self._get_delete(key)
        if not value:
            return None
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return decoded if isinstance(decoded, dict) else None

    def _get_delete(self, key: str) -> str | None:
        """Compatibility fallback for minimal Redis test doubles."""
        value = self.client.get(key)
        self.client.delete(key)
        return value


def _read_json_response(response) -> dict:
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise OIDCError("OIDC response too large")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OIDCError("OIDC response is not valid JSON") from error
    if not isinstance(data, dict):
        raise OIDCError("OIDC response must be an object")
    return data


def _https_endpoint(value: str, name: str) -> str:
    if any(char in value for char in "\r\n"):
        raise OIDCError(f"OIDC {name} contains invalid control characters")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise OIDCError(f"OIDC {name} must be an HTTPS endpoint")
    return value


def _b64decode_json(segment: str) -> dict:
    try:
        decoded = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        value = json.loads(decoded.decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, binascii.Error, json.JSONDecodeError) as error:
        raise OIDCError("OIDC token header is invalid") from error
    if not isinstance(value, dict):
        raise OIDCError("OIDC token header is invalid")
    return value


def _roles_from_claims(claims: dict, config: OIDCConfig) -> tuple[str, ...]:
    raw_groups = claims.get("groups", [])
    groups = {value for value in raw_groups if isinstance(value, str)} if isinstance(raw_groups, list) else set()
    realm_access = claims.get("realm_access", {})
    if isinstance(realm_access, dict) and isinstance(realm_access.get("roles"), list):
        groups.update(value for value in realm_access["roles"] if isinstance(value, str))
    resource_access = claims.get("resource_access", {})
    if isinstance(resource_access, dict):
        client_roles = resource_access.get(config.client_id, {})
        if isinstance(client_roles, dict) and isinstance(client_roles.get("roles"), list):
            groups.update(value for value in client_roles["roles"] if isinstance(value, str))
    mapped = []
    for app_role, provider_group in config.role_map:
        if app_role in ROLE_PERMISSIONS and provider_group in groups:
            mapped.append(app_role)
    return tuple(dict.fromkeys(mapped))


class OIDCClient:
    def __init__(
        self,
        config: OIDCConfig,
        state_store,
        fetch_json: Callable[[str], dict] | None = None,
        post_form: Callable[[str, dict], dict] | None = None,
    ):
        self.config = config
        self.state_store = state_store
        self._fetch_json_override = fetch_json
        self._post_form_override = post_form
        self._discovery: tuple[dict, float] | None = None
        self._jwks: tuple[object, float] | None = None
        self._lock = threading.RLock()

    @classmethod
    def from_environment(cls) -> "OIDCClient":
        issuer = os.environ.get("OIDC_ISSUER_URL", "").strip().rstrip("/")
        client_id = os.environ.get("OIDC_CLIENT_ID", "").strip()
        redirect_uri = os.environ.get("OIDC_REDIRECT_URI", "").strip()
        if not issuer or not client_id or not redirect_uri:
            raise OIDCError("OIDC issuer, client id, and redirect URI are required")
        _https_endpoint(issuer, "issuer")
        _https_endpoint(redirect_uri, "redirect URI")
        role_map = []
        for item in os.environ.get("OIDC_ROLE_MAP", "customer=customer,owner=owner,ops_manager=ops_manager,security_auditor=security_auditor,support_lead=support_lead").split(","):
            if "=" not in item:
                continue
            app_role, provider_group = (part.strip() for part in item.split("=", 1))
            if app_role in ROLE_PERMISSIONS and provider_group:
                role_map.append((app_role, provider_group))
        if os.environ.get("SESSION_STORE", "memory").lower() == "redis":
            state_store = RedisStateStore(os.environ.get("REDIS_URL"))
        else:
            state_store = MemoryStateStore()
        scopes = tuple(item for item in os.environ.get("OIDC_SCOPES", "openid profile email groups").split() if item)
        required_amr = tuple(item.strip().lower() for item in os.environ.get("OIDC_REQUIRED_AMR", "webauthn,fido2,otp").split(",") if item.strip())
        return cls(
            OIDCConfig(
                issuer=issuer,
                client_id=client_id,
                redirect_uri=redirect_uri,
                client_secret=os.environ.get("OIDC_CLIENT_SECRET") or None,
                scopes=scopes or ("openid", "profile", "email", "groups"),
                role_map=tuple(role_map),
                required_amr=required_amr or ("webauthn", "fido2", "otp"),
            ),
            state_store,
        )

    def authorization_url(self) -> str:
        discovery = self._get_discovery()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
        self.state_store.put(state, {"nonce": nonce, "verifier": verifier})
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return discovery["authorization_endpoint"] + "?" + urlencode(params)

    def authenticate_callback(self, code: str, state: str) -> Identity:
        if not code or not state or len(code) > 4096 or len(state) > 512:
            raise OIDCError("invalid OIDC callback")
        state_data = self.state_store.pop(state)
        if not state_data or not isinstance(state_data.get("nonce"), str) or not isinstance(state_data.get("verifier"), str):
            raise OIDCError("OIDC state expired or already used")
        discovery = self._get_discovery()
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "code_verifier": state_data["verifier"],
        }
        token_response = self._post_form(discovery["token_endpoint"], form)
        id_token = token_response.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise OIDCError("OIDC provider did not return an ID token")
        claims = self._verify_id_token(id_token, state_data["nonce"])
        username = claims.get("preferred_username") or claims.get("email") or claims.get("sub")
        if not isinstance(username, str) or not 1 <= len(username) <= 80:
            raise OIDCError("OIDC identity has no usable subject")
        roles = _roles_from_claims(claims, self.config)
        if not roles:
            raise OIDCError("OIDC identity has no mapped application role")
        return Identity(username, roles, subject=claims["sub"])

    def _get_discovery(self) -> dict:
        now = time.time()
        with self._lock:
            if self._discovery and self._discovery[1] > now:
                return self._discovery[0]
            url = self.config.issuer + "/.well-known/openid-configuration"
            raw = self._fetch_json(url)
            if not isinstance(raw, dict):
                raise OIDCError("OIDC discovery response is invalid")
            discovered_issuer = raw.get("issuer")
            if not isinstance(discovered_issuer, str) or discovered_issuer.rstrip("/") != self.config.issuer.rstrip("/"):
                raise OIDCError("OIDC issuer mismatch")
            required = {}
            for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                value = raw.get(key)
                if not isinstance(value, str):
                    raise OIDCError(f"OIDC discovery missing {key}")
                required[key] = _https_endpoint(value, key)
            response_types = raw.get("response_types_supported")
            if response_types is not None and (not isinstance(response_types, list) or "code" not in response_types):
                raise OIDCError("OIDC provider does not support authorization code")
            discovery = {"issuer": self.config.issuer, **required}
            self._discovery = (discovery, now + DISCOVERY_TTL_SECONDS)
            return discovery

    def _get_jwks(self):
        now = time.time()
        with self._lock:
            if self._jwks and self._jwks[1] > now:
                return self._jwks[0]
            try:
                from authlib.jose import JsonWebKey
            except ImportError as error:
                raise OIDCError("Install requirements-production.txt for OIDC token verification") from error
            jwks_uri = self._get_discovery()["jwks_uri"]
            key_set = JsonWebKey.import_key_set(self._fetch_json(jwks_uri))
            self._jwks = (key_set, now + JWKS_TTL_SECONDS)
            return key_set

    def _verify_id_token(self, token: str, nonce: str) -> dict:
        header_segment = token.split(".", 1)[0] if "." in token else ""
        header = _b64decode_json(header_segment)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise OIDCError("OIDC token algorithm or key id is not allowed")
        try:
            from authlib.jose import jwt
            claims = jwt.decode(
                token,
                self._get_jwks(),
                claims_options={
                    "iss": {"essential": True, "value": self.config.issuer},
                    "aud": {"essential": True, "value": self.config.client_id},
                    "nonce": {"essential": True, "value": nonce},
                },
            )
            claims.validate(leeway=60)
            amr = claims.get("amr", [])
            normalized_amr = {value.strip().lower() for value in amr if isinstance(value, str)} if isinstance(amr, list) else set()
            required_amr = {value.strip().lower() for value in self.config.required_amr if isinstance(value, str)}
            if required_amr and not normalized_amr.intersection(required_amr):
                raise OIDCError("OIDC authentication strength is insufficient")
        except OIDCError:
            raise
        except Exception as error:
            raise OIDCError("OIDC ID token validation failed") from error
        data = dict(claims)
        if not isinstance(data.get("sub"), str) or not data["sub"]:
            raise OIDCError("OIDC ID token has no subject")
        return data

    def _fetch_json(self, url: str) -> dict:
        if self._fetch_json_override:
            return self._fetch_json_override(url)
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "Ezwatek-OIDC/1"})
        try:
            with _OIDC_OPENER.open(request, timeout=5) as response:
                return _read_json_response(response)
        except OIDCError:
            raise
        except Exception as error:
            raise OIDCError("OIDC discovery request failed") from error

    def _post_form(self, url: str, form: dict) -> dict:
        if self._post_form_override:
            return self._post_form_override(url, form)
        body = urlencode(form).encode("utf-8")
        headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Ezwatek-OIDC/1"}
        if self.config.client_secret:
            basic = base64.b64encode(f"{self.config.client_id}:{self.config.client_secret}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with _OIDC_OPENER.open(request, timeout=5) as response:
                return _read_json_response(response)
        except OIDCError:
            raise
        except Exception as error:
            raise OIDCError("OIDC token request failed") from error
