"""Dependency-free IAM, MFA, RBAC and session primitives for Ezwatek.

This module deliberately keeps the local identity provider small and explicit. In
production, the preferred deployment is an external OIDC/SAML provider; these
primitives are the safe fallback for a controlled internal deployment.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import base64
import binascii
import hashlib
import json
import hmac
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie


PASSWORD_SCHEME = "scrypt"
PASSWORD_N = 2**14
PASSWORD_R = 8
PASSWORD_P = 1
PASSWORD_DKLEN = 32
PASSWORD_SALT_BYTES = 16
SESSION_TTL_SECONDS = 30 * 60
TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+\-]{2,63}$")
DIGITS_RE = re.compile(r"^[0-9]{6}$")


ROLE_PERMISSIONS = {
    "owner": frozenset({
        "admin:read",
        "admin:write",
        "security:read",
        "security:write",
        "providers:approve",
        "audit:read",
    }),
    "ops_manager": frozenset({
        "admin:read",
        "admin:write",
        "providers:approve",
        "audit:read",
    }),
    "security_auditor": frozenset({
        "admin:read",
        "security:read",
        "audit:read",
    }),
    "support_lead": frozenset({"admin:read"}),
}


@dataclass(frozen=True)
class Identity:
    username: str
    roles: tuple[str, ...]

    @property
    def permissions(self) -> frozenset[str]:
        permissions: set[str] = set()
        for role in self.roles:
            permissions.update(ROLE_PERMISSIONS.get(role, ()))
        return frozenset(permissions)


@dataclass(frozen=True)
class Session:
    token: str
    csrf_token: str
    identity: Identity
    created_at: float
    expires_at: float


class AuditLog:
    """Bounded, redacted runtime audit buffer.

    It is intentionally not presented as durable compliance storage. Production
    must stream these records to an append-only, access-controlled sink.
    """

    def __init__(self, max_events: int = 5000):
        self._events: deque[dict] = deque(maxlen=max_events)
        self._lock = threading.RLock()
        self._redaction_key = os.environ.get('AUDIT_REDACTION_KEY') or secrets.token_hex(32)

    def record(self, action: str, actor: str | None = None, success: bool = True, client_ip: str | None = None, details: dict | None = None) -> None:
        clean_details = {}
        for key, value in (details or {}).items():
            clean_key = str(key)[:40]
            clean_value = str(value).replace('\\n', ' ').replace('\\r', ' ')[:160]
            clean_details[clean_key] = clean_value
        event = {
            'event_id': secrets.token_hex(8),
            'timestamp': int(time.time()),
            'action': str(action)[:80],
            'actor': str(actor)[:80] if actor else None,
            'success': bool(success),
            'client_fingerprint': hashlib.sha256((self._redaction_key + (client_ip or 'unknown')).encode('utf-8')).hexdigest()[:16],
            'details': clean_details,
        }
        with self._lock:
            self._events.append(event)

    def recent(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        with self._lock:
            return list(reversed(list(self._events)[-limit:]))


class SecurityInputError(ValueError):
    """Raised when an authentication input is malformed."""


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str) or not 8 <= len(password) <= 256:
        raise SecurityInputError("password_length")
    return password.encode("utf-8")


def hash_password(password: str) -> str:
    """Return a portable scrypt password record.

    The record contains algorithm parameters and a random salt so it can be
    migrated later without storing plaintext or relying on a global secret.
    """
    raw_password = _password_bytes(password)
    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = hashlib.scrypt(
        raw_password,
        salt=salt,
        n=PASSWORD_N,
        r=PASSWORD_R,
        p=PASSWORD_P,
        dklen=PASSWORD_DKLEN,
    )
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return "$".join(
        (
            PASSWORD_SCHEME,
            str(PASSWORD_N),
            str(PASSWORD_R),
            str(PASSWORD_P),
            encode(salt),
            encode(digest),
        )
    )


def verify_password(password: str, record: str) -> bool:
    """Verify a password record without leaking whether it parsed."""
    try:
        raw_password = _password_bytes(password)
        if not isinstance(record, str):
            return False
        scheme, n_text, r_text, p_text, salt_text, digest_text = record.split("$", 5)
        if scheme != PASSWORD_SCHEME:
            return False
        n_value, r_value, p_value = int(n_text), int(r_text), int(p_text)
        if n_value < 2**10 or n_value > 2**20 or n_value & (n_value - 1) or not 1 <= r_value <= 32 or not 1 <= p_value <= 16:
            return False
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        salt = decode(salt_text)
        expected = decode(digest_text)
        if not 8 <= len(salt) <= 64 or not 16 <= len(expected) <= 64:
            return False
        digest = hashlib.scrypt(
            raw_password,
            salt=salt,
            n=n_value,
            r=r_value,
            p=p_value,
            dklen=len(expected),
        )
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError, UnicodeError, OverflowError):
        return False


def generate_totp_secret() -> str:
    """Generate a base32 secret suitable for an authenticator app."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp_bytes(secret: str) -> bytes:
    normalized = "".join(str(secret).split()).upper()
    return base64.b32decode(normalized + "=" * (-len(normalized) % 8), casefold=True)


def totp_code(secret: str, timestamp: int | float | None = None, counter_offset: int = 0) -> str:
    """Create an RFC 6238-compatible six digit TOTP code."""
    if timestamp is None:
        timestamp = time.time()
    key = _totp_bytes(secret)
    counter = int(timestamp // TOTP_STEP_SECONDS) + counter_offset
    message = counter.to_bytes(8, "big", signed=False)
    digest = hmac.new(key, message, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = ((digest[offset] & 0x7F) << 24) | ((digest[offset + 1] & 0xFF) << 16) | ((digest[offset + 2] & 0xFF) << 8) | (digest[offset + 3] & 0xFF)
    return f"{binary % (10 ** TOTP_DIGITS):0{TOTP_DIGITS}d}"


def verify_totp(secret: str, code: str, timestamp: int | float | None = None, window: int = 1) -> bool:
    """Verify a TOTP code with one 30-second clock-skew window."""
    if not isinstance(code, str) or not DIGITS_RE.fullmatch(code):
        return False
    try:
        return any(
            hmac.compare_digest(code, totp_code(secret, timestamp, offset))
            for offset in range(-window, window + 1)
        )
    except (ValueError, TypeError, binascii.Error):
        return False


def role_permissions(roles: tuple[str, ...] | list[str]) -> frozenset[str]:
    permissions: set[str] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, ()))
    return frozenset(permissions)


def can(identity: Identity | None, permission: str) -> bool:
    return bool(identity and permission in identity.permissions)


class LoginThrottle:
    """Small per-key login limiter; put a WAF/edge limiter in front in production."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 300, lockout_seconds: int = 300):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = threading.RLock()

    def allowed(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            if self._locked_until.get(key, 0) > now:
                return False
            failures = self._failures[key]
            while failures and failures[0] <= now - self.window_seconds:
                failures.popleft()
            return len(failures) < self.max_failures

    def failure(self, key: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            failures = self._failures[key]
            failures.append(now)
            if len(failures) >= self.max_failures:
                self._locked_until[key] = now + self.lockout_seconds

    def success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)


class RedisLoginThrottle:
    """Redis-backed login limiter using atomic counters and short-lived keys."""

    def __init__(self, url: str | None = None, max_failures: int = 5, window_seconds: int = 300, lockout_seconds: int = 300, client=None):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self.prefix = 'ezwatek:login:'
        if client is not None:
            self.client = client
            return
        if not url:
            raise RuntimeError('REDIS_URL is required when RATE_LIMIT_STORE=redis')
        try:
            import redis
        except ImportError as error:
            raise RuntimeError('Install requirements-production.txt for Redis rate limiting') from error
        kwargs = {'decode_responses': True, 'socket_timeout': 3, 'health_check_interval': 30}
        if url.startswith('rediss://'):
            kwargs['ssl_cert_reqs'] = 'required'
        self.client = redis.Redis.from_url(url, **kwargs)
        self.client.ping()

    def _digest(self, key: str) -> str:
        return hashlib.sha256(str(key).encode('utf-8')).hexdigest()

    def _failure_key(self, key: str) -> str:
        return self.prefix + 'fail:' + self._digest(key)

    def _lock_key(self, key: str) -> str:
        return self.prefix + 'lock:' + self._digest(key)

    def allowed(self, key: str, now: float | None = None) -> bool:
        del now  # Redis provides the authoritative clock for expiry.
        if self.client.exists(self._lock_key(key)):
            return False
        count = self.client.get(self._failure_key(key))
        return count is None or int(count) < self.max_failures

    def failure(self, key: str, now: float | None = None) -> None:
        del now
        failure_key = self._failure_key(key)
        count = int(self.client.incr(failure_key))
        if count == 1:
            self.client.expire(failure_key, self.window_seconds)
        if count >= self.max_failures:
            self.client.setex(self._lock_key(key), self.lockout_seconds, '1')

    def success(self, key: str) -> None:
        self.client.delete(self._failure_key(key), self._lock_key(key))


class SessionStore:
    """Opaque, expiring sessions with a separate CSRF token.

    This store is intentionally in-memory for the prototype. Production should
    use a shared encrypted session store or external IdP so multiple instances
    share revocation and expiry state.
    """

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    def create(self, identity: Identity, now: float | None = None) -> Session:
        now = time.time() if now is None else now
        session = Session(
            token=secrets.token_urlsafe(32),
            csrf_token=secrets.token_urlsafe(32),
            identity=identity,
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        with self._lock:
            self._purge(now)
            self._sessions[session.token] = session
        return session

    def get(self, token: str | None, now: float | None = None) -> Session | None:
        if not token:
            return None
        now = time.time() if now is None else now
        with self._lock:
            self._purge(now)
            session = self._sessions.get(token)
            if not session or session.expires_at <= now:
                return None
            return session

    def revoke(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sessions.pop(token, None)

    def _purge(self, now: float) -> None:
        expired = [token for token, session in self._sessions.items() if session.expires_at <= now]
        for token in expired:
            self._sessions.pop(token, None)


class RedisSessionStore:
    """Redis-backed session store for multi-instance production deployments."""

    def __init__(self, url: str | None = None, ttl_seconds: int = SESSION_TTL_SECONDS, client=None):
        self.ttl_seconds = ttl_seconds
        self.prefix = 'ezwatek:session:'
        if client is not None:
            self.client = client
            return
        if not url:
            raise RuntimeError('REDIS_URL is required when SESSION_STORE=redis')
        try:
            import redis
        except ImportError as error:
            raise RuntimeError('Install requirements-production.txt for Redis sessions') from error
        kwargs = {'decode_responses': True, 'socket_timeout': 3, 'health_check_interval': 30}
        if url.startswith('rediss://'):
            kwargs['ssl_cert_reqs'] = 'required'
        self.client = redis.Redis.from_url(url, **kwargs)
        self.client.ping()

    def _key(self, token: str) -> str:
        return self.prefix + token

    @staticmethod
    def _encode(session: Session) -> str:
        return json.dumps({
            'token': session.token,
            'csrf_token': session.csrf_token,
            'username': session.identity.username,
            'roles': list(session.identity.roles),
            'created_at': session.created_at,
            'expires_at': session.expires_at,
        }, separators=(',', ':'))

    @staticmethod
    def _decode(value: str) -> Session:
        data = json.loads(value)
        return Session(
            token=str(data['token']),
            csrf_token=str(data['csrf_token']),
            identity=Identity(str(data['username']), tuple(str(role) for role in data['roles'])),
            created_at=float(data['created_at']),
            expires_at=float(data['expires_at']),
        )

    def create(self, identity: Identity, now: float | None = None) -> Session:
        now = time.time() if now is None else now
        session = Session(
            token=secrets.token_urlsafe(32),
            csrf_token=secrets.token_urlsafe(32),
            identity=identity,
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        self.client.setex(self._key(session.token), self.ttl_seconds, self._encode(session))
        return session

    def get(self, token: str | None, now: float | None = None) -> Session | None:
        if not token:
            return None
        try:
            session = self._decode(self.client.get(self._key(token)))
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return None
        now = time.time() if now is None else now
        if session.expires_at <= now:
            self.revoke(token)
            return None
        return session

    def revoke(self, token: str | None) -> None:
        if token:
            self.client.delete(self._key(token))


class IAMService:
    """Local IAM facade with password + MFA + RBAC enforcement."""

    def __init__(self):
        session_store = os.environ.get('SESSION_STORE', 'memory').lower()
        redis_url = os.environ.get('REDIS_URL')
        if session_store == 'redis':
            self.sessions = RedisSessionStore(redis_url)
        elif session_store == 'memory':
            self.sessions = SessionStore()
        else:
            raise RuntimeError('SESSION_STORE must be memory or redis')
        rate_limit_store = os.environ.get('RATE_LIMIT_STORE', session_store).lower()
        if rate_limit_store == 'redis':
            self.login_throttle = RedisLoginThrottle(redis_url)
        elif rate_limit_store == 'memory':
            self.login_throttle = LoginThrottle()
        else:
            raise RuntimeError('RATE_LIMIT_STORE must be memory or redis')
        self.audit_log = AuditLog()
        self._dummy_hash = hash_password("not-a-real-password-constant")

    @staticmethod
    def _configured_identity() -> tuple[str | None, str | None, str | None, tuple[str, ...]]:
        username = os.environ.get("IAM_ADMIN_USERNAME")
        password_hash = os.environ.get("IAM_ADMIN_PASSWORD_HASH")
        totp_secret = os.environ.get("IAM_MFA_TOTP_SECRET")
        roles_text = os.environ.get("IAM_ADMIN_ROLES")
        if roles_text is None:
            configured_roles = ("owner",)
        else:
            configured_roles = tuple(
                role.strip() for role in roles_text.split(",") if role.strip() in ROLE_PERMISSIONS
            )
        return username, password_hash, totp_secret, configured_roles

    @staticmethod
    def _normalize_username(username: str) -> str:
        if not isinstance(username, str):
            return ""
        normalized = username.strip()
        return normalized if USERNAME_RE.fullmatch(normalized) else ""

    def authenticate(self, username: str, password: str, mfa_code: str, client_key: str) -> tuple[Identity | None, str]:
        if not self.login_throttle.allowed(client_key):
            self.audit_log.record('auth.login.rate_limited', success=False, client_ip=client_key)
            return None, "rate_limited"
        configured_username, password_hash, totp_secret, roles = self._configured_identity()
        normalized_username = self._normalize_username(username)
        username_ok = bool(configured_username and hmac.compare_digest(normalized_username, configured_username.strip()))
        password_ok = verify_password(password, password_hash) if password_hash else verify_password(password, self._dummy_hash)
        production = os.environ.get("APP_ENV", "development").lower() == "production"
        require_mfa = production or os.environ.get("IAM_REQUIRE_MFA", "1") == "1"
        mfa_ok = verify_totp(totp_secret, mfa_code) if totp_secret else False
        if not require_mfa:
            mfa_ok = True
        if not (username_ok and password_ok and mfa_ok and roles):
            self.login_throttle.failure(client_key)
            self.audit_log.record('auth.login.failed', actor=normalized_username or None, success=False, client_ip=client_key, details={'reason': 'invalid_credentials'})
            return None, "invalid_credentials"
        self.login_throttle.success(client_key)
        identity = Identity(normalized_username, roles)
        self.audit_log.record('auth.login.succeeded', actor=identity.username, success=True, client_ip=client_key, details={'roles': ','.join(identity.roles)})
        return identity, "ok"

    def login(self, username: str, password: str, mfa_code: str, client_key: str) -> tuple[Session | None, str]:
        identity, reason = self.authenticate(username, password, mfa_code, client_key)
        return (self.sessions.create(identity), reason) if identity else (None, reason)

    def session_from_cookie(self, cookie_header: str | None) -> Session | None:
        if not cookie_header:
            return None
        jar = SimpleCookie()
        try:
            jar.load(cookie_header)
        except Exception:
            return None
        for name in ("__Host-ezwatek_session", "ezwatek_session"):
            if name in jar:
                return self.sessions.get(jar[name].value)
        return None

    @staticmethod
    def session_cookie(session: Session, secure: bool) -> str:
        name = "__Host-ezwatek_session" if secure else "ezwatek_session"
        attributes = [f"{name}={session.token}", "Path=/", "HttpOnly", "SameSite=Strict", f"Max-Age={SESSION_TTL_SECONDS}"]
        if secure:
            attributes.append("Secure")
        return "; ".join(attributes)

    @staticmethod
    def clear_cookies(secure: bool) -> tuple[str, str]:
        attributes = ["Path=/", "HttpOnly", "SameSite=Strict", "Max-Age=0"]
        if secure:
            attributes.append("Secure")
        suffix = "; ".join(attributes)
        return tuple(f"{name}=; {suffix}" for name in ("__Host-ezwatek_session", "ezwatek_session"))

    @staticmethod
    def csrf_valid(session: Session | None, provided: str | None) -> bool:
        return bool(session and provided and hmac.compare_digest(session.csrf_token, provided))
