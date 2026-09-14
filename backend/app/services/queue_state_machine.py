"""Database-backed queue task outcome transitions (REQ-1, REQ-4, REQ-5, REQ-6).

Every state transition publishes real-time queue telemetry (REQ-1), retries
honour the exponential backoff calculator (REQ-4), maxed-out retries route to
manual follow-up and notify campaign staff (REQ-5), and completed calls are
auto-documented into the Mock EHR (REQ-6).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.queue_events import publish_queue_event
from app.db.models.campaign import Campaign
from app.db.models.call import Call, CallOutcome
from app.db.models.encounter import Encounter
from app.db.models.hospital import Hospital
from app.db.models.manual_followup import ManualFollowUp
from app.db.models.notification import Notification, NotificationChannel
from app.db.models.queue_task import QueueTask, QueueTaskStatus
from app.db.models.user import User, UserRole
from app.services.retry_calculator import next_retry_time

RETRYABLE_OUTCOMES = {CallOutcome.NO_ANSWER, CallOutcome.BUSY, CallOutcome.VOICEMAIL}


def _notify_campaign_staff(db: Session, *, hospital_id, message: str) -> int:
    users = (
        db.query(User)
        .filter(
            User.hospital_id == hospital_id,
            User.role.in_([UserRole.CAMPAIGN_MANAGER, UserRole.HOSPITAL_ADMIN]),
            User.is_active.is_(True),
        )
        .all()
    )
    for user in users:
        db.add(Notification(hospital_id=hospital_id, recipient_user_id=user.id, channel=NotificationChannel.IN_APP, message=message))
    return len(users)


def _latest_encounter(db: Session, *, patient_id, hospital_id) -> Encounter | None:
    return (
        db.query(Encounter)
        .filter(Encounter.patient_id == patient_id, Encounter.hospital_id == hospital_id)
        .order_by(Encounter.discharge_timestamp.desc())
        .first()
    )


def _auto_document_completed(db: Session, *, task: QueueTask, transcript: str | None, now: datetime) -> None:
    """REQ-6: persist structured observations + audit trail for a completed call."""
    from app.ai.documentation_agent import push_post_call_documentation

    if not transcript:
        return
    encounter = _latest_encounter(db, patient_id=task.patient_id, hospital_id=task.hospital_id)
    if encounter is None:
        return
    try:
        push_post_call_documentation(
            db,
            hospital_id=task.hospital_id,
            patient_id=task.patient_id,
            encounter_id=encounter.id,
            transcript=transcript,
            disposition="completed",
            caller_agent_id="queue_state_machine",
        )
    except Exception:  # noqa: BLE001 - auto-documentation must never break the transition
        pass


def apply_call_outcome(
    db: Session,
    *,
    task: QueueTask,
    outcome: CallOutcome,
    partial_transcript: str | None = None,
    callback_at: datetime | None = None,
    duration_seconds: int | None = None,
    now: datetime | None = None,
) -> QueueTask:
    now = now or datetime.now(timezone.utc)
    hospital = db.query(Hospital).filter(Hospital.id == task.hospital_id).one()
    campaign = db.query(Campaign).filter(Campaign.id == task.campaign_id, Campaign.hospital_id == task.hospital_id).one()
    call = Call(queue_task_id=task.id, hospital_id=task.hospital_id, patient_id=task.patient_id, outcome=outcome, partial_transcript=partial_transcript, scheduled_callback_at=callback_at, duration_seconds=duration_seconds)
    db.add(call)

    if outcome in RETRYABLE_OUTCOMES:
        task.retry_count += 1
        if task.retry_count >= campaign.max_retries:
            _route_to_manual_followup(db, task, f"Maximum retries reached after {outcome.value}")
        else:
            task.status = QueueTaskStatus.RETRY_SCHEDULED
            task.scheduled_for = next_retry_time(now, attempt_number=task.retry_count, timezone_name=hospital.timezone, calling_hours_start=hospital.calling_hours_start, calling_hours_end=hospital.calling_hours_end)
    elif outcome is CallOutcome.DROPPED:
        # REQ-4: DROPPED is retryable too — priority boost for fast reconnect,
        # then scheduled within calling hours using exponential backoff.
        task.status = QueueTaskStatus.RETRY_SCHEDULED
        task.priority_score += 100.0
        task.scheduled_for = next_retry_time(now, attempt_number=max(1, task.retry_count), timezone_name=hospital.timezone, calling_hours_start=hospital.calling_hours_start, calling_hours_end=hospital.calling_hours_end)
    elif outcome is CallOutcome.PATIENT_REQUESTED_CALLBACK:
        if callback_at is None:
            raise ValueError("callback_at is required for a requested callback")
        task.status = QueueTaskStatus.CALLBACK_SCHEDULED
        task.scheduled_for = callback_at
    elif outcome is CallOutcome.COMPLETED:
        task.status = QueueTaskStatus.COMPLETED
    else:
        task.status = QueueTaskStatus.ESCALATED
    task.updated_at = now
    task.locked_by_worker = None
    db.commit()
    db.refresh(task)
    try:
        publish_queue_event(db, hospital_id=task.hospital_id)
    except Exception:  # noqa: BLE001
        pass
    if outcome is CallOutcome.COMPLETED:
        _auto_document_completed(db, task=task, transcript=partial_transcript, now=now)
    return task


def _route_to_manual_followup(db: Session, task: QueueTask, reason: str) -> None:
    """REQ-5: max retries reached → MANUAL_FOLLOW_UP + campaign-staff notification."""
    task.status = QueueTaskStatus.MANUAL_FOLLOW_UP
    db.add(ManualFollowUp(hospital_id=task.hospital_id, patient_id=task.patient_id, campaign_id=task.campaign_id, reason=reason))
    _notify_campaign_staff(
        db,
        hospital_id=task.hospital_id,
        message=f"Manual follow-up required for patient {task.patient_id}: {reason}",
    )
