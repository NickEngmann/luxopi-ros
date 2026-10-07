#!/usr/bin/env python3
"""Exercise browser microphone capture through local ASR and Piper, silently.

Pass a speech WAV that the configured ASR model can recognize. Chromium feeds
that fixture to getUserMedia; the test never plays response audio through a
host speaker, but verifies that the generated reply WAV is available to the UI.
"""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
import wave

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--input-wav", required=True, type=Path)
    parser.add_argument("--expected-text", default="", help="Optional case-insensitive text fragment")
    parser.add_argument("--record-seconds", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output", type=Path, default=Path("/tmp/luxopi-browser-audio-e2e.json"))
    args = parser.parse_args()
    if urlsplit(args.url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Microphone E2E runs only against localhost; use an SSH tunnel for remote browsers")
    if not 0.5 <= args.record_seconds <= 20 or not 5 <= args.timeout <= 180:
        raise SystemExit("record duration must be 0.5..20 seconds and timeout 5..180 seconds")
    with wave.open(str(args.input_wav), "rb") as source:
        if source.getnframes() <= 0 or source.getnframes() / source.getframerate() > 20:
            raise SystemExit("input WAV must contain 1..20 seconds of audio")
        if source.getnchannels() not in {1, 2} or source.getsampwidth() not in {1, 2, 3, 4}:
            raise SystemExit("input WAV has an unsupported channel count or sample width")

    started = time.monotonic()
    page_errors = []
    report = {"passed": False, "input_wav": str(args.input_wav), "response_audio_played": False}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=[
            "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader",
            "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
            f"--use-file-for-fake-audio-capture={args.input_wav.resolve()}",
        ])
        context = browser.new_context(permissions=["microphone"])
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_function(
                'document.querySelector("#recordMic") && !document.querySelector("#recordMic").disabled',
                timeout=15000,
            )
            previous_state = page.evaluate('async () => (await fetch("/api/state")).json()')
            previous_transcript = str(previous_state.get("transcript", ""))
            previous_audio = str(previous_state.get("audio_response", ""))
            page.locator("#recordMic").click()
            page.wait_for_timeout(int(args.record_seconds * 1000))
            page.locator("#recordMic").click()
            deadline = time.monotonic() + args.timeout
            state = {}
            expected = args.expected_text.casefold().strip()
            while time.monotonic() < deadline:
                state = page.evaluate('async () => (await fetch("/api/state")).json()')
                transcript = str(state.get("transcript", ""))
                recognized = bool(transcript.strip()) and (not expected or expected in transcript.casefold())
                is_new_turn = (
                    transcript != previous_transcript
                    or str(state.get("audio_response", "")) != previous_audio
                )
                if is_new_turn and recognized and state.get("response") and state.get("audio_response"):
                    break
                page.wait_for_timeout(150)
            assert state.get("transcript"), {"reason": "no transcript returned", "last_state": state}
            assert is_new_turn, {"reason": "no new speech turn arrived", "last_state": state}
            if expected:
                assert expected in state["transcript"].casefold(), state["transcript"]
            assert state.get("response"), {"reason": "no spoken reply text", "last_state": state}
            audio_name = state.get("audio_response")
            assert audio_name, {"reason": "Piper response audio was not reported", "last_state": state}
            page.wait_for_function("document.querySelector('#replyAudio').src.includes('audio-response/')")
            response = page.request.get(f"{args.url}/api/audio-response/{audio_name}")
            body = response.body()
            assert response.status == 200, {"audio_http_status": response.status, "body": body[:200].decode(errors="replace")}
            assert body[:4] == b"RIFF" and body[8:12] == b"WAVE", "reply endpoint did not return a WAV file"
            while state.get("status") != "idle" and time.monotonic() < deadline:
                page.wait_for_timeout(150)
                state = page.evaluate('async () => (await fetch("/api/state")).json()')
            assert state.get("status") == "idle", {"reason": "speech turn did not return to idle", "last_state": state}
            assert not page_errors, page_errors
            report.update({
                "passed": True,
                "transcript": state["transcript"],
                "response": state["response"],
                "audio_response": audio_name,
                "audio_bytes": len(body),
                "status": state.get("status"),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            })
        finally:
            browser.close()
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
