#!/usr/bin/env python3
"""Exercise the dashboard image picker through real vision and ROS motion."""

import argparse
import datetime
import json
import math
import os
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    if os.environ.get("ROS_DOMAIN_ID") != "73" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise SystemExit("Set ROS_DOMAIN_ID=73 and ROS_LOCALHOST_ONLY=1 before browser image tests")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8083")
    parser.add_argument("--positive", required=True, type=Path)
    parser.add_argument("--negative", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.positive, args.negative):
        if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            raise SystemExit(f"missing image or image over 8 MiB: {path.name}")

    report = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "cases": [], "passed": False}
    console_errors = []
    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True, args=[
            "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader",
        ])
        page = browser.new_page(viewport={"width": 1440, "height": 1080})
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_function("document.querySelector('#connectionText').textContent.includes('ROS API')")
            page.wait_for_function("document.querySelector('#modelStatus').textContent.includes('dynamics')", timeout=30000)

            def state():
                return page.evaluate("async () => (await fetch('/api/state')).json()")

            def wait_for(predicate, timeout, label):
                deadline = time.monotonic() + timeout
                last = None
                while time.monotonic() < deadline:
                    last = state()
                    if predicate(last):
                        return last
                    page.wait_for_timeout(100)
                raise AssertionError(f"timed out waiting for {label}: {last}")

            wait_for(lambda value: value.get("health", {}).get("healthy")
                     and value.get("state") == "IDLE", 30, "healthy MuJoCo IDLE")
            time.sleep(6.0)
            baseline = state()
            page.locator("#visionImage").set_input_files(str(args.positive))
            started = time.monotonic()
            page.locator("#analyzeVisionImage").click()
            page.wait_for_function("document.querySelector('#visionImageStatus').textContent.includes('Face detected')", timeout=60000)
            positive_status = page.locator("#visionImageStatus").inner_text()
            positive = wait_for(lambda value:
                value.get("state") == "EMOTION_REACTING"
                and bool(value.get("animation"))
                and len(value.get("positions", [])) == len(baseline.get("positions", []))
                and bool(value.get("positions"))
                and max(abs(a - b) for a, b in zip(value["positions"], baseline["positions"])) > 0.015,
                35, "real image-driven emotion action and joint motion")
            emotion_match = re.search(r"Face detected · ([a-z]+) · (\d+) face", positive_status)
            assert emotion_match, positive_status
            assert positive.get("sensors", {}).get("person_present") is True, positive
            assert positive.get("sensors", {}).get("emotion") == emotion_match.group(1), positive
            report["cases"].append({
                "name": "dashboard_pixels_trigger_emotion_action",
                "passed": True,
                "emotion": emotion_match.group(1),
                "face_count": int(emotion_match.group(2)),
                "state": positive["state"],
                "animation": positive["animation"],
                "joint_displacement_rad": round(max(abs(a - b) for a, b in zip(
                    positive["positions"], baseline["positions"])), 5),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            })

            wait_for(lambda value: value.get("state") == "IDLE", 45, "emotion action recovery")
            page.locator("#visionImage").set_input_files(str(args.negative))
            page.locator("#analyzeVisionImage").click()
            page.wait_for_function("document.querySelector('#visionImageStatus').textContent.includes('No face detected')", timeout=60000)
            negative = wait_for(lambda value:
                value.get("state") == "IDLE"
                and value.get("sensors", {}).get("person_present") is False
                and value.get("sensors", {}).get("emotion") is None,
                8, "blank image clears camera state")
            page.wait_for_timeout(1000)
            assert negative.get("state") == "IDLE"
            assert not console_errors, console_errors
            report["cases"].append({
                "name": "dashboard_blank_image_clears_mood_without_motion",
                "passed": True,
                "person_present": negative["sensors"]["person_present"],
                "emotion": negative["sensors"].get("emotion"),
                "state": negative["state"],
            })
            report["passed"] = True
        finally:
            report["console_errors"] = console_errors
            report["ended_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            browser.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
