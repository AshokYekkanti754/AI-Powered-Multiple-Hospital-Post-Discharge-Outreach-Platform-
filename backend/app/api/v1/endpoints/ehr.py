import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.v1.deps import db_session, get_current_context
from app.db.models.ehr_audit import EHRAuditTrail
from app.middleware.tenant import TenantContext
from app.services import mock_ehr
from app.services.mock_ehr import EHRAuthorizationError

router = APIRouter()


def _run(action, db, context, patient_id, payload):
    try:
        result = action()
        db.add(EHRAuditTrail(hospital_id=context.hospital_id, patient_id=patient_id, tool_name=payload.get("tool_name", "ehr_api"), caller_agent_id=str(context.user_id), action=payload.get("action", "ehr_api"), input_params=payload, status="success"))
        db.commit()
        return result
    except EHRAuthorizationError as exc:
        db.add(EHRAuditTrail(hospital_id=context.hospital_id, patient_id=patient_id, tool_name="ehr_api", caller_agent_id=str(context.user_id), action="rejected", input_params=payload, status=f"rejected:{exc}"))
        db.commit()
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/patients/{patient_id}")
def get_patient(patient_id: uuid.UUID, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    return _run(lambda: mock_ehr.get_patient_profile(db, patient_id=patient_id, hospital_id=uuid.UUID(context.hospital_id)), db, context, patient_id, {"action": "get_patient"})


@router.get("/encounters/{encounter_id}")
def get_encounter(encounter_id: uuid.UUID, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    try: return mock_ehr.get_encounter_detail(db, encounter_id=encounter_id, hospital_id=uuid.UUID(context.hospital_id))
    except EHRAuthorizationError as exc: raise HTTPException(status_code=403, detail=str(exc))


@router.get("/observations")
def get_observations(patient_id: uuid.UUID, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    try: return mock_ehr.get_observations(db, patient_id=patient_id, hospital_id=uuid.UUID(context.hospital_id))
    except EHRAuthorizationError as exc: raise HTTPException(status_code=403, detail=str(exc))


class CommunicationPayload(BaseModel):
    patient_id: uuid.UUID
    outcome: str
    channel: str = "phone_call"
    notes: str = ""


@router.post("/communications", status_code=201)
def communication(payload: CommunicationPayload, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    result = _run(lambda: mock_ehr.record_communication(db, patient_id=payload.patient_id, hospital_id=uuid.UUID(context.hospital_id), channel=payload.channel, outcome=payload.outcome, notes=payload.notes), db, context, payload.patient_id, {"action": "record_communication", **payload.model_dump(mode="json")})
    return result


@router.get("/audit-trail")
def audit_trail(db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    return [{"action": row.action, "status": row.status, "tool_name": row.tool_name} for row in db.query(EHRAuditTrail).filter(EHRAuditTrail.hospital_id == context.hospital_id).all()]
