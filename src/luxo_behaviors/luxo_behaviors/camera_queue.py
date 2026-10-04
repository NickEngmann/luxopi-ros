"""Queue helpers for keeping camera processing focused on recent frames."""

from __future__ import annotations

from queue import Empty, Full, Queue
from typing import TypeVar


T = TypeVar("T")


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
