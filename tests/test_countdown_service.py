import pytest

from d2rso.countdown_service import CountdownEventType, CountdownService


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_retrigger_refreshes_existing_timer_without_duplicates():
    clock = FakeClock(start=10.0)
    service = CountdownService(time_provider=clock)

    first = service.refresh(skill_id=7, duration_seconds=5.0)
    assert first.type is CountdownEventType.UPDATED
    assert first.remaining_seconds == 5.0
    assert service.active_count == 1

    clock.advance(2.0)
    mid = service.emit_updates()
    assert len(mid) == 1
    assert mid[0].remaining_seconds == 3.0

    refreshed = service.refresh(skill_id=7, duration_seconds=5.0)
    assert refreshed.type is CountdownEventType.UPDATED
    assert refreshed.remaining_seconds == 5.0
    assert service.active_count == 1
    assert [item.skill_id for item in service.list_active()] == [7]

    clock.advance(1.0)
    post_refresh = service.emit_updates()
    assert len(post_refresh) == 1
    assert post_refresh[0].type is CountdownEventType.UPDATED
    assert post_refresh[0].remaining_seconds == 4.0


def test_completion_emits_removal_event_and_clears_active_timer():
    clock = FakeClock(start=20.0)
    service = CountdownService(time_provider=clock)

    service.refresh(skill_id=101, duration_seconds=2.0)
    clock.advance(1.0)

    one_second_left = service.emit_updates()
    assert len(one_second_left) == 1
    assert one_second_left[0].type is CountdownEventType.UPDATED
    assert one_second_left[0].remaining_seconds == 1.0
    assert service.active_count == 1

    clock.advance(1.0)
    completed = service.emit_updates()
    assert len(completed) == 1
    assert completed[0].type is CountdownEventType.REMOVED
    assert completed[0].completed is True
    assert completed[0].remaining_seconds == 0.0
    assert service.active_count == 0
    assert service.get_active(skill_id=101) is None


def test_manual_remove_emits_removal_event():
    service = CountdownService()
    service.refresh(skill_id=88, duration_seconds=6.0, now=100.0)

    removed = service.remove(skill_id=88, now=101.0)

    assert removed is not None
    assert removed.type is CountdownEventType.REMOVED
    assert removed.completed is False
    assert removed.remaining_seconds == 5.0
    assert service.active_count == 0


def test_service_supports_callbacks_without_gui_thread():
    service = CountdownService()
    received: list[tuple[CountdownEventType, int]] = []
    service.subscribe(lambda event: received.append((event.type, event.skill_id)))

    service.refresh(skill_id=3, duration_seconds=1.0, now=500.0)
    service.emit_updates(now=501.0)

    assert received == [
        (CountdownEventType.UPDATED, 3),
        (CountdownEventType.REMOVED, 3),
    ]


def test_zero_duration_refresh_emits_completed_removal_and_clears_timer():
    service = CountdownService()
    service.refresh(skill_id=1, duration_seconds=4.0, now=10.0)

    removed = service.refresh(skill_id=1, duration_seconds=0.0, now=11.0)

    assert removed.type is CountdownEventType.REMOVED
    assert removed.completed is True
    assert removed.remaining_seconds == 0.0
    assert service.get_active(skill_id=1, now=11.0) is None
    assert service.active_count == 0


def test_negative_duration_refresh_rejects_invalid_input():
    service = CountdownService()

    with pytest.raises(ValueError, match="duration_seconds must be >= 0"):
        service.refresh(skill_id=5, duration_seconds=-1.0, now=20.0)


def test_emit_updates_mixes_completion_and_active_update_in_same_tick():
    clock = FakeClock(start=0.0)
    service = CountdownService(time_provider=clock)
    service.refresh(skill_id=1, duration_seconds=1.0)
    service.refresh(skill_id=2, duration_seconds=3.0)

    clock.advance(1.5)
    events = service.emit_updates()
    events_by_id = {event.skill_id: event for event in events}

    assert len(events) == 2
    assert events_by_id[1].type is CountdownEventType.REMOVED
    assert events_by_id[1].completed is True
    assert events_by_id[2].type is CountdownEventType.UPDATED
    assert events_by_id[2].remaining_seconds == 1.5
    assert [countdown.skill_id for countdown in service.list_active()] == [2]
