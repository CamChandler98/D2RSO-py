"""Countdown lifecycle service for active skill trackers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic


class CountdownEventType(StrEnum):
    """Event types emitted by the countdown lifecycle service."""

    UPDATED = "updated"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class CountdownEvent:
    """Immutable event payload emitted for countdown updates/removals."""

    type: CountdownEventType
    skill_id: int
    duration_seconds: float
    remaining_seconds: float
    completed: bool = False


@dataclass(frozen=True, slots=True)
class ActiveCountdown:
    """Read-only snapshot of one active countdown."""

    skill_id: int
    duration_seconds: float
    started_at: float
    ends_at: float
    remaining_seconds: float


@dataclass(slots=True)
class _CountdownState:
    skill_id: int
    duration_seconds: float
    started_at: float
    ends_at: float

    def refresh(self, duration_seconds: float, now: float) -> None:
        self.duration_seconds = duration_seconds
        self.started_at = now
        self.ends_at = now + duration_seconds

    def remaining_seconds(self, now: float) -> float:
        return max(0.0, self.ends_at - now)


class CountdownService:
    """
    Owns cooldown countdown lifecycle independent of any GUI framework.

    Timers are keyed by ``skill_id``. Refreshing an existing ``skill_id`` replaces
    its schedule in-place, which prevents duplicate active trackers.
    """

    def __init__(self, *, time_provider: Callable[[], float] = monotonic) -> None:
        self._time_provider = time_provider
        self._states: dict[int, _CountdownState] = {}
        self._subscribers: list[Callable[[CountdownEvent], None]] = []

    def subscribe(self, callback: Callable[[CountdownEvent], None]) -> None:
        """Register an event subscriber if it is not already registered."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[CountdownEvent], None]) -> None:
        """Remove an event subscriber."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    @property
    def active_count(self) -> int:
        """Number of currently active countdowns."""
        return len(self._states)

    def refresh(
        self,
        *,
        skill_id: int,
        duration_seconds: float,
        now: float | None = None,
    ) -> CountdownEvent:
        """
        Start or restart a countdown by skill ID.

        Existing skill IDs are refreshed in-place to avoid duplicate active timers.
        """
        resolved_now = self._resolve_now(now)
        validated_duration = self._validate_duration(duration_seconds)

        if validated_duration == 0.0:
            self._states.pop(skill_id, None)
            return self._emit(
                CountdownEvent(
                    type=CountdownEventType.REMOVED,
                    skill_id=skill_id,
                    duration_seconds=0.0,
                    remaining_seconds=0.0,
                    completed=True,
                )
            )

        state = self._states.get(skill_id)
        if state is None:
            state = _CountdownState(
                skill_id=skill_id,
                duration_seconds=validated_duration,
                started_at=resolved_now,
                ends_at=resolved_now + validated_duration,
            )
            self._states[skill_id] = state
        else:
            state.refresh(validated_duration, resolved_now)

        return self._emit(self._build_updated_event(state, resolved_now))

    def remove(
        self,
        *,
        skill_id: int,
        completed: bool = False,
        now: float | None = None,
    ) -> CountdownEvent | None:
        """Remove an active countdown and emit a removal event."""
        state = self._states.pop(skill_id, None)
        if state is None:
            return None

        resolved_now = self._resolve_now(now)
        return self._emit(
            CountdownEvent(
                type=CountdownEventType.REMOVED,
                skill_id=skill_id,
                duration_seconds=state.duration_seconds,
                remaining_seconds=(
                    state.remaining_seconds(resolved_now) if not completed else 0.0
                ),
                completed=completed,
            )
        )

    def emit_updates(self, *, now: float | None = None) -> list[CountdownEvent]:
        """
        Emit one event per active countdown.

        Active timers emit ``UPDATED`` events with remaining seconds. Expired timers
        emit ``REMOVED`` events marked as completed and are removed from active state.
        """
        resolved_now = self._resolve_now(now)
        events: list[CountdownEvent] = []

        for skill_id, state in list(self._states.items()):
            if state.remaining_seconds(resolved_now) <= 0.0:
                self._states.pop(skill_id, None)
                events.append(
                    CountdownEvent(
                        type=CountdownEventType.REMOVED,
                        skill_id=skill_id,
                        duration_seconds=state.duration_seconds,
                        remaining_seconds=0.0,
                        completed=True,
                    )
                )
            else:
                events.append(self._build_updated_event(state, resolved_now))

        for event in events:
            self._emit(event)
        return events

    def get_active(
        self, *, skill_id: int, now: float | None = None
    ) -> ActiveCountdown | None:
        """Return the active countdown snapshot for one skill ID."""
        state = self._states.get(skill_id)
        if state is None:
            return None
        resolved_now = self._resolve_now(now)
        return ActiveCountdown(
            skill_id=state.skill_id,
            duration_seconds=state.duration_seconds,
            started_at=state.started_at,
            ends_at=state.ends_at,
            remaining_seconds=state.remaining_seconds(resolved_now),
        )

    def list_active(self, *, now: float | None = None) -> list[ActiveCountdown]:
        """Return snapshots for all active countdowns ordered by skill ID."""
        resolved_now = self._resolve_now(now)
        return [
            ActiveCountdown(
                skill_id=state.skill_id,
                duration_seconds=state.duration_seconds,
                started_at=state.started_at,
                ends_at=state.ends_at,
                remaining_seconds=state.remaining_seconds(resolved_now),
            )
            for _, state in sorted(self._states.items())
        ]

    def _build_updated_event(
        self, state: _CountdownState, now: float
    ) -> CountdownEvent:
        return CountdownEvent(
            type=CountdownEventType.UPDATED,
            skill_id=state.skill_id,
            duration_seconds=state.duration_seconds,
            remaining_seconds=state.remaining_seconds(now),
            completed=False,
        )

    def _resolve_now(self, now: float | None) -> float:
        return self._time_provider() if now is None else float(now)

    def _emit(self, event: CountdownEvent) -> CountdownEvent:
        for callback in list(self._subscribers):
            callback(event)
        return event

    @staticmethod
    def _validate_duration(duration_seconds: float) -> float:
        value = float(duration_seconds)
        if value < 0:
            raise ValueError("duration_seconds must be >= 0")
        return value


__all__ = [
    "ActiveCountdown",
    "CountdownEvent",
    "CountdownEventType",
    "CountdownService",
]
