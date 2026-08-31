from typing import Any


class ActionQueue:
    """Queue holding queued recovery actions awaiting execution or human approval."""

    def __init__(self):
        self._queue: list[dict[str, Any]] = []

    def enqueue(self, item: dict[str, Any]) -> None:
        self._queue.append(item)

    def dequeue(self) -> dict[str, Any] | None:
        if self._queue:
            return self._queue.pop(0)
        return None

    def size(self) -> int:
        return len(self._queue)
