"""Queue helpers for keeping camera processing focused on recent frames."""

from __future__ import annotations

from queue import Empty, Full, Queue
from typing import TypeVar


T = TypeVar("T")

# Two-stage inference emits one recognition message for every detected face.
# Keep small/latest queues for frame-level streams, but leave room for several
# per-face results across the bounded sequence synchronizer window.
OUTPUT_QUEUE_CAPACITY = {
    "color": 1,
    "detection": 1,
    "recognition": 256,
}


def create_output_queues(device):
    """Create bounded DepthAI output queues with per-stream capacities."""
    return {
        name: device.getOutputQueue(name, maxSize=capacity, blocking=False)
        for name, capacity in OUTPUT_QUEUE_CAPACITY.items()
    }


def enqueue_latest(target: Queue[T], item: T) -> bool:
    """Insert an item, evicting the oldest pending item when the queue is full.

    Camera inference is more useful with the most recent frame than with a
    backlog of stale frames. Balance Queue's unfinished-task counter when an
    unprocessed item is evicted so callers can safely use ``join``.
    """
    try:
        target.put_nowait(item)
        return True
    except Full:
        pass

    try:
        target.get_nowait()
    except Empty:
        return False

    target.task_done()
    try:
        target.put_nowait(item)
        return True
    except Full:
        return False
