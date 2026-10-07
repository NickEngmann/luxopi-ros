#!/usr/bin/env python3
"""Silent ROS E2E for legacy and simulated petting/contact zones.

Requires an isolated domain-73 graph with dashboard, collision classifier,
simulation interaction adapter, and M3 joint feedback. No hardware/audio path.
"""
import argparse
import datetime
import json
import os
import time
from urllib.request import Request, urlopen


def main():
    if os.environ.get("ROS_DOMAIN_ID") != "73" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise SystemExit("Petting scenarios require domain73 localhost-only")

    import rclpy
    from action_msgs.msg import GoalStatusArray
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Bool, Float32, Int16, String, UInt8

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--dashboard", default="http://127.0.0.1:8091")
    args = parser.parse_args()
    rclpy.init()
    node = Node("petting_zone_scenarios")
    data = {
        "state": None, "animation": None, "joints": [], "petting_events": [],
        "sensor_status": [], "interaction": {}, "action_status": [],
        "camera_emotion": None, "camera_person": None,
    }
    node.create_subscription(String, "/luxo/current_state", lambda m: data.update(state=m.data), 50)
    node.create_subscription(String, "/roarm/current_animation", lambda m: data.update(animation=m.data), 50)
    node.create_subscription(
        JointState, "/joint_states",
        lambda m: data["joints"].append(list(m.position)), 100,
    )
    node.create_subscription(String, "/collision/petting_events",
                             lambda m: data["petting_events"].append(m.data), 50)
    node.create_subscription(String, "/collision/sensor_status",
                             lambda m: data["sensor_status"].append(json.loads(m.data)), 50)
    node.create_subscription(String, "/sim/interaction_status",
                             lambda m: data.update(interaction=json.loads(m.data)), 50)
    node.create_subscription(String, "/camera/emotion", lambda m: data.update(camera_emotion=m.data), 50)
    node.create_subscription(Bool, "/camera/person_present",
                             lambda m: data.update(camera_person=bool(m.data)), 50)
    node.create_subscription(GoalStatusArray, "/play_animation/_action/status",
                             lambda m: data.update(action_status=[int(s.status) for s in m.status_list]), 50)

    proximity = node.create_publisher(Int16, "/i2c/apds9960/proximity", 10)
    distances = [node.create_publisher(Float32, f"/i2c/vl53_{side}/distance", 10)
                 for side in ("left", "right")]
    contacts = {
        name: node.create_publisher(UInt8, f"/touch_sensors/{name}", 10)
        for name in ("head_top", "head_left", "head_right", "head_bottom")
    }
    evidence = {
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "runtime_commit": os.environ.get("LUXOPI_RUNTIME_COMMIT", "unknown"),
        "cases": [], "passed": False,
    }
    controlled_touch = None
    controlled_zone = None
    last_touch_post = 0.0
    last_raw = 0.0
    def api_event(event):
        body = json.dumps(event, separators=(",", ":")).encode()
        request = Request(args.dashboard + "/api/events", data=body,
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=2) as response:
            if response.status != 202:
                raise AssertionError(f"dashboard did not accept event: {response.status}")
    def snapshot():
        with urlopen(args.dashboard + "/api/state", timeout=2) as response:
            return json.load(response)
    def publish_clear_sensors():
        nonlocal last_raw
        proximity.publish(Int16(data=0))
        for publisher in distances:
            publisher.publish(Float32(data=100.0))
        for name, publisher in contacts.items():
            if name != controlled_touch:
                publisher.publish(UInt8(data=0))
        last_raw = time.monotonic()
    def spin(seconds):
        nonlocal last_touch_post
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if time.monotonic() - last_raw > 0.08:
                publish_clear_sensors()
            if controlled_touch and time.monotonic() - last_touch_post > 1.2:
                api_event({"type": "touch", "sensor": controlled_touch, "value": 3})
                last_touch_post = time.monotonic()
            if controlled_zone and time.monotonic() - last_touch_post > 1.2:
                api_event({"type": "petting_zone", "zone": controlled_zone, "active": True})
                last_touch_post = time.monotonic()
            rclpy.spin_once(node, timeout_sec=0.02)
    def wait(predicate, timeout=15, label="condition"):
        end = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= end:
                raise AssertionError(f"timed out waiting for {label}; state={data['state']} "
                                     f"animation={data['animation']} interaction={data['interaction']}")
            spin(0.02)
    def record(name, **fields):
        evidence["cases"].append({"name": name, "passed": True, **fields})
    def clear_wait():
        nonlocal controlled_touch, controlled_zone
        controlled_touch, controlled_zone = None, None
        wait(lambda: data["state"] == "IDLE" and data["animation"] in (None, "")
             and not data["interaction"].get("petting_active"),
             timeout=20, label="petting release returns to IDLE")
        wait(lambda: not data["interaction"].get("error"), timeout=5,
             label="petting lease is released without a stale adapter error")
    def petting_zone(name, mode):
        nonlocal controlled_touch, controlled_zone, last_touch_post
        baseline = data["joints"][-1][:]
        maximum_displacement = 0.0
        event_start = len(data["petting_events"])
        if mode == "head_top":
            controlled_touch = mode
            api_event({"type": "touch", "sensor": mode, "value": 3})
        else:
            controlled_zone = mode
            api_event({"type": "petting_zone", "zone": mode, "active": True})
        last_touch_post = time.monotonic()
        wait(lambda: data["state"] == "PETTING" and data["animation"] == "folded_wiggle",
             timeout=15, label=f"{name} petting state/action")
        if mode == "head_top":
            wait(lambda: any(e.startswith("petting_started:")
                             for e in data["petting_events"][event_start:]),
                 timeout=5, label="collision classifier top petting event")
        else:
            wait(lambda: name in data["interaction"].get("petting_zones", []),
                 timeout=5, label=f"{name} adapter zone telemetry")
        def observe_joint_motion():
            nonlocal maximum_displacement
            if data["joints"]:
                maximum_displacement = max(
                    maximum_displacement,
                    max(abs(a - b) for a, b in zip(baseline, data["joints"][-1])),
                )
            return maximum_displacement > 0.015

        wait(observe_joint_motion,
             timeout=20, label=f"{name} folded_wiggle joint movement")
        assert data["state"] != "COLLISION_AVOIDING"
        if mode == "head_top":
            controlled_touch = None
            api_event({"type": "touch", "sensor": mode, "value": 0})
        else:
            controlled_zone = None
            api_event({"type": "petting_zone", "zone": mode, "active": False})
        wait(lambda: not data["interaction"].get("petting_active"),
             timeout=8, label=f"{name} release observed")
        if mode == "head_top":
            wait(lambda: "petting_stopped:0" in data["petting_events"][event_start:],
                 timeout=5, label="collision classifier top release event")
        clear_wait()
        record("petting_zone_press_release", zone=name,
               active_animation="folded_wiggle", state_after="IDLE",
               maximum_joint_displacement_rad=round(maximum_displacement, 4))

    try:
        wait(lambda: data["joints"] and data["state"] is not None, label="initial ROS feedback")
        assert urlopen(args.dashboard + "/", timeout=3).status == 200
        spin(6.0)  # Preserve collision-node startup grace.
        publish_clear_sensors()
        spin(0.5)
        petting_zone("head_top", "head_top")
        petting_zone("top_front", "top_front")
        petting_zone("antenna", "antenna")

        # Each raw side/bottom FSR channel remains an immediate collision input,
        # never a petting source. Keep the other two channels explicitly clear.
        # The deployed calibration intentionally crosses the side wiring:
        # head_left reports right and head_right reports left by default.
        for sensor, direction in (("head_left", "right"), ("head_right", "left"),
                                  ("head_bottom", "front")):
            event_count = len(data["petting_events"])
            controlled_touch = sensor
            api_event({"type": "touch", "sensor": sensor, "value": 3})
            wait(lambda: any(item.get("direction") == direction and item.get("source") == "fsr"
                             and item.get("active") and item.get("severity") == "danger"
                             for item in data["sensor_status"][-30:]),
                 timeout=5, label=f"{sensor} FSR danger classified as {direction}")
            wait(lambda: data["state"] == "COLLISION_AVOIDING", timeout=5,
                 label=f"{sensor} collision-priority state")
            assert len(data["petting_events"]) == event_count
            assert not data["interaction"].get("petting_active")
            api_event({"type": "touch", "sensor": sensor, "value": 0})
            controlled_touch = None
            wait(lambda: data["state"] == "IDLE", timeout=15,
                 label=f"{sensor} contact release clears collision state")
            record("contact_pad_remains_collision_only", sensor=sensor, direction=direction,
                   petting_event_count=0, state_after="IDLE")

        # Historical MPR121 petting inputs may overlap: releasing one zone must
        # leave the shared session active until the final zone is released.
        controlled_zone = "top_front"
        api_event({"type": "petting_zone", "zone": "top_front", "active": True})
        last_touch_post = time.monotonic()
        wait(lambda: data["state"] == "PETTING", label="overlap first zone")
        controlled_zone = "antenna"
        api_event({"type": "petting_zone", "zone": "antenna", "active": True})
        last_touch_post = time.monotonic()
        wait(lambda: set(data["interaction"].get("petting_zones", [])) == {"top_front", "antenna"},
             label="both petting zones are active")
        api_event({"type": "petting_zone", "zone": "top_front", "active": False})
        wait(lambda: data["interaction"].get("petting_zones") == ["antenna"],
             label="one overlapping zone released")
        assert data["state"] == "PETTING" and data["interaction"].get("petting_active")
        controlled_zone = None
        api_event({"type": "petting_zone", "zone": "antenna", "active": False})
        clear_wait()
        record("overlapping_petting_zones_release_independently", remaining="antenna",
               state_after="IDLE")

        # Exercise the dashboard's no-person flow through its public endpoint.
        # The selected emotion is deliberately non-neutral: it must not recreate
        # presence or refill the mood buffer after explicit absence.
        api_event({"type": "vision", "person_present": True,
                   "emotion": "happy", "metres": 1.2})
        wait(lambda: data["camera_person"] is True and data["camera_emotion"] == "happy",
             timeout=5, label="simulated camera positive output")
        api_event({"type": "vision", "person_present": False,
                   "emotion": "happy", "metres": 1.2})
        wait(lambda: data["camera_person"] is False, timeout=5,
             label="explicit camera person loss")
        absent = snapshot()["sensors"]
        assert absent.get("person_present") is False
        assert absent.get("emotion") is None and absent.get("person_distance") is None
        assert data["state"] == "IDLE"
        spin(2.5)
        assert data["state"] == "IDLE" and data["animation"] in (None, ""), \
            "cleared camera mood buffer still triggered an emotion action"
        record("absent_person_clears_mood_and_dashboard_output", person_present=False,
               emotion_output=None, distance_output=None, state_after="IDLE")
        evidence["passed"] = True
    except BaseException as exc:
        evidence["error"] = repr(exc)
        evidence["last_state"] = data["state"]
        evidence["last_animation"] = data["animation"]
        evidence["last_interaction"] = data["interaction"]
        evidence["last_action_status"] = data["action_status"]
        evidence["last_sensor_status"] = data["sensor_status"][-8:]
        evidence["last_petting_events"] = data["petting_events"][-8:]
        raise
    finally:
        controlled_touch = None
        controlled_zone = None
        publish_clear_sensors()
        try:
            for zone in ("top_front", "antenna"):
                api_event({"type": "petting_zone", "zone": zone, "active": False})
        except Exception:
            pass
        evidence["ended_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(args.output, "w") as output:
            json.dump(evidence, output, indent=2)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
