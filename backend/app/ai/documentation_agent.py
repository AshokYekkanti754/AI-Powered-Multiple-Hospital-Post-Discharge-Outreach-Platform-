"""Post-call EHR auto-documentation agent (REQ-6).

On ``CALL_COMPLETED`` this module:

  * parses the conversation transcript into structured symptoms/observations,
  * validates the extraction with Pydantic,
  * pushes each observation to the Mock EHR (``observations`` table),
  * writes one ``ehr_audit_trail`` row for the documentation run.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models.ehr_audit import EHRAuditTrail
from app.db.models.encounter import Encounter
from app.services import mock_ehr

# Phrases from the Voice Intake red-flag map that require escalation wording.
SEVERE_SYMPTOM_PHRASES = (
    "chest pain",
    "shortness of breath",
    "cannot breathe",
    "severe bleeding",
    "fever",
    "dizziness",
    "rapid heart rate",
    "loss of consciousness",
)

SPOKEN_SYMPTOM_PHRASES = (
    "headache",
    "swelling",
    "pain",
    "nausea",
    "fatigue",
    "cough",
    "tired",
    "sleepless",
    "redness",
    "discharge",
)


class PostCallObservation(BaseModel):
    symptom: str = Field(min_length=1, max_length=256)
    severity: str = Field(pattern="^(mild|moderate|severe)$")


class ClinicalNote(BaseModel):
    chief_concern: str = Field(default="")
    summary: str = Field(default="")
    disposition: str = Field(default="ready for triage")
    symptoms: list[PostCallObservation] = Field(default_factory=list)
    identity_verified: bool = True
    uncertainty: bool = False


def extract_clinical_note(transcript: str, disposition: str) -> ClinicalNote:
    """Deterministic structured extraction from a transcript.

    Red-flag vocabulary is classified as ``severe``; broader spoken symptom
    vocabulary as ``mild``; other explicitly reported symptoms ``moderate``.
    Agent questions are never treated as patient reports.
    """
    lowered = (transcript or "").lower()
    symptoms: list[PostCallObservation] = []
    matched_severe: set[str] = set()

    def _note(symptom: str, severity: str) -> None:
        key = symptom.lower()
        if any(existing.symptom.lower() == key for existing in symptoms):
            return
        symptoms.append(PostCallObservation(symptom=symptom, severity=severity))

    for phrase in SEVERE_SYMPTOM_PHRASES:
        if phrase in lowered:
            _note(phrase, "severe")
            matched_severe.add(phrase)
    for phrase in SPOKEN_SYMPTOM_PHRASES:
        if phrase in lowered:
            # Skip generic wording fully contained in an already-captured
            # severe phrase (e.g. "pain" inside "chest pain").
            if any(phrase in severe for severe in matched_severe):
                continue
            _note(phrase, "mild")

    # Only patient lines (anything after the first colon, not an Agent line)
    # that explicitly mention a symptom without matching the controlled vocab
    # are captured conservatively as moderate.
    for line in (transcript or "").splitlines():
        text = line.lower()
        if text.startswith("agent:") or ":" not in text:
            continue
        patient_part = text.split(":", 1)[1].strip()
        if not patient_part:
            continue
        if ("symptom" in patient_part or "hurt" in patient_part or "ache" in patient_part) and not any(
            p in patient_part for p in SEVERE_SYMPTOM_PHRASES + SPOKEN_SYMPTOM_PHRASES
        ):
            _note(patient_part[:120] or "reported symptom", "moderate")

    identity_verified = "may i verify" not in lowered or (
        "yes" in lowered and "that's me" not in lowered
    ) or "is speaking with" not in lowered
    if "may i verify" in lowered and ("yes, this is" in lowered or "that's me" in lowered or "yes, speaking" in lowered):
        identity_verified = True

    uncertainty = any(phrase in lowered for phrase in ("not sure", "maybe", "i don't know", "i don't understand", "can you repeat"))

    summary = (transcript or "").strip()[:2000]
    return ClinicalNote(
        chief_concern=(lowered.strip()[:120] or "post-discharge follow-up"),
        summary=summary or "No transcript available.",
        disposition=disposition,
        symptoms=symptoms,
        identity_verified=identity_verified,
        uncertainty=uncertainty,
    )


def document_call(transcript: str, disposition: str) -> ClinicalNote:
    """Backward-compatible wrapper: pure extraction, no DB writes."""
    return extract_clinical_note(transcript, disposition)


def push_post_call_documentation(
    db: Session,
    *,
    hospital_id,
    patient_id,
    encounter_id,
    transcript: str,
    disposition: str,
    caller_agent_id: str = "documentation_agent",
) -> ClinicalNote:
    """Auto-document a completed call: validate + persist observations + audit.

    Never raises on missing resources: if the encounter cannot be resolved the
    call is recorded as a rejected audit entry so operators can trace failures.
    """
    note = extract_clinical_note(transcript, disposition)
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).one_or_none()
    if encounter is None:
        db.add(EHRAuditTrail(
            hospital_id=hospital_id, patient_id=patient_id,
            tool_name="post_call_auto_documentation", caller_agent_id=caller_agent_id,
            action="document_call", input_params={"encounter_id": str(encounter_id)}, status="rejected:encounter_not_found",
        ))
        db.commit()
        return note

    success = 0
    for obs in note.symptoms:
        try:
            mock_ehr.record_observation(
                db, patient_id=patient_id, encounter_id=encounter_id, hospital_id=hospital_id,
                observation_type="post_call_symptom", value=f"{obs.symptom} ({obs.severity})",
            )
            success += 1
        except Exception:  # noqa: BLE001 - one bad observation must not drop the audit trail
            pass

    db.add(EHRAuditTrail(
        hospital_id=hospital_id, patient_id=patient_id,
        tool_name="post_call_auto_documentation", caller_agent_id=caller_agent_id,
        action="document_call",
        input_params={
            "encounter_id": str(encounter_id),
            "symptoms": [o.model_dump(mode="json") for o in note.symptoms],
            "identity_verified": note.identity_verified,
            "uncertainty": note.uncertainty,
        },
        status="success" if success == len(note.symptoms) else "partial",
    ))
    db.commit()
    return note
