#!/usr/bin/env python3
"""Check the articulated cable harness in the simulator's rendered M3 model."""
import argparse
import datetime
import json
import math
from pathlib import Path
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path,
                        default=Path("docs/validation/2026-10-07/wiring-browser-e2e.json"))
    args = parser.parse_args()
    if urlsplit(args.url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Wire-geometry E2E is restricted to a local isolated simulator")
    evidence = {"started_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "passed": False, "hardware_used": False, "cases": []}

    def record(name, **details):
        item = {"scenario": name, "passed": True, **details}
        evidence["cases"].append(item)
        print(json.dumps(item), flush=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=[
            "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader",
        ])
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_function("typeof window.luxoWiringSummary === 'function'", timeout=20_000)
            page.wait_for_function("document.querySelector('#modelSelect').value === 'm3'")
            page.request.post(args.url + "/api/events", data={"type": "simulator_autonomy", "enabled": False})
            page.request.post(args.url + "/api/events", data={"type": "cancel_animation"})
            page.request.post(args.url + "/api/events", data={"type": "state_request", "state": "IDLE"})

            def snapshot():
                return page.evaluate("() => ({wires:window.luxoWiringSummary(), frames:window.luxoM3FramePositions()})")

            def wait_for_pose(target, timeout=20):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    page.request.post(args.url + "/api/events", data={
                        "type": "manual_joint_target",
                        "positions": dict(zip(("base_link_to_link1", "link1_to_link2",
                                                "link2_to_link3", "link3_to_link4",
                                                "link4_to_link5", "link5_to_gripper_link"), target)),
                    })
                    state = page.evaluate("async () => (await fetch('/api/state')).json()")
                    if (state.get("state") == "USER_CONTROL" and
                            max(abs(a - b) for a, b in zip(state.get("positions", []), target)) < .04):
                        return snapshot()
                    page.wait_for_timeout(100)
                raise AssertionError("simulator did not reach the requested joint pose")

            initial = wait_for_pose([0.15, -0.25, 0.55, 0.15, -0.2, 0.2])
            wires = initial["wires"]
            assert wires["visible"] and len(wires["cables"]) == 4, wires
            assert all(cable["vertices"] > 100 for cable in wires["cables"]), wires
            assert all(math.isfinite(v) for point in (wires["start"], wires["end"])
                       for v in point), wires
            record("four_routed_cables_render_with_finite_geometry",
                   cables=wires["cables"], start=wires["start"], end=wires["end"])

            moved = wait_for_pose([-0.8, 0.4, 1.1, -0.5, 1.0, 0.7])
            delta = math.dist(initial["wires"]["end"], moved["wires"]["end"])
            assert moved["wires"]["revision"] > initial["wires"]["revision"]
            assert delta > .04, {"end_effector_cable_motion_m": delta}
            assert math.dist(initial["frames"]["hand_tcp"], moved["frames"]["hand_tcp"]) > .04
            record("cable_harness_recalculates_with_arm_and_wrist_motion",
                   cable_endpoint_delta_m=round(delta, 4),
                   geometry_revision=moved["wires"]["revision"])

            assert not errors, errors
            evidence["passed"] = True
        except BaseException as exc:
            evidence["error"] = repr(exc)
            raise
        finally:
            browser.close()
            evidence["ended_at"] = datetime.datetime.now(datetime.UTC).isoformat()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
