"""Home Assistant event validation; only high-level allowlisted commands pass."""


def normalize_command(event_data):
    if not isinstance(event_data, dict):
        return None
    kind = event_data.get("command")
    if kind == "animation":
        name = event_data.get("name")
        if isinstance(name, str) and name and len(name) <= 80:
            return {"kind": "animation", "name": name}
    if kind == "music":
        operation = event_data.get("operation")
        if operation in {"play", "pause", "stop", "next", "previous"}:
            return {"kind": "music", "operation": operation}
        source = event_data.get("source")
        if operation == "select_source" and source in {"Spotify", "Music Assistant"}:
            return {"kind": "music", "operation": operation, "source": source}
        query = event_data.get("query")
        if operation == "play_media" and isinstance(query, str) and query.strip() and len(query) <= 240:
            return {"kind": "music", "operation": "play_media", "query": query.strip()}
    return None
