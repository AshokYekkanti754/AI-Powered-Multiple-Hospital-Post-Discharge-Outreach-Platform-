"""End-to-end call orchestration part 1: helpers + pipeline head."""
from __future__ import annotations
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.ai.clinical_triage import triage_with_protocols
from app.ai.consensus_council import TriageDecision, TriageStatus, run_consensus
from app.ai.documentation_agent import document_call
from app.ai.llm_provider import assess as llm_assess
from app.ai.voice_intake import run_voice_intake
from app.db.models.ai_log import AILog
from app.db.models.call import Call, CallOutcome
from app.db.models.campaign import Campaign
from app.db.models.encounter import Encounter
from app.db.models.hospital import Hospital
from app.db.models.patient import Patient
from app.db.models.queue_task import QueueTask, QueueTaskStatus
from app.services.voice_provider import place_call


def _assessor(name: str):
    def _fn(transcript: str) -> TriageDecision:
        out = llm_assess(transcript, agent_name=name)
        return TriageDecision(status=TriageStatus(out["status"]), rationale=out["rationale"])
    _fn.__name__ = name
    return _fn


def _outcome_for_status(status: TriageStatus, intake) -> CallOutcome:
    if status in (TriageStatus.URGENT, TriageStatus.ESCALATED, TriageStatus.UNCERTAIN, TriageStatus.CONCERNING):
        return CallOutcome.FAILED
    if intake.callback_requested:
        return CallOutcome.PATIENT_REQUESTED_CALLBACK
    return CallOutcome.COMPLETED


def process_queue_task(db: Session, *, task_id: uuid.UUID, worker_id: str = "orchestrator",
                       patient_seed: int | None = None, transcript_override: str | None = None,
                       simulated_outcome=None, now=None) -> dict:
    """Run one queue task end-to-end. Idempotent per task (replays return existing Call)."""
    from app.db.models.escalation import EscalationSeverity
    from app.events.bus import DomainEvent, bus
    from app.services import mock_ehr
    from app.services.escalation_service import create_escalation
    from app.services.queue_state_machine import RETRYABLE_OUTCOMES, apply_call_outcome
    now = now or datetime.now(timezone.utc)
    task = db.query(QueueTask).filter(QueueTask.id == task_id).one_or_none()
    if task is None:
        raise ValueError("queue task not found")
    existing = db.query(Call).filter(Call.queue_task_id == task.id).order_by(Call.created_at.desc()).first()
    if existing is not None:
        return {"task_id": str(task.id), "status": task.status.value, "call_id": str(existing.id),
                "outcome": existing.outcome.value, "idempotent_replay": True}
    hospital = db.query(Hospital).filter(Hospital.id == task.hospital_id).one()
    patient = db.query(Patient).filter(Patient.id == task.patient_id).one()
    encounter = (db.query(Encounter).filter(Encounter.patient_id == patient.id,
                 Encounter.hospital_id == hospital.id).order_by(Encounter.discharge_timestamp.desc()).first())
    campaign = db.query(Campaign).filter(Campaign.id == task.campaign_id).one()
    task.status = QueueTaskStatus.CALLING
    task.call_started_at = now
    task.locked_by_worker = worker_id
    db.commit()
    started = time.monotonic()
    place_call(to_phone=patient.phone_number, script=f"Follow-up for {patient.first_name} {patient.last_name}")
    intake = run_voice_intake(patient, encounter, patient_seed=patient_seed, override=transcript_override)
    latency_ms = int((time.monotonic() - started) * 1000)
    base = triage_with_protocols(db, hospital_id=hospital.id, transcript=intake.transcript)
    consensus = run_consensus(intake.transcript, [_assessor("assessor_a"), _assessor("assessor_b"), lambda _: base])
    final_status = consensus.final_status
    note = document_call(intake.transcript, final_status.value)
    outcome = simulated_outcome or _outcome_for_status(final_status, intake)
    db.add(AILog(hospital_id=hospital.id, agent_name="voice_intake", model_used="simulated",
                 prompt_tokens=len(intake.transcript.split()), completion_tokens=len(intake.symptoms),
                 latency_ms=latency_ms, estimated_cost=0.0,
                 structured_output=intake.model_dump(mode="json"), consensus_disagreement=False))
    db.add(AILog(hospital_id=hospital.id, agent_name="consensus_council", model_used="deterministic",
                 prompt_tokens=len(intake.transcript.split()), completion_tokens=1, latency_ms=0,
                 structured_output=consensus.model_dump(mode="json"), consensus_disagreement=consensus.disagreement))
    db.flush()
    callback_at = None
    if outcome is CallOutcome.PATIENT_REQUESTED_CALLBACK:
        from datetime import timedelta
        callback_at = now + timedelta(hours=24)
    task = apply_call_outcome(db, task=task, outcome=outcome, partial_transcript=intake.transcript,
                              callback_at=callback_at, duration_seconds=180, now=now)
    call = db.query(Call).filter(Call.queue_task_id == task.id).order_by(Call.created_at.desc()).first()
    for log in db.query(AILog).filter(AILog.hospital_id == hospital.id, AILog.call_id.is_(None)).all():
        if log.agent_name in ("voice_intake", "consensus_council") and call is not None:
            log.call_id = call.id
    try:
        mock_ehr.record_communication(db, patient_id=patient.id, hospital_id=hospital.id,
            channel="phone_call", outcome=outcome.value,
            notes=f"{note.summary[:500]} | disposition={final_status.value}")
    except Exception:
        db.rollback()
    escalation_id = None
    if final_status in (TriageStatus.URGENT, TriageStatus.ESCALATED, TriageStatus.UNCERTAIN, TriageStatus.CONCERNING):
        sev = EscalationSeverity.URGENT if final_status in (TriageStatus.URGENT, TriageStatus.ESCALATED) else EscalationSeverity.HIGH
        esc = create_escalation(db, hospital_id=hospital.id, patient_id=patient.id, campaign_id=campaign.id,
            call_id=call.id if call else None, severity=sev,
            trigger_reason=f"consensus={final_status.value}; red_flags={intake.red_flags}")
        escalation_id = str(esc.id)
        bus.publish(DomainEvent(event_type="ESCALATION_CREATED", hospital_id=str(hospital.id),
                                payload={"escalation_id": escalation_id}))
        task.status = QueueTaskStatus.ESCALATED
        db.commit()
        db.refresh(task)
    bus.publish(DomainEvent(event_type="CALL_NO_ANSWER" if outcome in RETRYABLE_OUTCOMES else "CALL_COMPLETED",
                            hospital_id=str(hospital.id), payload={"task_id": str(task.id)}))
    return {"task_id": str(task.id), "status": task.status.value, "call_id": str(call.id) if call else None,
            "outcome": outcome.value, "triage": final_status.value, "disagreement": consensus.disagreement,
            "escalation_id": escalation_id, "red_flags": intake.red_flags, "idempotent_replay": False}

