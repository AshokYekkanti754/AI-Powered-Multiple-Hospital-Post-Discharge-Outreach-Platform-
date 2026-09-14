"""Escalation lifecycle and fail-safe staff notification operations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy.orm import Session
from app.db.models.escalation import Escalation, EscalationSeverity, EscalationStatus
from app.db.models.notification import Notification, NotificationChannel
from app.db.models.user import User, UserRole


def _staff(db: Session, hospital_id):
    return db.query(User).filter(User.hospital_id == hospital_id, User.role.in_([UserRole.HOSPITAL_ADMIN, UserRole.CLINICAL_REVIEWER])).all()


def notify_staff(db: Session, *, hospital_id, message: str, include_admins: bool = True) -> int:
    roles = [UserRole.HOSPITAL_ADMIN, UserRole.CLINICAL_REVIEWER] if include_admins else [UserRole.CLINICAL_REVIEWER]
    users = db.query(User).filter(User.hospital_id == hospital_id, User.role.in_(roles), User.is_active.is_(True)).all()
    for user in users:
        db.add(Notification(hospital_id=hospital_id, recipient_user_id=user.id, channel=NotificationChannel.IN_APP, message=message))
    return len(users)


def create_escalation(db: Session, *, hospital_id, patient_id, campaign_id, severity: EscalationSeverity, trigger_reason: str, call_id=None) -> Escalation:
    escalation = Escalation(hospital_id=hospital_id, patient_id=patient_id, campaign_id=campaign_id, call_id=call_id, severity=severity, trigger_reason=trigger_reason)
    db.add(escalation)
    db.flush()
    notify_staff(db, hospital_id=hospital_id, message=f"{severity.value} escalation for patient {patient_id}: {trigger_reason}")
    db.commit()
    db.refresh(escalation)
    # REQ-2: dispatch the 15-minute escalation timeout chain.
    _dispatch_timeout_check(escalation)
    return escalation


def _dispatch_timeout_check(escalation: Escalation, *, countdown: int = 900) -> None:
    """Queue a delayed Celery task that re-checks the escalation after 15 minutes.

    Requires a reachable Redis broker (Celery's backend). When Redis is
    unavailable (unit tests, worker-less dev) this is a no-op; the timeout can
    then be exercised directly via ``enforce_escalation_timeout``.
    """
    try:
        from app.core.queue_events import redis_available

        if not redis_available():
            return
        from app.workers.escalation_timeout_worker import check_escalation_timeout

        fn = getattr(check_escalation_timeout, "apply_async", None)
        if fn is not None:
            fn(args=[str(escalation.id)], countdown=countdown)
    except Exception:  # noqa: BLE001 - scheduling must never break escalation creation
        pass


def enforce_escalation_timeout(
    db: Session,
    *,
    escalation_id,
    now: datetime | None = None,
    timeout_minutes: int = 15,
) -> bool:
    """REQ-2: elevate an escalation to URGENT if it is still OPEN after 15 minutes.

    Marks ``timeout_triggered = True`` and issues a secondary alert to hospital
    administrators via the notifications table. Returns False when the
    escalation is missing, already acknowledged/resolved, or not yet expired.
    """
    escalation = db.query(Escalation).filter(Escalation.id == escalation_id).one_or_none()
    if escalation is None or escalation.status is not EscalationStatus.OPEN:
        return False
    now = now or datetime.now(timezone.utc)
    created = escalation.created_at
    if created is None:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created > now - timedelta(minutes=timeout_minutes):
        return False
    # Elevate severity (never downgrade) and persist the timeout flag.
    if escalation.severity.value != EscalationSeverity.URGENT.value:
        escalation.severity = EscalationSeverity.URGENT
    escalation.timeout_triggered = True
    notify_staff(
        db,
        hospital_id=escalation.hospital_id,
        message=f"Backup alert: escalation {escalation.id} remains unacknowledged after {timeout_minutes} minutes.",
        include_admins=True,
    )
    db.commit()
    db.refresh(escalation)
    return True


def acknowledge_escalation(db: Session, *, escalation: Escalation, user_id, now=None) -> Escalation:
    if escalation.status is not EscalationStatus.OPEN:
        return escalation
    escalation.status = EscalationStatus.ACKNOWLEDGED
    escalation.assigned_user_id = user_id
    escalation.acknowledged_at = now or datetime.now(timezone.utc)
    db.commit()
    db.refresh(escalation)
    return escalation


def resolve_escalation(db: Session, *, escalation: Escalation, notes: str, now=None) -> Escalation:
    escalation.status = EscalationStatus.RESOLVED
    escalation.resolved_at = now or datetime.now(timezone.utc)
    if notes:
        escalation.trigger_reason = f"{escalation.trigger_reason}\nResolution: {notes}"
    db.commit()
    db.refresh(escalation)
    return escalation


def trigger_timeout_backup(db: Session, *, escalation_id, now=None) -> bool:
    """Backward-compatible alias for the 15-minute escalation timeout check."""
    return enforce_escalation_timeout(db, escalation_id=escalation_id, now=now, timeout_minutes=15)
