"""
Voice Intake Agent (PRD §34-35).

This is the conversational component of the outreach call. In the prototype
telephony is simulated, so this module owns:

  * the *conversation script* — the questions the agent asks, derived from the
    hospital protocol / campaign configuration,
  * simulated patient responses (deterministic per seed so evaluations and the
    safety benchmark are repeatable),
  * *structured extraction* of the information the rest of the pipeline needs:
    verified identity, reported symptoms, red flags, uncertainty, callback
    requests and the full transcript.

The output (`IntakeSummary`) is the single source of truth that the Clinical
Triage Agent and the Consensus Council consume. A real voice provider would be
swapped in behind the same interface (STT -> transcript -> IntakeSummary).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.db.models.encounter import Encounter, RiskTier
from app.db.models.patient import Patient

# Protocol-derived questions the agent asks in order.
QUESTIONS = [
    "Since you left the hospital, have you experienced any new or worsening symptoms?",
    "Are you taking your medications as prescribed?",
    "Have you been able to eat, drink and move around as usual?",
    "Do you have any pain, swelling, redness or discharge at your surgical site?",
    "Is there anything else you would like your care team to know about?",
]

# REQ-8: Strict Voice Intake Agent guardrails. This exact system prompt is
# provided to any real LLM-backed implementation so the behaviour is
# reproducible and auditable. The deterministic simulation below already
# mirrors every rule (intro -> identity verfication -> protocol questions ->
# uncertainty handling -> boundary-respecting capture).
VOICE_INTAKE_SYSTEM_PROMPT = """\
You are the Voice Intake Agent for a hospital post-discharge outreach team.

STRICT OPERATING RULES — follow every one, in order:

1. INTRODUCTION & CALL PURPOSE
   Introduce yourself as part of the hospital outreach team and explain that you
   are calling to check on the patient after their recent discharge. Never begin
   asking clinical questions before completing the introduction.

2. PATIENT IDENTITY VERIFICATION (MANDATORY)
   Before collecting any health information, verify you are speaking with the
   correct person by asking EXACTLY: "May I verify I am speaking with [Patient
   Full Name]?" Do NOT proceed if the patient cannot confirm their identity; ask
   for clarification and route to a human operator if identity cannot be
   confirmed.

3. PROTOCOL-DEFINED SYMPTOM QUESTIONS
   Ask the approved discharge-recovery questions sequentially, one at a time.
   Do not reorder, skip, or invent questions outside the approved protocol list.

4. UNCERTAINTY DETECTION
   If the patient sounds confused, unsure, or answers ambiguously, ask for
   clarification and record their raw response verbatim for the clinical team.
   Flag the answer as uncertain rather than guessing what the patient meant.

5. BOUNDARIES
   Strictly capture symptoms and observations only. You are NOT a diagnosing
   clinician: never invent a diagnosis, never offer unapproved medical advice,
   never override or reinterpret hospital protocols, and never minimise a
   reported symptom. All red-flag symptoms MUST be preserved for human review.

CLOSING: Always thank the patient and tell them a member of their care team may
follow up. Never leave the impression that the AI provided a clinical opinion.
"""

# Symptom phrases the agent listens for; each maps to a red-flag escalation term.
SYMPTOM_RED_FLAGS = {
    "chest pain": "new or worsening chest pain",
    "shortness of breath": "shortness of breath at rest",
    "cannot breathe": "shortness of breath at rest",
    "severe bleeding": "bleeding from the incision site",
    "fever": "fever above 100.4F",
    "dizziness": "dizziness or fainting",
    "rapid heart rate": "rapid heart rate",
    "loss of consciousness": "loss of consciousness",
}


class IntakeSummary(BaseModel):
    identity_verified: bool = True
    symptoms: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    uncertainty: bool = False
    callback_requested: bool = False
    callback_preference: str | None = None
    transcript: str = ""
    questions_asked: list[str] = Field(default_factory=list)
    disposition: str = "ready for triage"


@dataclass
class SimulatedResponse:
    """Response for a single patient to a single agent question."""

    text: str
    symptoms: list[str] = field(default_factory=list)
    uncertain: bool = False
    callback_requested: bool = False
    callback_preference: str | None = None


# Pool of simulated patient answers per risk tier. REPEATABLE: a random.Random(seed)
# is used so the same patient+seed always produces the same conversation.
RISK_RESPONSES = {
    RiskTier.LOW: [
        ("Everything feels fine, thank you.", []),
        ("I feel much better. No issues to report.", []),
        ("I've been resting and taking my medicine.", []),
        ("A little tired, but otherwise okay.", []),
    ],
    RiskTier.MEDIUM: [
        ("I'm okay but a bit tired and have some mild swelling.", ["swelling"]),
        ("I have a mild headache and trouble sleeping.", ["headache"]),
        ("I've been short of breath when I walk up stairs.", ["shortness of breath"]),
        ("I'm coughing a bit more than usual.", ["cough"]),
    ],
    RiskTier.HIGH: [
        ("I felt some chest pain this morning and I wasn't sure what to do.", ["chest pain"]),
        ("I've been dizzy and had a rapid heart rate.", ["dizziness", "rapid heart rate"]),
        ("I'm having trouble catching my breath at rest.", ["shortness of breath"]),
        ("I ran a fever last night.", ["fever"]),
    ],
    RiskTier.CRITICAL: [
        ("I have chest pain right now and it's hard to breathe.", ["chest pain", "shortness of breath"]),
        ("I think I'm bleeding from the incision site.", ["severe bleeding"]),
        ("I nearly fainted and I can't catch my breath.", ["dizziness", "shortness of breath"]),
        ("I've been dizzy and am having chest pain when I lie down.", ["chest pain", "dizziness"]),
    ],
}

DEFAULT_RESPONSES = [
    ("I'm doing alright, I think.", []),
    ("Not sure, maybe a little off.", []),
]


def _build_response_pool(encounter: Encounter) -> list[SimulatedResponse]:
    tier = encounter.risk_tier if encounter.risk_tier in RISK_RESPONSES else RiskTier.MEDIUM
    pool = [SimulatedResponse(text=text, symptoms=list(symptoms)) for text, symptoms in RISK_RESPONSES[tier]]
    pool.extend(SimulatedResponse(text=text, symptoms=list(symptoms)) for text, symptoms in DEFAULT_RESPONSES)
    return pool


def _seed_for(patient: Patient, encounter: Encounter) -> int:
    value = str(patient.id) + str(encounter.id)
    return abs(hash(value)) % (2**31)
def synthesize_transcript(
    patient: Patient,
    encounter: Encounter,
    patient_seed: int | None = None,
    override: str | None = None,
) -> tuple[list[SimulatedResponse], str]:
    """Produce a deterministic simulated conversation for the given patient.

    The script mirrors ``VOICE_INTAKE_SYSTEM_PROMPT``: it opens with the
    outreach introduction, performs the mandatory identity verification, asks
    the protocol questions sequentially, and closes within agent boundaries.

    Returns (responses, transcript). ``override`` can inject a scripted
    patient utterance (used by the safety evaluation harness).
    """
    rng = random.Random(patient_seed if patient_seed is not None else _seed_for(patient, encounter))
    pool = _build_response_pool(encounter)

    lines = [
        # REQ-8 rule 1: introduction & call purpose.
        f"Agent: Hello, this is the {encounter.care_setting.title()} outreach team from your hospital, "
        "following up on your recent discharge to make sure you are recovering well. "
        "This call may be recorded for quality and care purposes.",
        # REQ-8 rule 2: mandatory identity verification.
        f"Agent: May I verify I am speaking with {patient.first_name} {patient.last_name}?",
        f"{patient.first_name}: Yes, this is {patient.first_name} {patient.last_name}.",
        "Agent: Thank you. Is now a good time to ask you a few quick questions about how you're feeling?",
        f"{patient.first_name}: Yes.",
    ]

    responses: list[SimulatedResponse] = []
    asked = list(QUESTIONS)
    if override:
        responses.append(SimulatedResponse(text=override, symptoms=[], uncertain=True))
        lines.append(f"Agent: {QUESTIONS[0]}")
        lines.append(f"{patient.first_name}: {override}")
        asked = asked[1:]
        pool = []
    for q in asked:
        lines.append(f"Agent: {q}")
        if not pool:
            text, symptoms = rng.choice(DEFAULT_RESPONSES)
            response = SimulatedResponse(text=text, symptoms=list(symptoms))
        else:
            candidate = pool.pop(rng.randrange(len(pool)))
            if rng.random() < 0.25:
                response = SimulatedResponse(
                    text=candidate.text,
                    symptoms=candidate.symptoms,
                    uncertain=rng.random() < 0.35,
                    callback_requested=rng.random() < 0.08,
                    callback_preference="tomorrow after 6 PM" if rng.random() < 0.08 else None,
                )
            else:
                response = candidate
        responses.append(response)
        line = f"{patient.first_name}: {response.text}"
        if response.callback_preference:
            line += f" Could you call me back {response.callback_preference}?"
        lines.append(line)

    lines.append("Agent: Thank you. A member of your care team may follow up with you. Take care. Goodbye.")
    return responses, "\n".join(lines)


def extract_intake(
    transcript: str,
    responses: list[SimulatedResponse] | None = None,
    identity_verified: bool = True,
) -> IntakeSummary:
    """Extract a structured IntakeSummary from the conversation transcript."""
    lowered = (transcript or "").lower()
    symptoms: list[str] = []
    red_flags: list[str] = []
    for phrase, flag in SYMPTOM_RED_FLAGS.items():
        if phrase in lowered:
            symptoms.append(phrase)
            red_flags.append(flag)

    if responses:
        for response in responses:
            for phrase, flag in SYMPTOM_RED_FLAGS.items():
                if phrase in response.text.lower() and phrase not in symptoms:
                    symptoms.append(phrase)
                    red_flags.append(flag)

    callback_requested = "call me back" in lowered or "callback" in lowered or bool(
        responses and any(r.callback_requested for r in responses)
    )
    callback_preference = None
    for response in responses or []:
        if response.callback_preference:
            callback_preference = response.callback_preference
            break
    uncertainty = bool(responses and any(r.uncertain for r in responses))

    return IntakeSummary(
        identity_verified=identity_verified,
        symptoms=sorted(set(symptoms)),
        red_flags=sorted(set(red_flags)),
        uncertainty=uncertainty,
        callback_requested=callback_requested,
        callback_preference=callback_preference,
        transcript=transcript,
        questions_asked=list(QUESTIONS),
        disposition="ready for triage",
    )


def run_voice_intake(
    patient: Patient,
    encounter: Encounter,
    patient_seed: int | None = None,
    override: str | None = None,
) -> IntakeSummary:
    """Run the full simulated voice intake and return the structured summary."""
    responses, transcript = synthesize_transcript(patient, encounter, patient_seed=patient_seed, override=override)
    return extract_intake(transcript, responses=responses)