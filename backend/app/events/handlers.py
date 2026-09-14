"""Default operational event handlers."""
from app.events.bus import DomainEvent, bus
from app.services.escalation_service import notify_staff


def handle_call_completed(event: DomainEvent) -> None:
    return None


def handle_call_no_answer(event: DomainEvent) -> None:
    return None


def handle_escalation_created(event: DomainEvent) -> None:
    return None


bus.subscribe("CALL_COMPLETED", handle_call_completed)
bus.subscribe("CALL_NO_ANSWER", handle_call_no_answer)
bus.subscribe("ESCALATION_CREATED", handle_escalation_created)
