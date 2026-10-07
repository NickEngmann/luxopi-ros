import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from native_suite_policy import execute_with_timeout, motion_suite_timeout_seconds


def test_continuous_full_playlist_gets_long_timeout_without_extra_flag():
    assert motion_suite_timeout_seconds(
        full_animation_playlist=True,
        feasible_retiming=False,
        continuous_retiming=True,
    ) == 3600


def test_noncontinuous_full_playlist_keeps_existing_timeout():
    assert motion_suite_timeout_seconds(
        full_animation_playlist=True,
        feasible_retiming=False,
        continuous_retiming=False,
    ) == 500


def test_core_motion_probe_does_not_get_full_playlist_budget():
    assert motion_suite_timeout_seconds(
        full_animation_playlist=False,
        feasible_retiming=True,
        continuous_retiming=True,
    ) == 500


def test_expired_suite_writes_timeout_evidence_and_returns_failure():
    with tempfile.TemporaryDirectory() as directory:
        log_path = Path(directory) / "suite.log"
        exit_code, timed_out = execute_with_timeout(
            [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(2)"],
            log_path,
            0.05,
        )
        assert exit_code == 124
        assert timed_out is True
        assert "started" in log_path.read_text()
        assert "TIMED OUT after 0.05 seconds" in log_path.read_text()
