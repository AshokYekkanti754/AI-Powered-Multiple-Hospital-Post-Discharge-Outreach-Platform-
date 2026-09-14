from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, get_current_context
from app.db.models.encounter import Encounter
from app.db.models.patient import Patient
from app.middleware.tenant import TenantContext
from app.services.patient_ingestion import ingest_discharge_batch
from app.services.eligibility_engine import evaluate_eligibility

router = APIRouter()


class IngestPayload(BaseModel):
    hospital_id: str | None = None
    records: list[dict]


class EligibilityQuery(BaseModel):
    patient_id: str | None = None


@router.post("/ingest", status_code=201)
def ingest(payload: IngestPayload, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz
    hospital_id = payload.hospital_id
    if context.role != "PLATFORM_ADMIN":
        if hospital_id is not None and str(hospital_id) != str(context.hospital_id):
            raise HTTPException(status_code=403, detail="Cross-tenant access is forbidden")
        hospital_id = _uuid.UUID(str(context.hospital_id))
    else:
        hospital_id = _uuid.UUID(str(hospital_id)) if hospital_id else None
    if hospital_id is None:
        raise HTTPException(status_code=422, detail="hospital_id is required for platform admins")
    report = ingest_discharge_batch(db, hospital_id=hospital_id, records=payload.records)
    return {"hospital_id": report.hospital_id, "total_submitted": report.total_submitted, "ingested": report.ingested, "failed": report.failed, "errors": [error.__dict__ for error in report.errors], "patient_ids": report.patient_ids}


@router.get("")
def list_patients(search: str | None = None, risk_tier: str | None = None, limit: int = 100, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    if context.hospital_id is None:
        # platform admin without tenant: return empty list w/ hint instead of 500
        return []
    query = db.query(Patient).filter(Patient.hospital_id == context.hospital_id)
    if search:
        query = query.filter((Patient.mrn.contains(search)) | (Patient.first_name.contains(search)) | (Patient.last_name.contains(search)))
    rows = query.order_by(Patient.created_at.desc()).limit(limit).all()
    if risk_tier:
        allowed = {enc.patient_id for enc in db.query(Encounter).filter(Encounter.hospital_id == context.hospital_id, Encounter.risk_tier == risk_tier).all()}
        rows = [patient for patient in rows if patient.id in allowed]
    return [{"id": str(p.id), "mrn": p.mrn, "first_name": p.first_name, "last_name": p.last_name, "phone_number": p.phone_number, "preferred_language": p.preferred_language, "consent_status": p.consent_status} for p in rows]


@router.get("/{patient_id}/timeline")
def timeline(patient_id: str, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if str(patient.hospital_id) != str(context.hospital_id):
        raise HTTPException(status_code=403, detail="Cross-tenant access is forbidden")
    encounters = db.query(Encounter).filter(Encounter.patient_id == patient_id, Encounter.hospital_id == context.hospital_id).order_by(Encounter.discharge_timestamp.asc()).all()
    return [{"type": "discharge", "timestamp": encounter.discharge_timestamp.isoformat(), "detail": {"encounter_id": str(encounter.id), "risk_tier": encounter.risk_tier.value, "discharge_instructions": encounter.discharge_instructions}} for encounter in encounters]


@router.post("/eligibility-check")
def eligibility_check(patient_id: str | None = None, payload: EligibilityQuery | None = None, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    import uuid as _uuid2
    from datetime import datetime as _dt2, timezone as _tz2
    pid = patient_id or (payload.patient_id if payload else None)
    if not pid:
        raise HTTPException(status_code=422, detail="patient_id is required (query ?patient_id= or body {patient_id})")
    try:
        _uuid2.UUID(str(pid))
    except ValueError:
        raise HTTPException(status_code=422, detail="patient_id must be a valid UUID")
    patient = db.query(Patient).filter(Patient.id == pid, Patient.hospital_id == context.hospital_id).first()
    encounter = db.query(Encounter).filter(Encounter.patient_id == pid, Encounter.hospital_id == context.hospital_id).order_by(Encounter.discharge_timestamp.desc()).first()
    if patient is None or encounter is None:
        raise HTTPException(status_code=404, detail="Patient or encounter not found")
    result = evaluate_eligibility(encounter_id=str(encounter.id), patient_id=str(patient.id), discharge_timestamp=encounter.discharge_timestamp, follow_up_window_hours=encounter.follow_up_window_hours, risk_score=encounter.risk_score, consent_status=patient.consent_status, now=_dt2.now(_tz2.utc))
    return {**result.__dict__, "risk_tier": result.risk_tier.value}
