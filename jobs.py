"""Reliable job queue primitives for Ezwatek background work.

The application can use the in-memory adapter in development. Production uses
Redis Streams with consumer groups, acknowledgements, retry attempts, and a dead
letter stream. A job is data only; external notification/payment providers must
be invoked by an explicitly configured worker handler.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import hashlib
import json
import re
import secrets
import threading
import time
from typing import Any


JOB_KIND_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,79}$")
MAX_JOB_PAYLOAD_BYTES = 32 * 1024
DEFAULT_MAX_ATTEMPTS = 5


class JobQueueError(RuntimeError):
    """Raised when a job cannot be validated or persisted."""


class JobQueueFull(JobQueueError):
    """Raised by the bounded development queue when it is full."""


@dataclass(frozen=True)
class Job:
    job_id: str
    kind: str
    payload: dict[str, Any]
    attempts: int = 0
    enqueued_at: float = 0.0
    stream_id: str | None = None


def _validate_job(kind: str, payload: dict[str, Any]) -> str:
    if not isinstance(kind, str) or not JOB_KIND_RE.fullmatch(kind):
        raise JobQueueError("invalid_job_kind")
    if not isinstance(payload, dict):
        raise JobQueueError("job_payload_must_be_object")
    try:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise JobQueueError("job_payload_not_json") from error
    if len(encoded.encode("utf-8")) > MAX_JOB_PAYLOAD_BYTES:
        raise JobQueueError("job_payload_too_large")
    return encoded


def _dedupe_digest(key: str) -> str:
    return hashlib.sha256(str(key).encode("utf-8")).hexdigest()


class InMemoryJobQueue:
    """Bounded adapter for local development and deterministic unit tests."""

    def __init__(self, max_jobs: int = 1000, max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        if max_jobs < 1:
            raise ValueError("max_jobs must be positive")
        self.max_jobs = max_jobs
        if not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts
        self._pending: deque[Job] = deque()
        self._dead_letters: list[Job] = []
        self._dedupe: dict[str, tuple[str, float]] = {}
        self._lock = threading.RLock()

    def enqueue(self, kind: str, payload: dict[str, Any], dedupe_key: str | None = None, dedupe_seconds: int = 300) -> Job | None:
        _validate_job(kind, payload)
        now = time.time()
        with self._lock:
            self._purge_dedupe(now)
            if dedupe_key:
                digest = _dedupe_digest(dedupe_key)
                existing = self._dedupe.get(digest)
                if existing:
                    return None
            if len(self._pending) >= self.max_jobs:
                raise JobQueueFull("job_queue_full")
            job = Job(secrets.token_hex(16), kind, dict(payload), enqueued_at=now)
            self._pending.append(job)
            if dedupe_key:
                self._dedupe[digest] = (job.job_id, now + max(1, int(dedupe_seconds)))
            return job

    def reserve(self, count: int = 1) -> list[Job]:
        count = max(1, min(int(count), 100))
        with self._lock:
            jobs = []
            for _ in range(min(count, len(self._pending))):
                job = self._pending.popleft()
                jobs.append(replace(job, attempts=job.attempts + 1))
            return jobs

    def ack(self, job: Job) -> None:
        del job

    def retry(self, job: Job) -> Job | None:
        with self._lock:
            if job.attempts >= self.max_attempts:
                self._dead_letters.append(job)
                return None
            retried = replace(job, stream_id=None)
            self._pending.append(retried)
            return retried

    def dead_letters(self) -> list[Job]:
        with self._lock:
            return list(self._dead_letters)

    def _purge_dedupe(self, now: float) -> None:
        expired = [digest for digest, (_, expires_at) in self._dedupe.items() if expires_at <= now]
        for digest in expired:
            self._dedupe.pop(digest, None)


class RedisJobQueue:
    """Reliable Redis Streams queue using consumer groups."""

    def __init__(
        self,
        url: str | None = None,
        stream: str = "ezwatek:jobs",
        group: str = "ezwatek-workers",
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        max_stream_length: int = 100_000,
        client=None,
    ):
        if not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if not isinstance(max_stream_length, int) or max_stream_length < 1:
            raise ValueError("max_stream_length must be positive")
        self.stream = stream
        self.dead_letter_stream = stream + ":dead"
        self.group = group
        self.max_attempts = max_attempts
        self.max_stream_length = max_stream_length
        if not re.fullmatch(r"[a-zA-Z0-9:_-]{1,100}", stream) or not re.fullmatch(r"[a-zA-Z0-9:_-]{1,100}", group):
            raise ValueError("invalid_redis_queue_name")
        if client is not None:
            self.client = client
        else:
            if not url:
                raise RuntimeError("REDIS_URL is required for RedisJobQueue")
            try:
                import redis
            except ImportError as error:
                raise RuntimeError("Install requirements-production.txt for Redis jobs") from error
            kwargs = {
                "decode_responses": True,
                "socket_connect_timeout": 3,
                "socket_timeout": 5,
                "health_check_interval": 30,
            }
            if url.startswith("rediss://"):
                kwargs["ssl_cert_reqs"] = "required"
            self.client = redis.Redis.from_url(url, **kwargs)
            self.client.ping()
        self._ensure_group()

    def _ensure_group(self) -> None:
        try:
            self.client.xgroup_create(self.stream, self.group, id="$", mkstream=True)
        except Exception as error:  # redis-py exposes ResponseError only when imported.
            if "BUSYGROUP" not in str(error):
                raise

    def enqueue(self, kind: str, payload: dict[str, Any], dedupe_key: str | None = None, dedupe_seconds: int = 300) -> Job | None:
        encoded_payload = _validate_job(kind, payload)
        dedupe_redis_key = None
        if dedupe_key:
            dedupe_redis_key = f"{self.stream}:dedupe:{_dedupe_digest(dedupe_key)}"
            if not self.client.set(dedupe_redis_key, "1", nx=True, ex=max(1, int(dedupe_seconds))):
                return None
        job_id = secrets.token_hex(16)
        enqueued_at = time.time()
        fields = {
            "job_id": job_id,
            "kind": kind,
            "payload": encoded_payload,
            "attempts": "0",
            "enqueued_at": str(enqueued_at),
        }
        try:
            stream_id = self.client.xadd(self.stream, fields, maxlen=self.max_stream_length, approximate=True)
        except Exception:
            if dedupe_redis_key:
                self.client.delete(dedupe_redis_key)
            raise
        return Job(job_id, kind, dict(payload), enqueued_at=enqueued_at, stream_id=str(stream_id))

    def reserve(self, consumer: str, count: int = 1, block_ms: int = 1000) -> list[Job]:
        if not isinstance(consumer, str) or not consumer or len(consumer) > 100:
            raise JobQueueError("invalid_consumer")
        count = max(1, min(int(count), 100))
        block_ms = max(0, min(int(block_ms), 60_000))
        response = self.client.xreadgroup(self.group, consumer, {self.stream: ">"}, count=count, block=block_ms)
        jobs: list[Job] = []
        for _, messages in response or []:
            for stream_id, fields in messages:
                jobs.append(self._job_from_fields(str(stream_id), fields))
        return jobs

    def claim_stale(self, consumer: str, min_idle_ms: int = 60_000, count: int = 10) -> list[Job]:
        count = max(1, min(int(count), 100))
        min_idle_ms = max(1_000, min(int(min_idle_ms), 86_400_000))
        result = self.client.xautoclaim(self.stream, self.group, consumer, min_idle_ms, start_id="0-0", count=count)
        messages = result[1] if isinstance(result, (tuple, list)) and len(result) >= 2 else []
        return [self._job_from_fields(str(stream_id), fields) for stream_id, fields in messages]

    def ack(self, job: Job) -> None:
        if job.stream_id:
            self.client.xack(self.stream, self.group, job.stream_id)

    def retry(self, job: Job) -> Job | None:
        """Publish the next attempt before acknowledging the current delivery.

        This preserves at-least-once delivery if Redis is interrupted during a
        retry. A failed acknowledgement can produce a duplicate, which handlers
        must tolerate through their own idempotency keys; losing a job is worse.
        """
        next_attempt = job.attempts + 1
        target_stream = self.dead_letter_stream if next_attempt >= self.max_attempts else self.stream
        stream_id = self.client.xadd(
            target_stream,
            self._fields_for(job, next_attempt),
            maxlen=self.max_stream_length,
            approximate=True,
        )
        self.ack(job)
        if target_stream == self.dead_letter_stream:
            return None
        return replace(job, attempts=next_attempt, stream_id=str(stream_id), enqueued_at=time.time())

    def _fields_for(self, job: Job, attempts: int) -> dict[str, str]:
        return {
            "job_id": job.job_id,
            "kind": job.kind,
            "payload": json.dumps(job.payload, ensure_ascii=False, separators=(",", ":")),
            "attempts": str(attempts),
            "enqueued_at": str(time.time()),
        }

    @staticmethod
    def _job_from_fields(stream_id: str, fields: dict[str, Any]) -> Job:
        try:
            kind = str(fields["kind"])
            payload = json.loads(fields["payload"])
            attempts = int(fields.get("attempts", 0))
            enqueued_at = float(fields.get("enqueued_at", 0))
            job_id = str(fields["job_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise JobQueueError("corrupt_job") from error
        _validate_job(kind, payload)
        return Job(job_id, kind, payload, attempts=attempts, enqueued_at=enqueued_at, stream_id=stream_id)
