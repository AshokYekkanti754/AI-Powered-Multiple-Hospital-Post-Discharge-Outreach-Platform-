"""Small idempotent event bus with an optional Celery bridge."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
import uuid


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    hospital_id: str
    payload: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable[[DomainEvent], None]]] = defaultdict(list)
        self._processed: set[str] = set()

    def subscribe(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> bool:
        if event.event_id in self._processed:
            return False
        self._processed.add(event.event_id)
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        return True


bus = EventBus()
