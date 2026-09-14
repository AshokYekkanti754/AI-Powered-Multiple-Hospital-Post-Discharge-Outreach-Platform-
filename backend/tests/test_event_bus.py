from app.events.bus import DomainEvent, EventBus


def test_event_bus_is_idempotent_by_event_id():
    bus = EventBus()
    received = []
    bus.subscribe("CALL_COMPLETED", received.append)
    event = DomainEvent(event_type="CALL_COMPLETED", hospital_id="h1", event_id="event-1")
    assert bus.publish(event) is True
    assert bus.publish(event) is False
    assert len(received) == 1
