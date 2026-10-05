import pytest

from luxo_behaviors.sim_interaction_rules import (
    VoiceCueLifecycle, parse_petting_event,
)
from luxo_behaviors.state_machine import completion_matches_owner


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ("petting_started:2", ("petting_started", 2)),
        ("petting_started:255", ("petting_started", 255)),
        ("petting_stopped:0", ("petting_stopped", 0)),
    ],
)
def test_parse_petting_event(event, expected):
    assert parse_petting_event(event) == expected


@pytest.mark.parametrize(
    "event",
    [
        "", "petting_started", "petting_started:nope", "other:50",
        "petting_started:1", "petting_started:256", "petting_stopped:-1",
    ],
)
def test_reject_malformed_or_out_of_range_petting_events(event):
    with pytest.raises(ValueError):
        parse_petting_event(event)


def test_voice_cues_follow_a_session_without_owning_its_state():
    cues = VoiceCueLifecycle()
    cues.transcript()  # The bridge publishes text immediately before listening.
    generation = cues.status("listening")
    assert [cues.pop(), cues.pop()] == ["listening", "acknowledge"]
    assert cues.status("thinking") == generation
    assert cues.pop() == "thinking"
    assert cues.status("speaking") == generation
    assert cues.pop() == "speaking"

    idle_generation = cues.status("idle")
    assert idle_generation != generation
    assert cues.pop() == "settle"
    assert cues.pop() is None
    assert not cues.is_current(generation)


def test_explicit_action_suppresses_queued_cues_without_ending_voice_session():
    cues = VoiceCueLifecycle()
    generation = cues.status("listening")
    assert cues.pop() == "listening"
    cues.status("thinking")
    cues.suppress()
    assert cues.pop() is None
    assert cues.is_current(generation)
    # Only the actual voice-idle event ends this session.
    next_generation = cues.status("idle")
    assert next_generation != generation
    assert cues.pop() is None


def test_completion_is_accepted_only_for_current_state_owner():
    assert completion_matches_owner("user_control", "user_control")
    assert not completion_matches_owner("collision", "animation_command")
    assert not completion_matches_owner("user_control", "animation_command")
