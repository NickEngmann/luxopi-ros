"""Small authenticated clients for Home Assistant and Music Assistant APIs.

These integrations are intentionally outbound and optional. Missing credentials,
network loss, or a stopped media server never affect ROS motion or safety.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


HA_DEFAULT_URL = "http://100.110.232.145:8123"
MA_DEFAULT_PORT = 8095


def read_secret(path):
    """Read a single-line secret from the same private-file pattern used by Reachy."""
    try:
        return Path(path).expanduser().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def integration_config(name, *, default_url=None):
    """Resolve LuxoPI service settings; file-backed credentials are the normal path.

    Environment variables remain useful for containers and tests. On the robot,
    credentials live in ~/.config/luxopi and are never placed in launch files.
    """
    prefix = f"LUXOPI_{name.upper()}"
    config_dir = Path(os.environ.get("LUXOPI_CONFIG_DIR", "~/.config/luxopi")).expanduser()
    url = os.environ.get(f"{prefix}_URL", "").strip()
    if not url:
        url = read_secret(config_dir / f"{name.lower()}_url") or (default_url or "")
    token = os.environ.get(f"{prefix}_TOKEN", "").strip()
    if not token:
        token = read_secret(config_dir / f"{name.lower()}_token")
    return url, token


class ApiError(RuntimeError):
    """A remote service returned an error or an invalid response."""


def _base_url(url):
    value = str(url or "").strip().rstrip("/")
    if value.startswith("ws://"):
        value = "http://" + value[5:]
    elif value.startswith("wss://"):
        value = "https://" + value[6:]
    if not value.startswith(("http://", "https://")):
        raise ValueError("base URL must use http or https")
    return value


class HomeAssistantClient:
    """Push robot health/state into Home Assistant's REST state API."""

    def __init__(self, base_url, token, *, timeout=2.0, opener=None):
        self.base_url = _base_url(base_url)
        if not token:
            raise ValueError("Home Assistant token is required")
        self.token = str(token)
        self.timeout = float(timeout)
        self.opener = opener or urllib.request.urlopen

    def set_state(self, entity_id, state, attributes=None):
        if not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", str(entity_id)):
            raise ValueError("invalid Home Assistant entity id")
        if not isinstance(state, (str, int, float, bool)):
            raise ValueError("state must be a scalar")
        payload = json.dumps({"state": state, "attributes": attributes or {}}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/states/{entity_id}", data=payload,
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"}, method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                result = json.loads(response.read(65536).decode("utf-8"))
                if response.status not in (200, 201):
                    raise ApiError(f"Home Assistant returned HTTP {response.status}")
                return result
        except urllib.error.URLError as exc:
            raise ApiError(f"Home Assistant unavailable: {exc}") from exc

    def call_service(self, domain, service, data):
        if not re.fullmatch(r"[a-z_]+", str(domain)) or not re.fullmatch(r"[a-z_]+", str(service)):
            raise ValueError("invalid Home Assistant service")
        if not isinstance(data, dict) or len(data) > 16:
            raise ValueError("service data must be a bounded object")
        request = urllib.request.Request(
            f"{self.base_url}/api/services/{domain}/{service}",
            data=json.dumps(data).encode(),
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"}, method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                result = json.loads(response.read(65536).decode("utf-8"))
                if response.status != 200:
                    raise ApiError(f"Home Assistant returned HTTP {response.status}")
                return result
        except urllib.error.URLError as exc:
            raise ApiError(f"Home Assistant unavailable: {exc}") from exc


class MusicAssistantClient:
    """Send allowlisted queue operations through Music Assistant's REST API.

    This follows Reachy's ``_ma_api`` contract: a command/args JSON body at
    ``/api`` and the Music Assistant profile token as a Bearer credential.
    """

    COMMANDS = {
        "play": "player_queues/play",
        "pause": "player_queues/pause",
        "stop": "player_queues/stop",
        "next": "player_queues/next",
        "previous": "player_queues/previous",
    }

    def __init__(self, base_url, token, player_id, *, timeout=4.0, opener=None):
        self.base_url = _base_url(base_url)
        if self.base_url.endswith("/ws"):
            self.base_url = self.base_url[:-3]
        if not token or not str(player_id).strip():
            raise ValueError("Music Assistant token and Sendspin player id are required")
        self.token = str(token)
        self.player_id = str(player_id).strip()
        self.timeout = float(timeout)
        self.opener = opener or urllib.request.urlopen

    def command(self, operation, *, query=None):
        if operation == "play_media":
            if not isinstance(query, str) or not query.strip() or len(query) > 240:
                raise ValueError("play_media requires a bounded search query")
            search = self._request("music/search", {
                "search_query": query.strip(),
                "media_types": ["track", "album", "playlist"], "limit": 1,
            })
            media = self._first_media_uri(search)
            if not media:
                raise ApiError("Music Assistant search returned no playable media")
            return self._request("player_queues/play_media", {
                "queue_id": self.player_id, "media": media,
            })
        else:
            command = self.COMMANDS.get(operation)
            if command is None:
                raise ValueError("unsupported Music Assistant operation")
            args = {"queue_id": self.player_id}
        return self._request(command, args)

    @staticmethod
    def _first_media_uri(result):
        # API versions/providers wrap results differently (e.g. {tracks: [...]}
        # or {result: {tracks: [...]}}). Walk only JSON containers and return
        # the first valid media URI without depending on a provider's shape.
        pending = [result]
        while pending:
            item = pending.pop(0)
            if isinstance(item, dict):
                uri = item.get("uri")
                if isinstance(uri, str) and "://" in uri and len(uri) <= 512:
                    return uri
                pending.extend(value for value in item.values()
                               if isinstance(value, (dict, list)))
            elif isinstance(item, list):
                pending.extend(value for value in item
                               if isinstance(value, (dict, list)))
        return None

    def _request(self, command, args):
        payload = json.dumps({"command": command, "args": args}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api", data=payload,
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"}, method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                result = json.loads(response.read(262144).decode("utf-8"))
                if response.status != 200:
                    raise ApiError(f"Music Assistant returned HTTP {response.status}")
                if isinstance(result, dict) and result.get("error"):
                    raise ApiError("Music Assistant rejected the request")
                return result
        except urllib.error.URLError as exc:
            raise ApiError(f"Music Assistant unavailable: {exc}") from exc


def default_music_assistant_url(ha_url):
    """Reachy's fallback: Music Assistant on the same host as Home Assistant."""
    from urllib.parse import urlsplit

    parts = urlsplit(_base_url(ha_url))
    if not parts.hostname:
        raise ValueError("Home Assistant URL must include a hostname")
    return f"http://{parts.hostname}:{MA_DEFAULT_PORT}"
