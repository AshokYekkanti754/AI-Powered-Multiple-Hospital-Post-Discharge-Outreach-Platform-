from datetime import datetime, timedelta, timezone
from app.db.models.campaign import Campaign, CampaignStatus
from app.db.models.escalation import EscalationSeverity, EscalationStatus
from app.db.models.patient import Patient
from app.db.models.user import UserRole
from app.db.models.notification import Notification
from app.services.escalation_service import acknowledge_escalation, create_escalation, trigger_timeout_backup


def test_urgent_escalation_notifies_staff_and_timeout_sends_backup(db_session, make_hospital, make_user):
    hospital = make_hospital()
    reviewer = make_user("reviewer@test.local", role=UserRole.CLINICAL_REVIEWER, hospital_id=hospital.id)
    admin = make_user("admin@test.local", role=UserRole.HOSPITAL_ADMIN, hospital_id=hospital.id)
    patient = Patient(hospital_id=hospital.id, mrn="P-1", first_name="Pat", last_name="Ient", phone_number="1", date_of_birth=datetime(1980, 1, 1).date())
    campaign = Campaign(hospital_id=hospital.id, name="C", status=CampaignStatus.RUNNING)
    db_session.add_all([patient, campaign]); db_session.commit()
    escalation = create_escalation(db_session, hospital_id=hospital.id, patient_id=patient.id, campaign_id=campaign.id, severity=EscalationSeverity.URGENT, trigger_reason="severe symptom")
    assert db_session.query(Notification).count() == 2
    escalation.created_at = datetime.now(timezone.utc) - timedelta(minutes=16)
    db_session.commit()
    assert trigger_timeout_backup(db_session, escalation_id=escalation.id) is True
    assert db_session.query(Notification).count() == 4


def test_acknowledgement_prevents_timeout_backup(db_session, make_hospital, make_user):
    hospital = make_hospital()
    reviewer = make_user("reviewer2@test.local", role=UserRole.CLINICAL_REVIEWER, hospital_id=hospital.id)
    patient = Patient(hospital_id=hospital.id, mrn="P-2", first_name="Pat", last_name="Ient", phone_number="1", date_of_birth=datetime(1980, 1, 1).date())
    campaign = Campaign(hospital_id=hospital.id, name="C2", status=CampaignStatus.RUNNING)
    db_session.add_all([patient, campaign]); db_session.commit()
    escalation = create_escalation(db_session, hospital_id=hospital.id, patient_id=patient.id, campaign_id=campaign.id, severity=EscalationSeverity.HIGH, trigger_reason="symptom")
    acknowledge_escalation(db_session, escalation=escalation, user_id=reviewer.id)
    escalation.created_at = datetime.now(timezone.utc) - timedelta(minutes=16)
    db_session.commit()
    assert trigger_timeout_backup(db_session, escalation_id=escalation.id) is False
