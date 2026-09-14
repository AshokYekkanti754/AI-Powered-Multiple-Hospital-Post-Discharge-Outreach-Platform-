"""
Pydantic-wrapped EHR tool interface (PRD §47-48, §89).

This is the ONLY surface an AI agent framework should ever call. Each tool:
  - has a strict Pydantic input schema (agents cannot pass arbitrary kwargs
    or SQL — malformed input is rejected before it reaches mock_ehr.py),
  - is bound to a hospital_id supplied by the *caller's authenticated
    context*, never by the agent's own free-text output,
  - writes exactly one ehr_audit_trail row per invocation, success or failure,
  - never executes raw SQL — it only calls functions in app.services.mock_ehr.

Agents must never be given direct DB session access or a raw-SQL tool.
"""
import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.db.models.ehr_audit import EHRAuditTrail
from app.services import mock_ehr
from app.services.mock_ehr import EHRAuthorizationError


class ToolResult(BaseModel):
    ok: bool
    data: dict | list | None = None
    error: str | None = None


def _audit(db: Session, *, hospital_id, patient_id, tool_name: str, caller_agent_id: str, input_params: dict, status: str):
    db.add(EHRAuditTrail(
        hospital_id=hospital_id,
        patient_id=patient_id,
        tool_name=tool_name,
        caller_agent_id=caller_agent_id,
        action=tool_name,
        input_params=input_params,
        status=status,
    ))
    db.commit()


class GetPatientMedicalHistoryInput(BaseModel):
    patient_id: uuid.UUID


def get_patient_medical_history(
    db: Session, *, hospital_id: uuid.UUID, caller_agent_id: str, patient_id: str
) -> ToolResult:
    try:
        args = GetPatientMedicalHistoryInput(patient_id=patient_id)
    except ValidationError as exc:
        return ToolResult(ok=False, error=f"invalid_input: {exc}")

    try:
        history = mock_ehr.get_medical_history(db, patient_id=args.patient_id, hospital_id=hospital_id)
        _audit(db, hospital_id=hospital_id, patient_id=args.patient_id, tool_name="get_patient_medical_history",
               caller_agent_id=caller_agent_id, input_params=args.model_dump(mode="json"), status="success")
        return ToolResult(ok=True, data=history)
    except EHRAuthorizationError as exc:
        _audit(db, hospital_id=hospital_id, patient_id=args.patient_id, tool_name="get_patient_medical_history",
               caller_agent_id=caller_agent_id, input_params=args.model_dump(mode="json"), status=f"rejected:{exc}")
        return ToolResult(ok=False, error=str(exc))


class RecordPostCallObservationInput(BaseModel):
    patient_id: uuid.UUID
    encounter_id: uuid.UUID
    symptom: str = Field(min_length=1, max_length=256)
    severity: Literal["mild", "moderate", "severe"]


def record_post_call_observation(
    db: Session, *, hospital_id: uuid.UUID, caller_agent_id: str,
    patient_id: str, encounter_id: str, symptom: str, severity: str,
) -> ToolResult:
    try:
        args = RecordPostCallObservationInput(
            patient_id=patient_id, encounter_id=encounter_id, symptom=symptom, severity=severity
        )
    except ValidationError as exc:
        return ToolResult(ok=False, error=f"invalid_input: {exc}")

    try:
        result = mock_ehr.record_observation(
            db, patient_id=args.patient_id, encounter_id=args.encounter_id, hospital_id=hospital_id,
            observation_type="post_call_symptom", value=f"{args.symptom} ({args.severity})",
        )
        _audit(db, hospital_id=hospital_id, patient_id=args.patient_id, tool_name="record_post_call_observation",
               caller_agent_id=caller_agent_id, input_params=args.model_dump(mode="json"), status="success")
        return ToolResult(ok=True, data=result)
    except EHRAuthorizationError as exc:
        _audit(db, hospital_id=hospital_id, patient_id=args.patient_id, tool_name="record_post_call_observation",
               caller_agent_id=caller_agent_id, input_params=args.model_dump(mode="json"), status=f"rejected:{exc}")
        return ToolResult(ok=False, error=str(exc))


class CreateClinicalFollowupTaskInput(BaseModel):
    patient_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=1000)


def create_clinical_followup_task(
    db: Session, *, hospital_id: uuid.UUID, caller_agent_id: str, patient_id: str, reason: str
) -> ToolResult:
    try:
        args = CreateClinicalFollowupTaskInput(patient_id=patient_id, reason=reason)
    except ValidationError as exc:
        return ToolResult(ok=False, error=f"invalid_input: {exc}")

    try:
        result = mock_ehr.create_followup_task(db, patient_id=args.patient_id, hospital_id=hospital_id, reason=args.reason)
        _audit(db, hospital_id=hospital_id, patient_id=args.patient_id, tool_name="create_clinical_followup_task",
               caller_agent_id=caller_agent_id, input_params=args.model_dump(mode="json"), status="success")
        return ToolResult(ok=True, data=result)
    except EHRAuthorizationError as exc:
        _audit(db, hospital_id=hospital_id, patient_id=args.patient_id, tool_name="create_clinical_followup_task",
               caller_agent_id=caller_agent_id, input_params=args.model_dump(mode="json"), status=f"rejected:{exc}")
        return ToolResult(ok=False, error=str(exc))
