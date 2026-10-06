#!/usr/bin/env python3
"""Verify image upload→CPU vision→camera reaction→measured simulator motion.

Run only against the full simulator with the optional `vision` profile enabled.
The supplied private image paths are read-only inputs and are never copied.
"""

import argparse
import datetime
import json
import math
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_json(url, method="GET", data=None, content_type="application/json", timeout=10):
    request = Request(url, data=data, method=method,
                      headers={"Content-Type": content_type} if data is not None else {})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def snapshot(base_url):
    return http_json(base_url.rstrip("/") + "/api/state")


def wait_for(base_url, predicate, timeout, description):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = snapshot(base_url)
        if predicate(latest):
            return latest
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {description}; last snapshot={latest}")


def submit_image(base_url, path):
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    result = http_json(base_url.rstrip("/") + "/api/vision", "POST",
                       path.read_bytes(), mime, timeout=60)
    return result["vision"]


def displacement(first, current):
    a = first.get("positions", [])
    b = current.get("positions", [])
    if len(a) != len(b) or not a:
        return 0.0
    if not all(math.isfinite(value) for value in a + b):
        return 0.0
    return max(abs(left - right) for left, right in zip(a, b))


def main():
    if os.environ.get("ROS_DOMAIN_ID") != "73" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise SystemExit("Set ROS_DOMAIN_ID=73 and ROS_LOCALHOST_ONLY=1 before image simulator tests")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8083")
    parser.add_argument("--positive", required=True, type=Path, help="private image containing a face")
    parser.add_argument("--negative", required=True, type=Path, help="blank/no-face image")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.positive.is_file() or not args.negative.is_file():
        raise SystemExit("positive and negative input images must exist")

    report = {
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "simulator": args.url,
        "cases": [],
        "passed": False,
    }
    initial = wait_for(args.url, lambda value: value.get("health", {}).get("healthy"),
                       15, "healthy full simulator")
    if initial.get("simulation_backend") != "mujoco":
        raise AssertionError(f"expected MuJoCo backend, got {initial.get('simulation_backend')}")
    # Let the live policy's startup cooldown elapse rather than shortening it.
    time.sleep(6.0)
    idle = wait_for(args.url, lambda value: value.get("state") == "IDLE", 10, "IDLE before face")
    started_at = time.monotonic()
    positive = submit_image(args.url, args.positive)
    assert positive["person_present"] is True and positive["face_count"] > 0
    assert positive["emotion"] in {"neutral", "happy", "sad", "surprise", "anger"}
    assert positive.get("distance_meters") is None
    moved = wait_for(args.url, lambda value:
                     value.get("state") == "EMOTION_REACTING"
                     and bool(value.get("animation"))
                     and displacement(idle, value) > 0.015,
                     35, "face-driven emotion action and joint movement")
    report["cases"].append({
        "name": "actual_pixels_trigger_shared_emotion_action",
        "passed": True,
        "person_present": True,
        "emotion": positive["emotion"],
        "face_count": positive["face_count"],
        "distance_meters": None,
        "state": moved["state"],
        "animation": moved["animation"],
        "joint_displacement_rad": round(displacement(idle, moved), 5),
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
    })
    wait_for(args.url, lambda value: value.get("state") == "IDLE", 45,
             "emotion action returns to IDLE")
    negative = submit_image(args.url, args.negative)
    assert negative["person_present"] is False and negative["face_count"] == 0
    latest = wait_for(args.url, lambda value:
                      value.get("sensors", {}).get("person_present") is False
                      and value.get("sensors", {}).get("emotion") is None
                      and value.get("state") == "IDLE",
                      8, "blank image clears camera presence and mood")
    time.sleep(1.0)
    stable = snapshot(args.url)
    assert stable.get("state") == "IDLE", stable
    assert stable.get("sensors", {}).get("person_present") is False, stable
    report["cases"].append({
        "name": "blank_pixels_clear_camera_without_reaction",
        "passed": True,
        "person_present": latest["sensors"]["person_present"],
        "emotion": latest["sensors"].get("emotion"),
        "state": stable["state"],
    })
    report["passed"] = True
    report["ended_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
