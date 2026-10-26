"""Background worker loop for Ezwatek job handlers.

Deploy this as a separate process from the HTTP application. Handlers are
registered by the deployment-specific integration layer so provider credentials
never live in the web process or in job payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
from collections.abc import Callable
from typing import Any

from jobs import Job


Handler = Callable[[dict[str, Any]], None]
LOGGER = logging.getLogger("ezwatek.worker")


@dataclass(frozen=True)
class WorkerStats:
    processed: int = 0
    retried: int = 0
    dead_lettered: int = 0
    failed: int = 0


class JobWorker:
    """Process jobs with acknowledgement and bounded retry semantics."""

    def __init__(self, queue, handlers: dict[str, Handler], consumer: str, claim_idle_ms: int = 60_000):
        if not handlers:
            raise ValueError("at least one job handler is required")
        if not consumer or len(consumer) > 100:
            raise ValueError("invalid_consumer")
        self.queue = queue
        self.handlers = dict(handlers)
        self.consumer = consumer
        self.claim_idle_ms = claim_idle_ms

    def process_once(self, count: int = 10, block_ms: int = 1000) -> WorkerStats:
        jobs: list[Job] = []
        claim_stale = getattr(self.queue, "claim_stale", None)
        if callable(claim_stale):
            jobs.extend(claim_stale(self.consumer, self.claim_idle_ms, count))
        jobs.extend(self.queue.reserve(self.consumer, count, block_ms) if self._redis_style() else self.queue.reserve(count))
        processed = retried = dead_lettered = failed = 0
        seen: set[str] = set()
        for job in jobs:
            if job.job_id in seen:
                continue
            seen.add(job.job_id)
            handler = self.handlers.get(job.kind)
            if handler is None:
                failed += 1
                retry_result = self.queue.retry(job)
                if retry_result is None:
                    dead_lettered += 1
                else:
                    retried += 1
                continue
            try:
                handler(dict(job.payload))
            except Exception:
                failed += 1
                LOGGER.exception("job handler failed kind=%s job_id=%s", job.kind, job.job_id)
                retry_result = self.queue.retry(job)
                if retry_result is None:
                    dead_lettered += 1
                else:
                    retried += 1
            else:
                self.queue.ack(job)
                processed += 1
        return WorkerStats(processed, retried, dead_lettered, failed)

    def run(self, stop_event: threading.Event, poll_seconds: float = 1.0) -> None:
        while not stop_event.is_set():
            stats = self.process_once()
            if not stats.processed and not stats.retried and not stats.dead_lettered:
                stop_event.wait(max(0.05, poll_seconds))

    def _redis_style(self) -> bool:
        return callable(getattr(self.queue, "claim_stale", None))
