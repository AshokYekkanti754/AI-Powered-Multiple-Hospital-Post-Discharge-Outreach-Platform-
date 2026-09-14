"""
Mock EHR service (PRD §11-12).

This is the ONLY place that touches Patient/Encounter/Observation/
CommunicationLog/FollowUpTask rows on behalf of an AI agent or the EHR API
layer. Every function here:
  - takes an explicit hospital_id and enforces it against the resource's
    actual owner before reading or writing anything,
  - never accepts or builds raw SQL from caller input,
  - is the single choke point audited by ehr_audit_trail.
"""
import uuid

from sqlalchemy.orm import Session

from app.db.models.communication import CommunicationLog
from app.db.models.condition import Condition
from app.db.models.encounter import Encounter
from app.db.models.followup_task import FollowUpTask
from app.db.models.observation import Observation
from app.db.models.patient import Patient


class EHRAuthorizationError(Exception):
    """Raised when a resource does not belong to the caller's hospital_id."""


def _get_patient_or_raise(db: Session, patient_id: uuid.UUID, hospital_id: uuid.UUID) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise EHRAuthorizationError("patient_not_found")
    if str(patient.hospital_id) != str(hospital_id):
        raise EHRAuthorizationError("patient_belongs_to_a_different_hospital")
    return patient


def get_patient_profile(db: Session, *, patient_id: uuid.UUID, hospital_id: uuid.UUID) -> dict:
    patient = _get_patient_or_raise(db, patient_id, hospital_id)
    return {
        "id": str(patient.id),
        "mrn": patient.mrn,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "phone_number": patient.phone_number,
        "preferred_language": patient.preferred_language,
        "consent_status": patient.consent_status,
    }


def get_encounter_detail(db: Session, *, encounter_id: uuid.UUID, hospital_id: uuid.UUID) -> dict:
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if encounter is None:
        raise EHRAuthorizationError("encounter_not_found")
    if str(encounter.hospital_id) != str(hospital_id):
        raise EHRAuthorizationError("encounter_belongs_to_a_different_hospital")
    return {
        "id": str(encounter.id),
        "patient_id": str(encounter.patient_id),
        "discharge_timestamp": encounter.discharge_timestamp.isoformat(),
        "care_setting": encounter.care_setting,
        "risk_tier": encounter.risk_tier.value,
        "discharge_instructions": encounter.discharge_instructions,
    }


def get_observations(db: Session, *, patient_id: uuid.UUID, hospital_id: uuid.UUID) -> list[dict]:
    _get_patient_or_raise(db, patient_id, hospital_id)  # enforces tenant ownership before querying children
    rows = db.query(Observation).filter(Observation.patient_id == patient_id).all()
    return [
        {
            "id": str(o.id),
            "encounter_id": str(o.encounter_id),
            "observation_type": o.observation_type,
            "value": o.value,
            "recorded_at": o.recorded_at.isoformat(),
        }
        for o in rows
    ]


def get_medical_history(db: Session, *, patient_id: uuid.UUID, hospital_id: uuid.UUID) -> dict:
    patient = _get_patient_or_raise(db, patient_id, hospital_id)
    conditions = db.query(Condition).filter(Condition.patient_id == patient_id).all()
    encounters = db.query(Encounter).filter(Encounter.patient_id == patient_id).all()
    return {
        "patient": get_patient_profile(db, patient_id=patient_id, hospital_id=hospital_id),
        "conditions": [{"code": c.code, "description": c.description} for c in conditions],
        "encounters": [get_encounter_detail(db, encounter_id=e.id, hospital_id=hospital_id) for e in encounters],
    }


def record_communication(
    db: Session, *, patient_id: uuid.UUID, hospital_id: uuid.UUID, channel: str, outcome: str, notes: str = ""
) -> dict:
    _get_patient_or_raise(db, patient_id, hospital_id)
    log = CommunicationLog(hospital_id=hospital_id, patient_id=patient_id, channel=channel, outcome=outcome, notes=notes)
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"id": str(log.id), "patient_id": str(log.patient_id), "channel": log.channel, "outcome": log.outcome}


def record_observation(
    db: Session, *, patient_id: uuid.UUID, encounter_id: uuid.UUID, hospital_id: uuid.UUID,
    observation_type: str, value: str,
) -> dict:
    from datetime import datetime, timezone

    _get_patient_or_raise(db, patient_id, hospital_id)
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if encounter is None or str(encounter.hospital_id) != str(hospital_id) or str(encounter.patient_id) != str(patient_id):
        raise EHRAuthorizationError("encounter_not_found_or_mismatched")

    obs = Observation(
        patient_id=patient_id, encounter_id=encounter_id,
        observation_type=observation_type, value=value,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return {"id": str(obs.id), "observation_type": obs.observation_type, "value": obs.value}


def create_followup_task(db: Session, *, patient_id: uuid.UUID, hospital_id: uuid.UUID, reason: str) -> dict:
    _get_patient_or_raise(db, patient_id, hospital_id)
    task = FollowUpTask(hospital_id=hospital_id, patient_id=patient_id, reason=reason)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": str(task.id), "patient_id": str(task.patient_id), "reason": task.reason, "status": task.status.value}
