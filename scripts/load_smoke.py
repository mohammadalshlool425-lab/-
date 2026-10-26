#!/usr/bin/env python3
"""Run a bounded, read-only HTTP smoke load against a local or staging target."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import statistics
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def one_request(url: str, timeout: float) -> tuple[int, float]:
    started = time.perf_counter()
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Ezwatek-load-smoke/1"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310
        response.read(4096)
        return response.status, (time.perf_counter() - started) * 1000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--allow-remote", action="store_true", help="explicitly allow a non-local target")
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        parser.error("--url must be an HTTP(S) URL")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} and not args.allow_remote:
        parser.error("refusing a remote target; use --allow-remote only for an approved staging host")
    if not 1 <= args.requests <= 10_000 or not 1 <= args.concurrency <= 100 or args.concurrency > args.requests:
        parser.error("requests must be 1..10000 and concurrency must be 1..100 and no greater than requests")

    results: list[tuple[int, float]] = []
    errors = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(one_request, args.url, args.timeout) for _ in range(args.requests)]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                errors += 1
    latencies = [latency for _, latency in results]
    sorted_latencies = sorted(latencies)
    p95 = sorted_latencies[min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.95))] if sorted_latencies else None
    summary = {
        "url": f"{parsed.scheme}://{parsed.hostname}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}{parsed.path}",
        "requested": args.requests,
        "completed": len(results),
        "errors": errors,
        "non_200": sum(status != 200 for status, _ in results),
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else None,
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "p95": round(p95, 2) if p95 is not None else None,
            "max": round(max(latencies), 2) if latencies else None,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return 0 if errors == 0 and summary["non_200"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
