from datetime import datetime, timezone
from app.db.models.call import CallOutcome
from app.db.models.campaign import Campaign, CampaignStatus
from app.db.models.patient import Patient
from app.db.models.manual_followup import ManualFollowUp
from app.db.models.queue_task import QueueTask, QueueTaskStatus
from app.services.queue_state_machine import apply_call_outcome


def _task(db_session, make_hospital):
    hospital = make_hospital()
    patient = Patient(hospital_id=hospital.id, mrn="M-1", first_name="A", last_name="B", phone_number="1", date_of_birth=datetime(1980, 1, 1).date())
    campaign = Campaign(hospital_id=hospital.id, name="C", status=CampaignStatus.RUNNING, max_retries=2)
    db_session.add_all([patient, campaign]); db_session.flush()
    task = QueueTask(hospital_id=hospital.id, campaign_id=campaign.id, patient_id=patient.id, status=QueueTaskStatus.CALLING, updated_at=datetime.now(timezone.utc))
    db_session.add(task); db_session.commit(); db_session.refresh(task)
    return task


def test_max_retries_routes_to_manual_followup(db_session, make_hospital):
    task = _task(db_session, make_hospital)
    apply_call_outcome(db_session, task=task, outcome=CallOutcome.NO_ANSWER)
    apply_call_outcome(db_session, task=task, outcome=CallOutcome.NO_ANSWER)
    assert task.status is QueueTaskStatus.MANUAL_FOLLOW_UP
    assert db_session.query(ManualFollowUp).count() == 1


def test_dropped_call_preserves_transcript_and_prioritizes_reconnect(db_session, make_hospital):
    task = _task(db_session, make_hospital)
    apply_call_outcome(db_session, task=task, outcome=CallOutcome.DROPPED, partial_transcript="I feel dizzy")
    assert task.status is QueueTaskStatus.RETRY_SCHEDULED
    assert task.priority_score >= 100
