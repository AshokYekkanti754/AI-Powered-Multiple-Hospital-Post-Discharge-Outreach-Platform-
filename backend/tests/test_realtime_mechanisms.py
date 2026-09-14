"""Tests for the 7 real-time operational mechanisms + Voice Intake guardrails.

Covers the required scenarios:
  1. 15-minute escalation timeout worker elevates unacknowledged escalations.
  2. Stuck tasks (>90s) reset to RETRY_SCHEDULED and release Redis concurrency locks.
  3. Exponential backoff rolls after-hours calls to the next morning.
  4. Max retries route tasks to MANUAL_FOLLOW_UP.
  5. /api/v1/health returns HTTP 200 with all 6 component statuses.

Plus: real-time queue telemetry publishing (REQ-1), CALL_COMPLETED EHR
auto-documentation (REQ-6) and the Voice Intake guardrail script (REQ-8).
"""
from datetime import datetime, time, timedelta, timezone

from app.db.models.user import UserRole


def _patient(db_session, hospital_id, mrn="M-9"):
    from app.db.models.patient import Patient

    p = Patient(
        hospital_id=hospital_id,
        mrn=mrn,
        first_name="Test",
        last_name="Patient",
        phone_number="+10000000000",
        date_of_birth=datetime(1980, 1, 1).date(),
    )
    db_session.add(p)
    db_session.flush()
    return p


def _campaign(db_session, hospital_id, max_retries=3):
    from app.db.models.campaign import Campaign, CampaignStatus

    c = Campaign(hospital_id=hospital_id, name="Realtime Test", status=CampaignStatus.RUNNING, max_retries=max_retries)
    db_session.add(c)
    db_session.flush()
    return c


def _encounter(db_session, hospital_id, patient_id):
    from app.db.models.encounter import Encounter, RiskTier

    e = Encounter(
        hospital_id=hospital_id,
        patient_id=patient_id,
        discharge_timestamp=datetime.now(timezone.utc),
        risk_score=30.0,
        risk_tier=RiskTier.LOW,
    )
    db_session.add(e)
    db_session.flush()
    return e
# ---------------------------------------------------------------------------
# 1) 15-minute escalation timeout chain (REQ-2)
# ---------------------------------------------------------------------------
def test_timeout_worker_elevates_unacknowledged_escalation(db_session, make_hospital, make_user):
    from app.db.models.escalation import EscalationSeverity, EscalationStatus
    from app.db.models.notification import Notification
    from app.services.escalation_service import acknowledge_escalation, create_escalation, enforce_escalation_timeout
    from app.workers.escalation_timeout_worker import _check_escalation_timeout_impl

    hospital = make_hospital()
    admin = make_user("admin@t.test", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    make_user("clin@t.test", role=UserRole.CLINICAL_REVIEWER, hospital_id=hospital.id)
    patient = _patient(db_session, hospital.id)
    campaign = _campaign(db_session, hospital.id)
    db_session.commit()

    esc = create_escalation(
        db_session,
        hospital_id=hospital.id,
        patient_id=patient.id,
        campaign_id=campaign.id,
        severity=EscalationSeverity.MEDIUM,
        trigger_reason="reported chest pain",
    )
    assert esc.severity is EscalationSeverity.MEDIUM
    assert esc.timeout_triggered is False
    notification_count_after_create = db_session.query(Notification).count()

    # Simulate the fire-and-forget delay: the escalation is now 16 minutes old.
    esc.created_at = datetime.now(timezone.utc) - timedelta(minutes=16)
    db_session.commit()

    result = _check_escalation_timeout_impl(str(esc.id), db=db_session)
    assert result["elevated"] is True

    db_session.refresh(esc)
    assert esc.severity is EscalationSeverity.URGENT
    assert esc.timeout_triggered is True
    # Secondary alert went to both hospital admins + clinical reviewers.
    assert db_session.query(Notification).count() == notification_count_after_create + 2

    # An ACKNOWLEDGED escalation must not be elevated by the worker.
    esc2 = create_escalation(
        db_session,
        hospital_id=hospital.id,
        patient_id=patient.id,
        campaign_id=campaign.id,
        severity=EscalationSeverity.HIGH,
        trigger_reason="headache",
    )
    acknowledge_escalation(db_session, escalation=esc2, user_id=admin.id)
    esc2.created_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    db_session.commit()
    assert enforce_escalation_timeout(db_session, escalation_id=esc2.id) is False
    assert esc2.status is EscalationStatus.ACKNOWLEDGED
# ---------------------------------------------------------------------------
# 2) Stuck task recovery worker (REQ-3)
# ---------------------------------------------------------------------------
def test_stuck_task_reclaimer_resets_and_releases_concurrency_slots(db_session, make_hospital):
    from app.core.redis import semaphore
    from app.db.models.audit_log import AuditLog
    from app.db.models.queue_task import QueueTask, QueueTaskStatus
    from app.workers.stuck_task_reclaimer import reclaim_stuck_tasks

    hospital = make_hospital()
    patient = _patient(db_session, hospital.id, mrn="M-STUCK")
    campaign = _campaign(db_session, hospital.id)
    for i in range(2):
        db_session.add(
            QueueTask(
                hospital_id=hospital.id,
                campaign_id=campaign.id,
                patient_id=patient.id,
                status=QueueTaskStatus.CALLING,
                call_started_at=datetime.now(timezone.utc) - timedelta(seconds=120),  # stale > 90s
                locked_by_worker="worker-1" if i % 2 == 0 else None,  # one has no heartbeat
            )
        )
    db_session.commit()

    with semaphore.acquire(str(hospital.id), 10):
        with semaphore.acquire(str(hospital.id), 10):
            before = semaphore.active_count(str(hospital.id))
            assert before >= 2

            reclaimed = reclaim_stuck_tasks(
                db_session,
                hospital_id=hospital.id,
                now=datetime.now(timezone.utc),
                stale_after_seconds=90,
            )
            assert reclaimed == 2

            after = semaphore.active_count(str(hospital.id))
            assert after == before - 2

    tasks = db_session.query(QueueTask).all()
    assert len(tasks) == 2
    assert all(t.status is QueueTaskStatus.RETRY_SCHEDULED for t in tasks)
    assert all(t.locked_by_worker is None for t in tasks)
    assert db_session.query(AuditLog).filter(AuditLog.action == "queue.reclaim_stuck").count() == 2


def test_stuck_task_reclaimer_ignores_recent_calls(db_session, make_hospital):
    from app.db.models.queue_task import QueueTask, QueueTaskStatus
    from app.workers.stuck_task_reclaimer import reclaim_stuck_tasks

    hospital = make_hospital()
    patient = _patient(db_session, hospital.id, mrn="M-FRESH")
    campaign = _campaign(db_session, hospital.id)
    db_session.add(
        QueueTask(
            hospital_id=hospital.id,
            campaign_id=campaign.id,
            patient_id=patient.id,
            status=QueueTaskStatus.CALLING,
            call_started_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            locked_by_worker="worker-busy",
        )
    )
    db_session.commit()

    reclaimed = reclaim_stuck_tasks(db_session, hospital_id=hospital.id, now=datetime.now(timezone.utc))
    assert reclaimed == 0
    assert db_session.query(QueueTask).one().status is QueueTaskStatus.CALLING
# ---------------------------------------------------------------------------
# 3) Exponential backoff + calling-hours calculator (REQ-4)
# ---------------------------------------------------------------------------
def test_retry_delays_follow_15_45_120_and_clamp_past_three():
    from app.services.retry_calculator import retry_delay_minutes

    assert [retry_delay_minutes(i) for i in (1, 2, 3, 4, 5)] == [15, 45, 120, 120, 120]


def test_after_hours_retry_rolls_forward_to_next_morning():
    from app.services.retry_calculator import next_retry_time

    now = datetime(2026, 9, 14, 19, 50, tzinfo=timezone.utc)
    result = next_retry_time(
        now,
        attempt_number=1,
        timezone_name="UTC",
        calling_hours_start=time(8),
        calling_hours_end=time(20),
    )
    # Candidate = 20:05 (outside window) -> next business day 08:00.
    assert result == datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc)


def test_in_window_retry_uses_plain_backoff():
    from app.services.retry_calculator import next_retry_time

    now = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)
    assert next_retry_time(now, attempt_number=2, timezone_name="UTC", calling_hours_start=time(8), calling_hours_end=time(20)) == now + timedelta(minutes=45)
    assert next_retry_time(now, attempt_number=3, timezone_name="UTC", calling_hours_start=time(8), calling_hours_end=time(20)) == now + timedelta(minutes=120)


# ---------------------------------------------------------------------------
# 4) Max retries -> MANUAL_FOLLOW_UP + campaign notification (REQ-5)
# ---------------------------------------------------------------------------
def test_max_retries_route_to_manual_followup_and_notify_campaign_staff(db_session, make_hospital, make_user):
    from app.db.models.call import CallOutcome
    from app.db.models.manual_followup import ManualFollowUp
    from app.db.models.notification import Notification
    from app.db.models.queue_task import QueueTask, QueueTaskStatus
    from app.services.queue_state_machine import apply_call_outcome

    hospital = make_hospital()
    cm = make_user("campaign@t.test", role=UserRole.CAMPAIGN_MANAGER, hospital_id=hospital.id)
    patient = _patient(db_session, hospital.id, mrn="M-MAX")
    campaign = _campaign(db_session, hospital.id, max_retries=1)
    task = QueueTask(
        hospital_id=hospital.id,
        campaign_id=campaign.id,
        patient_id=patient.id,
        status=QueueTaskStatus.CALLING,
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()

    task = apply_call_outcome(db_session, task=task, outcome=CallOutcome.NO_ANSWER)
    assert task.status is QueueTaskStatus.MANUAL_FOLLOW_UP
    assert db_session.query(ManualFollowUp).count() == 1
    notification = (
        db_session.query(Notification)
        .filter(Notification.recipient_user_id == cm.id)
        .one_or_none()
    )
    assert notification is not None
    assert "Manual follow-up required" in notification.message
# ---------------------------------------------------------------------------
# 5) System component health checks (REQ-7)
# ---------------------------------------------------------------------------
def test_health_endpoint_reports_all_components(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"healthy", "degraded", "unavailable"}
    names = {c["component"] for c in body["components"]}
    assert names == {
        "backend_api",
        "database",
        "queue_workers_redis",
        "ai_providers",
        "mock_ehr",
        "websocket_telemetry",
    }
    assert all(c["status"] in {"HEALTHY", "DEGRADED", "UNAVAILABLE"} for c in body["components"])


# ---------------------------------------------------------------------------
# 1b) Real-time queue telemetry publishing (REQ-1)
# ---------------------------------------------------------------------------
def test_queue_state_change_publishes_telemetry(db_session, make_hospital):
    from app.core.queue_events import _latest
    from app.db.models.call import CallOutcome
    from app.db.models.queue_task import QueueTask, QueueTaskStatus
    from app.services.queue_state_machine import apply_call_outcome

    hospital = make_hospital(max_concurrent_calls=4)
    patient = _patient(db_session, hospital.id, mrn="M-TELEM")
    campaign = _campaign(db_session, hospital.id)
    task = QueueTask(
        hospital_id=hospital.id,
        campaign_id=campaign.id,
        patient_id=patient.id,
        status=QueueTaskStatus.CALLING,
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()

    apply_call_outcome(
        db_session,
        task=task,
        outcome=CallOutcome.COMPLETED,
        partial_transcript="Patient feels fine.",
    )

    payload = _latest.get(str(hospital.id))
    assert payload is not None
    assert payload["event"] == "queue_update"
    for key in ("active_calls", "max_capacity", "pending", "completed", "escalated", "retrying"):
        assert key in payload
    assert payload["max_capacity"] == 4
    assert payload["completed"] >= 1
# ---------------------------------------------------------------------------
# 6) Post-call EHR auto-documentation (REQ-6)
# ---------------------------------------------------------------------------
def test_completed_call_auto_documents_into_mock_ehr(db_session, make_hospital):
    from app.db.models.call import CallOutcome
    from app.db.models.ehr_audit import EHRAuditTrail
    from app.db.models.observation import Observation
    from app.db.models.queue_task import QueueTask, QueueTaskStatus
    from app.services.queue_state_machine import apply_call_outcome

    hospital = make_hospital()
    patient = _patient(db_session, hospital.id, mrn="M-DOC")
    encounter = _encounter(db_session, hospital.id, patient.id)
    campaign = _campaign(db_session, hospital.id)
    task = QueueTask(
        hospital_id=hospital.id,
        campaign_id=campaign.id,
        patient_id=patient.id,
        status=QueueTaskStatus.CALLING,
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(task)
    db_session.commit()

    transcript = (
        "Agent: May I verify I am speaking with Test Patient?\n"
        "Test: Yes, this is Test Patient.\n"
        "Agent: Since you left the hospital, have you experienced any new or worsening symptoms?\n"
        "Test: I have chest pain and a fever."
    )
    apply_call_outcome(
        db_session,
        task=task,
        outcome=CallOutcome.COMPLETED,
        partial_transcript=transcript,
    )

    observations = db_session.query(Observation).filter(Observation.patient_id == patient.id).all()
    assert len(observations) == 2
    values = {o.value for o in observations}
    assert "chest pain (severe)" in values
    assert "fever (severe)" in values

    audit = (
        db_session.query(EHRAuditTrail)
        .filter(EHRAuditTrail.action == "document_call")
        .one_or_none()
    )
    assert audit is not None
    assert audit.status == "success"
    assert audit.caller_agent_id == "queue_state_machine"


# ---------------------------------------------------------------------------
# 8) Voice Intake Agent guardrails (REQ-8)
# ---------------------------------------------------------------------------
def test_voice_intake_transcript_enforces_guardrails(db_session, make_hospital):
    from app.ai.voice_intake import QUESTIONS, VOICE_INTAKE_SYSTEM_PROMPT, synthesize_transcript

    for rule in (
        "INTRODUCTION & CALL PURPOSE",
        "PATIENT IDENTITY VERIFICATION (MANDATORY)",
        "PROTOCOL-DEFINED SYMPTOM QUESTIONS",
        "UNCERTAINTY DETECTION",
        "BOUNDARIES",
    ):
        assert rule in VOICE_INTAKE_SYSTEM_PROMPT

    hospital = make_hospital()
    patient = _patient(db_session, hospital.id, mrn="M-GUARD")
    encounter = _encounter(db_session, hospital.id, patient.id)

    _, transcript = synthesize_transcript(patient, encounter, patient_seed=7)

    assert transcript.startswith("Agent: Hello")
    assert "following up on your recent discharge" in transcript
    assert f"May I verify I am speaking with {patient.first_name} {patient.last_name}?" in transcript
    assert "Yes, this is" in transcript
    first_question_index = transcript.find(QUESTIONS[0])
    assert first_question_index != -1
    assert transcript.find(QUESTIONS[1]) > first_question_index
    assert "Take care. Goodbye." in transcript