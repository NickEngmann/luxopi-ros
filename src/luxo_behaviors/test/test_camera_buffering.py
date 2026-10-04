from queue import Queue

import pytest

from luxo_behaviors.MultiMsgSync import TwoStageHostSeqSync
from luxo_behaviors.camera_queue import enqueue_latest


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
