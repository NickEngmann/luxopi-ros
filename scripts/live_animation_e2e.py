#!/usr/bin/env python3
"""Verify autonomous mesh motion and click-latched petting on the live dashboard."""

import argparse
import json
import time

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()
    base = args.url.rstrip("/")
    result = {"url": base, "checks": []}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base, wait_until="domcontentloaded", timeout=30_000)
        page.locator("canvas").first.wait_for(state="visible", timeout=15_000)

        def state():
            response = page.request.get(base + "/api/state", timeout=5000)
            assert response.ok, f"dashboard returned HTTP {response.status}"
            return response.json()

        deadline = time.monotonic() + args.timeout
        start_positions = state().get("positions", [])
        auto_samples = []
        while time.monotonic() < deadline:
            sample = state()
            if sample.get("animation"):
                auto_samples.append(sample)
                if len(auto_samples) >= 3:
                    break
            page.wait_for_timeout(500)
        assert auto_samples, "autonomous idle driver did not start an animation"
        auto_name = auto_samples[0]["animation"]
        auto_positions = auto_samples[-1].get("positions", [])
        auto_delta = max(
            (abs(a - b) for a, b in zip(start_positions, auto_positions)), default=0.0
        )
        assert auto_delta > 0.005, {"animation": auto_name, "joint_delta": auto_delta}
        result["checks"].append({
            "name": "autonomous_idle_animation_moves_mesh",
            "animation": auto_name,
            "joint_delta_rad": auto_delta,
        })

        # The pad is a click-to-latch control: one click must sustain the real
        # petting state/action long enough to observe its motion.
        page.locator('[data-petting-zone="antenna"]').click()
        pet_deadline = time.monotonic() + 10
        pet_samples = []
        while time.monotonic() < pet_deadline:
            sample = state()
            if sample.get("state") == "PETTING" and sample.get("animation"):
                pet_samples.append(sample)
                if len(pet_samples) >= 3:
                    break
            page.wait_for_timeout(250)
        assert pet_samples, "one antenna click did not sustain the real PETTING animation"
        pet_name = pet_samples[0]["animation"]
        before_release = pet_samples[0].get("positions", [])
        after_motion = pet_samples[-1].get("positions", [])
        pet_delta = max((abs(a - b) for a, b in zip(before_release, after_motion)), default=0.0)
        assert pet_delta > 0.005, {"animation": pet_name, "joint_delta": pet_delta}
        page.locator('[data-petting-zone="antenna"]').click()
        release_deadline = time.monotonic() + 12
        while time.monotonic() < release_deadline:
            sample = state()
            if sample.get("state") == "IDLE" and not sample.get("animation"):
                break
            page.wait_for_timeout(250)
        else:
            raise AssertionError("releasing the antenna did not return to IDLE")
        result["checks"].append({
            "name": "click_latched_petting_moves_and_releases",
            "animation": pet_name,
            "joint_delta_rad": pet_delta,
        })

        # An obstacle is a held sensor stimulus. It must reach the classifier
        # and bounded retreat controller while an animation is moving.
        page.locator("#animationNameSelect").select_option("nod")
        page.locator("#runAnimation").click()
        animation_deadline = time.monotonic() + 12
        while time.monotonic() < animation_deadline:
            sample = state()
            if sample.get("animation") == "nod":
                break
            page.wait_for_timeout(200)
        else:
            raise AssertionError("manual nod did not start for obstacle scenario")
        before_obstacle = sample.get("positions", [])
        obstacle = page.locator('[data-side="left"]')
        obstacle.click()
        obstacle_deadline = time.monotonic() + 8
        while time.monotonic() < obstacle_deadline:
            sample = state()
            motion = sample.get("motion", {})
            if sample.get("sensors", {}).get("left_severity") == "warning" and motion.get("avoidance_mode") == "adjust":
                break
            page.wait_for_timeout(200)
        else:
            raise AssertionError({"obstacle_not_classified": sample.get("sensors"), "motion": sample.get("motion")})
        obstacle_delta = max(
            (abs(a - b) for a, b in zip(before_obstacle, sample.get("positions", []))),
            default=0.0,
        )
        assert obstacle_delta > 0.005, {"avoidance": motion, "joint_delta": obstacle_delta}
        obstacle.click()
        clear_deadline = time.monotonic() + 8
        while time.monotonic() < clear_deadline:
            sample = state()
            if sample.get("sensors", {}).get("left_severity") == "safe":
                break
            page.wait_for_timeout(200)
        else:
            raise AssertionError("released virtual obstacle did not classify clear")
        result["checks"].append({
            "name": "virtual_obstacle_reaches_classifier_and_retreat",
            "severity": "warning",
            "avoidance_mode": "adjust",
            "joint_delta_rad": obstacle_delta,
            "release_severity": sample["sensors"].get("left_severity"),
            "post_clear_mode": sample.get("motion", {}).get("avoidance_mode"),
        })

        assert not errors, errors
        result["page_errors"] = errors
        browser.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
