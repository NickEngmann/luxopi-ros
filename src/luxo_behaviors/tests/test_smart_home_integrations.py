import json
import os

import pytest

from luxo_behaviors.integrations.api_clients import (
    ApiError, HomeAssistantClient, MusicAssistantClient, default_music_assistant_url,
    integration_config,
)
from luxo_behaviors.integrations.home_assistant_events import normalize_command


class Response:
    status = 200

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return json.dumps(self.value).encode()


def test_home_assistant_state_and_service_calls_are_authenticated_and_bounded():
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, request.get_header("Authorization"),
                      json.loads(request.data), timeout))
        return Response({"entity_id": "sensor.luxopi_state"})

    client = HomeAssistantClient("http://ha.local/", "test-token", opener=opener)
    client.set_state("sensor.luxopi_state", "IDLE", {"owner": ""})
    client.call_service("media_player", "select_source", {
        "entity_id": "media_player.robot", "source": "Spotify",
    })
    assert calls[0][0] == "http://ha.local/api/states/sensor.luxopi_state"
    assert calls[0][1] == "Bearer test-token"
    assert calls[1][0] == "http://ha.local/api/services/media_player/select_source"
    assert calls[1][2]["source"] == "Spotify"
    with pytest.raises(ValueError):
        client.set_state("sensor.luxopi; rm -rf", "IDLE")


def test_music_assistant_search_resolves_then_routes_to_sendspin_player():
    calls = []

    def opener(request, timeout):
        payload = json.loads(request.data)
        calls.append((request.full_url, request.get_header("Authorization"), payload))
        response = ({"tracks": [{"uri": "spotify://track/123"}]}
                    if payload["command"] == "music/search" else {"success": True})
        return Response(response)

    client = MusicAssistantClient("ws://ma.local:8095/ws", "ma-token", "sendspin-luxopi", opener=opener)
    client.command("play_media", query="jazz piano")
    assert [call[2]["command"] for call in calls] == [
        "music/search", "player_queues/play_media",
    ]
    assert calls[1][2]["args"] == {
        "queue_id": "sendspin-luxopi", "media": "spotify://track/123",
    }
    assert calls[0][0] == "http://ma.local:8095/api"
    assert all(call[1] == "Bearer ma-token" for call in calls)
    with pytest.raises(ValueError):
        client.command("play_media", query="x" * 241)
    with pytest.raises(ValueError):
        client.command("arbitrary_rpc")


@pytest.mark.parametrize("data,expected", [
    ({"command": "animation", "name": "nod"},
     {"kind": "animation", "name": "nod"}),
    ({"command": "music", "operation": "play_media", "query": "jazz"},
     {"kind": "music", "operation": "play_media", "query": "jazz"}),
    ({"command": "music", "operation": "select_source", "source": "Spotify"},
     {"kind": "music", "operation": "select_source", "source": "Spotify"}),
    ({"command": "set_joint", "name": "base", "angle": 999}, None),
    ({"command": "animation", "name": "x" * 81}, None),
])
def test_home_assistant_event_commands_are_high_level_allowlisted(data, expected):
    assert normalize_command(data) == expected


def test_reachy_style_file_config_and_music_assistant_same_host_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXOPI_CONFIG_DIR", str(tmp_path))
    (tmp_path / "ha_token").write_text("ha-secret\n")
    (tmp_path / "ma_token").write_text("ma-secret\n")
    (tmp_path / "ma_url").write_text("ws://garden.local:8095/ws\n")
    assert integration_config("ha", default_url="http://garden.local:8123") == (
        "http://garden.local:8123", "ha-secret")
    assert integration_config("ma") == ("ws://garden.local:8095/ws", "ma-secret")
    assert default_music_assistant_url("https://garden.local:8123") == "http://garden.local:8095"


def test_sendspin_is_a_separate_systemd_service_not_a_ros_child():
    from pathlib import Path

    unit = Path(__file__).parents[3] / "systemd" / "luxopi-sendspin.service"
    text = unit.read_text()
    assert "ExecStart=/usr/bin/sendspin daemon" in text
    assert "--hardware-volume false" in text
    assert "ExecStartPre" not in text
