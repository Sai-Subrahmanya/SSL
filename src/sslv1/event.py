"""Event model and the audit trail.

Every important state transition produces an event carrying enough context
for an audit trail (``PR-SEC-003`` / ``PR-SECURITY-003``).

Events are append-only and are never mutated or deleted by the domain layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Mapping, Optional, Tuple

from .enums import (
    EventSeverity,
    EventSource,
    EventType,
)
from .identity import Identifier
from .time_model import Timestamp


@dataclass(frozen=True)
class Event:
    """An immutable audit record."""

    event_id: int
    timestamp: Timestamp
    device_id: Identifier
    event_type: EventType
    source: EventSource
    severity: EventSeverity
    reason: str
    site_id: Optional[Identifier] = None
    group_id: Optional[Identifier] = None
    lamp_id: Optional[Identifier] = None
    related_fault_id: Optional[str] = None
    actor: Optional[str] = None
    event_data: Mapping[str, object] = field(default_factory=dict)

    def summary(self) -> str:
        location = "/".join(
            str(p) for p in (self.site_id, self.group_id, self.lamp_id) if p is not None
        )
        return "[%s] %s %s %s (%s)" % (
            self.timestamp.ticks,
            location or "-",
            self.event_type.value,
            self.reason,
            self.actor or "system",
        )


class EventLog:
    """Append-only, sequentially numbered event store."""

    def __init__(self) -> None:
        self._events: List[Event] = []
        self._next_id = 1

    def record(
        self,
        timestamp: Timestamp,
        device_id: Identifier,
        event_type: EventType,
        source: EventSource,
        severity: EventSeverity,
        reason: str,
        site_id: Optional[Identifier] = None,
        group_id: Optional[Identifier] = None,
        lamp_id: Optional[Identifier] = None,
        related_fault_id: Optional[str] = None,
        actor: Optional[str] = None,
        event_data: Optional[Mapping[str, object]] = None,
    ) -> Event:
        event = Event(
            event_id=self._next_id,
            timestamp=timestamp,
            device_id=device_id,
            event_type=event_type,
            source=source,
            severity=severity,
            reason=reason,
            site_id=site_id,
            group_id=group_id,
            lamp_id=lamp_id,
            related_fault_id=related_fault_id,
            actor=actor,
            event_data=dict(event_data or {}),
        )
        self._next_id += 1
        self._events.append(event)
        return event

    # -- queries -----------------------------------------------------------
    @property
    def events(self) -> Tuple[Event, ...]:
        return tuple(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    def filter(
        self,
        event_type: Optional[EventType] = None,
        source: Optional[EventSource] = None,
        severity: Optional[EventSeverity] = None,
        lamp_id: Optional[Identifier] = None,
        related_fault_id: Optional[str] = None,
        min_severity: Optional[EventSeverity] = None,
    ) -> Tuple[Event, ...]:
        order = list(EventSeverity)
        floor = order.index(min_severity) if min_severity else None
        result = []
        for event in self._events:
            if event_type is not None and event.event_type is not event_type:
                continue
            if source is not None and event.source is not source:
                continue
            if severity is not None and event.severity is not severity:
                continue
            if lamp_id is not None and event.lamp_id != lamp_id:
                continue
            if related_fault_id is not None and event.related_fault_id != related_fault_id:
                continue
            if floor is not None and order.index(event.severity) < floor:
                continue
            result.append(event)
        return tuple(result)

    def counts_by_type(self) -> Dict[EventType, int]:
        counts: Dict[EventType, int] = {}
        for event in self._events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts
