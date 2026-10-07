#!/usr/bin/env python3
"""Stress the simulator HTTP boundary, sensor limits, and retry semantics."""
import argparse
import concurrent.futures
import datetime
import json
import pathlib
import time
import urllib.error
import urllib.request
import uuid


def request(url, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url + path, data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def post(url, event):
    return request(url, "/api/events", event)


def wait_state(url, predicate, timeout=8):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        _, last = request(url, "/api/state")
        if predicate(last):
            return last
        time.sleep(0.05)
    raise AssertionError(f"simulator state condition timed out; last={last}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    report = {"started_at": datetime.datetime.now(datetime.UTC).isoformat(),
              "url": args.url, "cases": [], "passed": False}

    def record(name, **details):
        report["cases"].append({"name": name, "passed": True, **details})

    _, initial = request(args.url, "/api/state")
    assert initial["health"]["healthy"], initial.get("health")
    record("healthy_start", health=initial["health"])
    initial_autonomy = initial.get("sensors", {}).get("simulator_autonomy_enabled", False)
    post(args.url, {"type": "simulator_autonomy", "enabled": False})
    post(args.url, {"type": "voice_active", "active": False})
    post(args.url, {"type": "state_request", "state": "IDLE"})
    wait_state(args.url, lambda s: (
        s.get("state") == "IDLE"
        and s.get("sensors", {}).get("simulator_autonomy_enabled") is False))

    # Identical retries from concurrent HTTP clients must enqueue exactly once;
    # reusing a token for a different command must conflict.
    request_id = "e2e-" + uuid.uuid4().hex
    event = {"type": "light_color", "color": "cyan", "request_id": request_id}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        replies = list(pool.map(lambda _: post(args.url, event), range(16)))
    assert all(code == 202 for code, _ in replies), replies
    assert sum(not body.get("duplicate", False) for _, body in replies) == 1, replies
    conflict = post(args.url, {**event, "color": "purple"})
    assert conflict[0] == 409, conflict
    wait_state(args.url, lambda s: s.get("sensors", {}).get("light_color_requested") == "cyan")
    diagnostics_code, diagnostics = request(args.url, "/api/diagnostics")
    assert diagnostics_code == 200 and diagnostics["event_ingress"]["duplicates"] >= 15
    assert any(row.get("request_id") == request_id and row["outcome"] == "duplicate"
               for row in diagnostics["event_ingress"]["recent"]), diagnostics
    record("concurrent_retry_is_idempotent", retries=len(replies), duplicate_count=sum(
        body.get("duplicate", False) for _, body in replies), conflicting_reuse=conflict[0])

    # Test inclusive API bounds and that the simulator consumes edge values.
    for side in ("left", "right"):
        for value in (0.0, 1.2):
            code, response = post(args.url, {"type": "distance", "side": side, "metres": value})
            assert code == 202, (side, value, code, response)
            snap = wait_state(args.url, lambda s: s.get("sensors", {}).get(f"{side}_distance") == value)
            record("distance_boundary", side=side, metres=value,
                   received=snap["sensors"][f"{side}_distance"])
    for angle in (0, 359):
        code, response = post(args.url, {"type": "audio_direction", "degrees": angle})
        assert code == 202, response
        snap = wait_state(args.url, lambda s: s.get("sensors", {}).get("requested_mic_direction") == angle)
        record("doa_wrap_boundary", degrees=angle, yaw=snap.get("direction"))
    post(args.url, {"type": "voice_active", "active": False})
    idle = wait_state(args.url, lambda s: s.get("state") == "IDLE", timeout=5)
    record("doa_inactive_returns_idle", state=idle["state"], voice_active=idle["voice_active"])
    for sensor in ("head_top", "head_left", "head_bottom", "head_right"):
        for value in (0, 255):
            code, response = post(args.url, {"type": "touch", "sensor": sensor, "value": value})
            assert code == 202, response
            snap = wait_state(args.url, lambda s: s.get("sensors", {}).get(sensor) == value)
            record("touch_boundary", sensor=sensor, value=value)

    # Occupancy/safety edges: simultaneous left+right hazards hold movement;
    # clearing both returns the FSM to a non-hazard state without stale latches.
    for side in ("left", "right"):
        code, response = post(args.url, {"type": "collision", "side": side, "active": True})
        assert code == 202, response
    hazard = wait_state(args.url, lambda s: all(s.get("sensors", {}).get("simulated_obstacles", {}).get(x)
                                                 for x in ("left", "right")))
    record("dual_side_collision_latch", state=hazard["state"],
           obstacles=hazard["sensors"]["simulated_obstacles"])
    for side in ("left", "right"):
        code, response = post(args.url, {"type": "collision", "side": side, "active": False})
        assert code == 202, response
    clear = wait_state(args.url, lambda s: (
        not any(s.get("sensors", {}).get("simulated_obstacles", {}).values())
        and s.get("state") != "COLLISION_AVOIDING"), timeout=10)
    record("collision_clear_recovery", state=clear["state"])

    # API rejection edges: no unsafe request should reach ROS.
    invalid = [
        {"type": "audio_direction", "degrees": 360},
        {"type": "distance", "side": "rear", "metres": 0.2},
        {"type": "distance", "side": "left", "metres": 1.2001},
        {"type": "touch", "sensor": "head_top", "value": 256},
        {"type": "proximity", "value": True},
        {"type": "state_request", "state": "FLY"},
        {"type": "animation", "name": "dance", "speed": 2.01},
        {"type": "brightness", "value": float("nan")},
        {"type": "light_color", "color": "ultraviolet"},
        {"type": "light_control", "enabled": True, "request_id": "../escape"},
    ]
    rejected = []
    for payload in invalid:
        code, body = post(args.url, payload)
        assert code == 400 and body.get("error"), (payload, code, body)
        rejected.append({"type": payload.get("type"), "status": code})
    record("invalid_inputs_rejected", cases=rejected)

    # Concurrent unique events exercise queue draining and bounded audit
    # retention. No event payload is retained in the audit trail.
    stress = [{"type": "gesture", "gesture": "none", "request_id": "stress-" + uuid.uuid4().hex}
              for _ in range(160)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        stress_results = list(pool.map(lambda item: post(args.url, item), stress))
    assert all(code in (202, 429) for code, _ in stress_results), stress_results
    wait_state(args.url, lambda s: s.get("event_ingress", {}).get("queue_depth", 0) == 0, timeout=12)
    _, after_stress = request(args.url, "/api/diagnostics")
    ingress = after_stress["event_ingress"]
    assert ingress["queue_depth"] == 0, ingress
    assert ingress["queue_capacity"] == 64, ingress
    assert len(ingress["recent"]) <= 100, len(ingress["recent"])
    record("concurrent_queue_stress", submitted=len(stress),
           accepted=sum(code == 202 for code, _ in stress_results),
           backpressured=sum(code == 429 for code, _ in stress_results),
           audit_records=len(ingress["recent"]), queue_depth=ingress["queue_depth"])

    # Restore a neutral, unattended simulation state for the next test/user.
    cleanup = [
        {"type": "voice_active", "active": False},
        {"type": "proximity", "value": 0},
        {"type": "distance", "side": "left", "metres": 1.2},
        {"type": "distance", "side": "right", "metres": 1.2},
    ]
    cleanup += [
        {"type": "collision", "side": side, "active": False}
        for side in ("front", "left", "right")
    ]
    cleanup += [
        {"type": "sensor_fault", "side": side, "active": False}
        for side in ("front", "left", "right")
    ]
    cleanup += [
        {"type": "touch", "sensor": sensor, "value": 0}
        for sensor in ("head_top", "head_left", "head_bottom", "head_right")
    ]
    cleanup += [
        {"type": "petting_zone", "zone": zone, "active": False}
        for zone in ("top_front", "antenna")
    ]
    for item in cleanup:
        post(args.url, item)
    wait_state(args.url, lambda s: s.get("state") != "COLLISION_AVOIDING", timeout=10)
    post(args.url, {"type": "state_request", "state": "IDLE"})
    wait_state(args.url, lambda s: s.get("state") == "IDLE")
    post(args.url, {"type": "simulator_autonomy", "enabled": initial_autonomy})

    _, final = request(args.url, "/api/state")
    assert final["health"]["healthy"], final["health"]
    assert final["event_ingress"]["rejected"] >= len(invalid), final["event_ingress"]
    record("healthy_finish", health=final["health"], ingress=final["event_ingress"])
    report.update(passed=True, ended_at=datetime.datetime.now(datetime.UTC).isoformat())
    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    main()
