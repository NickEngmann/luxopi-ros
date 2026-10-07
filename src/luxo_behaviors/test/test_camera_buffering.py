import ast
import textwrap
from queue import Queue
from pathlib import Path

import pytest

from luxo_behaviors.MultiMsgSync import TwoStageHostSeqSync
from luxo_behaviors.camera_queue import (
    OUTPUT_QUEUE_CAPACITY,
    create_output_queues,
    enqueue_latest,
)


class FakeFrame:
    def __init__(self, sequence):
        self.sequence = sequence

    def getSequenceNum(self):
        return self.sequence


class FakeDetections(FakeFrame):
    def __init__(self, sequence, count):
        super().__init__(sequence)
        self.detections = [None] * count


def test_sync_discards_oldest_unmatched_sequences():
    sync = TwoStageHostSeqSync(max_pending_sequences=3)
    for sequence in range(10):
        sync.add_msg(FakeFrame(sequence), "color")

    assert len(sync.msgs) == 3
    assert list(sync.msgs) == ["7", "8", "9"]


def test_sync_returns_matching_frame_and_discards_older_pending_data():
    sync = TwoStageHostSeqSync(max_pending_sequences=4)
    for sequence in range(3):
        sync.add_msg(FakeFrame(sequence), "color")
        sync.add_msg(FakeDetections(sequence, 1), "detection")

    sync.add_msg(FakeFrame(3), "color")
    sync.add_msg(FakeDetections(3, 1), "detection")
    recognition = FakeFrame(3)
    sync.add_msg(recognition, "recognition")

    result = sync.get_msgs()
    assert result["color"].sequence == 3
    assert result["recognition"] == [recognition]
    assert not sync.msgs


def test_sync_preserves_all_per_face_recognition_results():
    sync = TwoStageHostSeqSync(max_pending_sequences=4)
    sync.add_msg(FakeFrame(7), "color")
    sync.add_msg(FakeDetections(7, 3), "detection")
    recognitions = [FakeFrame(7) for _ in range(3)]
    for result in recognitions:
        sync.add_msg(result, "recognition")

    completed = sync.get_msgs()

    assert completed["len"] == 3
    assert completed["recognition"] == recognitions


def test_depthai_recognition_queue_has_bounded_burst_capacity():
    assert OUTPUT_QUEUE_CAPACITY == {
        "color": 1,
        "detection": 1,
        "recognition": 256,
    }

    class FakeDevice:
        def __init__(self):
            self.calls = []

        def getOutputQueue(self, name, maxSize, blocking):
            self.calls.append((name, maxSize, blocking))
            return name

    device = FakeDevice()
    queues = create_output_queues(device)

    assert queues == {"color": "color", "detection": "detection", "recognition": "recognition"}
    assert device.calls == [
        ("color", 1, False),
        ("detection", 1, False),
        ("recognition", 256, False),
    ]


def test_sync_rejects_unbounded_or_zero_capacity():
    with pytest.raises(ValueError):
        TwoStageHostSeqSync(max_pending_sequences=0)


def test_enqueue_latest_replaces_stale_pending_frame_and_balances_queue():
    pending = Queue(maxsize=1)
    assert enqueue_latest(pending, "old")
    assert enqueue_latest(pending, "new")
    assert pending.get_nowait() == "new"
    pending.task_done()
    pending.join()


def test_embedded_crop_script_evicts_oldest_sequence():
    source_path = (
        Path(__file__).parents[1]
        / "luxo_behaviors"
        / "camera_interaction.py"
    )
    module = ast.parse(source_path.read_text())
    script = next(
        ast.literal_eval(call.args[0])
        for call in ast.walk(module)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "setScript"
    )
    helper_script = textwrap.dedent(script).split("def get_msgs():")[0]

    class FakeScriptNode:
        @staticmethod
        def warn(_message):
            pass

    scope = {"node": FakeScriptNode()}
    exec(helper_script, scope)
    for sequence in range(17):
        scope["add_msg"](FakeFrame(sequence), "preview")

    assert list(scope["msgs"]) == [str(sequence) for sequence in range(2, 17)]
    assert "del msgs[next(iter(msgs))]" in helper_script
