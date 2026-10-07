#!/usr/bin/env python3
"""Stress the simulator dashboard's bounded event queue without motion inputs."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(url, event=None):
    if event is None:
        with urlopen(url + "/api/state", timeout=5) as response:
            return response.status, json.load(response)
    body = json.dumps(event).encode("utf-8")
    req = Request(url + "/api/events", data=body,
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=8) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--requests", type=int, default=512)
    parser.add_argument("--workers", type=int, default=128)
    parser.add_argument("--output", type=Path,
                        default=Path("docs/validation/2026-10-06/dashboard-queue-stress-e2e.json"))
    args = parser.parse_args()
    if not 1 <= args.requests <= 2048 or not 1 <= args.workers <= 256:
        raise SystemExit("requests must be 1..2048 and workers must be 1..256")

    before_code, before = request(args.url)
    assert before_code == 200 and before["health"]["healthy"], before
    event = {"type": "gesture", "gesture": "none"}
    started = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(request, args.url, event) for _ in range(args.requests)]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = time.monotonic() - started
    counts = Counter(status for status, _ in results)
    unexpected = [(status, body) for status, body in results if status not in (202, 429)]
    assert not unexpected, unexpected[:3]

    # A final sentinel proves an overloaded queue drains and accepts new work.
    sentinel = {"type": "gesture", "gesture": "none"}
    status, body = request(args.url, sentinel)
    assert status == 202, (status, body)
    deadline = time.monotonic() + 10
    after = None
    while time.monotonic() < deadline:
        code, snapshot = request(args.url)
        if code == 200 and snapshot["sensors"].get("gesture") == "none":
            after = snapshot
            break
        time.sleep(.1)
    assert after is not None, "dashboard queue did not drain to the final sensor event"
    assert after["health"]["healthy"], after["health"]
    report = {
        "suite": "dashboard_queue_stress_e2e",
        "passed": True,
        "request_count": args.requests,
        "worker_count": args.workers,
        "responses": dict(sorted(counts.items())),
        "elapsed_seconds": round(elapsed, 3),
        "overload_response": 429 in counts,
        "sentinel_accepted": True,
        "bridge_healthy_after_load": after["health"]["healthy"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
