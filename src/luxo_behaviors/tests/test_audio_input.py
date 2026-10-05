import io
from pathlib import Path
import wave

import pytest

from luxo_behaviors.audio_input import save_audio, remove_audio, validate_audio_name
from luxo_behaviors.conversation_transport import ConversationClient


def wav(seconds=.2):
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b'\0\0' * int(16000 * seconds))
    return output.getvalue()


def test_pcm_saved_privately_then_cleaned_without_path_escape(tmp_path):
    directory = tmp_path / 'clips'
    name = save_audio(wav(), directory)
    target = directory / name
    assert target.read_bytes() == wav()
    assert target.stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700
    remove_audio(name, directory)
    assert not target.exists()
    for invalid in ('../private.wav', '/tmp/private.wav', 'a.wav', '0' * 32 + '.wav/extra'):
        with pytest.raises(ValueError):
            validate_audio_name(invalid)


@pytest.mark.parametrize('payload', [b'', b'not audio', wav(30.1), wav()[:-5]])
def test_bad_or_oversized_duration_is_rejected_without_file(payload, tmp_path):
    with pytest.raises(ValueError):
        save_audio(payload, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_audio_request_uses_same_bounded_reusable_transport():
    import sys
    child = "import json,sys\nfor line in sys.stdin:\n r=json.loads(line);print(json.dumps({'id':r['id'],'text':'Please nod','response':r['audio_file']}),flush=True)"
    client = ConversationClient([sys.executable, '-u', '-c', child], timeout=3)
    try:
        name = 'a' * 32 + '.wav'
        assert client.request_audio(name)['response'] == name
        with pytest.raises(ValueError):
            client.request_audio('../escape.wav')
    finally:
        client.close()
