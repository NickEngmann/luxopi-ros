import pytest

from luxo_behaviors.sim_interaction_rules import parse_petting_event


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
