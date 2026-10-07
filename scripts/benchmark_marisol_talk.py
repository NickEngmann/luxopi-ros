#!/usr/bin/env python3
"""Sequential synthetic-speech ASR/Talk benchmark; never plays reply audio."""

import argparse
import base64
import json
import re
import ssl
import statistics
import time
from pathlib import Path
from urllib.request import Request, urlopen


def normalized(text):
    return re.sub(r"[^a-z0-9 ]+", "", text.casefold()).split()


def word_error_rate(reference, hypothesis):
    expected, actual = normalized(reference), normalized(hypothesis)
    if not expected:
        return 0.0 if not actual else 1.0
    row = list(range(len(actual) + 1))
    for index, word in enumerate(expected, 1):
        next_row = [index]
        for column, observed in enumerate(actual, 1):
            next_row.append(min(
                next_row[-1] + 1,
                row[column] + 1,
                row[column - 1] + (word != observed),
            ))
        row = next_row
    return row[-1] / len(expected)


def request_json(url, payload=None, timeout=45):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = Request(url, data=body, headers=headers)
    with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
        return json.loads(response.read(8 * 1024 * 1024).decode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://marisol.tailf22a5.ts.net:8443")
    parser.add_argument("--case", action="append", nargs=2, metavar=("EXPECTED", "WAV"), required=True)
    parser.add_argument("--source", default="locally synthesized Piper WAV commands")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    status = request_json(base_url + "/api/talk/status")
    guide = request_json(base_url + "/api/talk/guide")
    assert guide.get("api") == "marisol-speech", guide.get("api")
    cases = []
    for expected, filename in args.case:
        wav = Path(filename).read_bytes()
        if len(wav) < 44 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
            raise ValueError(f"not a WAV file: {filename}")
        started = time.perf_counter()
        result = request_json(base_url + "/api/talk/turn", {
            "audio_b64": base64.b64encode(wav).decode("ascii"),
            "mime": "audio/wav",
            "chat": "",
        })
        elapsed = time.perf_counter() - started
        transcript = str(result.get("transcript", ""))
        timings = result.get("timings") or {}
        # Keep only useful timings and metadata. Never persist reply audio.
        cases.append({
            "fixture": Path(filename).name,
            "expected": expected,
            "transcript": transcript,
            "wer": round(word_error_rate(expected, transcript), 4),
            "exact_match": normalized(expected) == normalized(transcript),
            "request_seconds": round(elapsed, 3),
            "asr_seconds": timings.get("asr_s"),
            "total_seconds": timings.get("total_s"),
            "llm_seconds": timings.get("llm_s"),
            "tts_tail_seconds": timings.get("tts_tail_s"),
            "reply_words": len(normalized(result.get("text", ""))),
            "reply_audio_discarded": bool(result.get("m4a_b64")),
            "error": result.get("error"),
        })
    report = {
        "benchmark": "Marisol HTTP Talk API, audio ASR + response generation",
        "source": args.source + "; not human/acoustic accuracy",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoint": base_url + "/api/talk/turn",
        "model_status_before": status,
        "cases": cases,
        "summary": {
            "count": len(cases),
            "exact_matches": sum(case["exact_match"] for case in cases),
            "mean_wer": round(statistics.mean(case["wer"] for case in cases), 4),
            "mean_request_seconds": round(statistics.mean(case["request_seconds"] for case in cases), 3),
            "p95_request_seconds": round(sorted(case["request_seconds"] for case in cases)[min(len(cases)-1, int(.95 * len(cases)))], 3),
        },
        "response_audio_played": False,
        "response_audio_saved": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
