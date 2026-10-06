import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from native_suite_policy import motion_suite_timeout_seconds


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
