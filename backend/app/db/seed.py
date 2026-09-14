"""
Demo data seeder (PRD §119: "Appropriate seeded data").

Provides an idempotent seed of the core operating entities so that login,
dashboards, campaigns, queues and the AI call pipeline all have real data to
work with on first boot:

  - 1 platform admin
  - 2 hospitals, each with HOSPITAL_ADMIN / CAMPAIGN_MANAGER /
    CLINICAL_REVIEWER users
  - ~60 patients per hospital (with encounters, conditions, observations)
  - 1 DRAFT campaign per hospital
  - hospital-specific clinical protocol documents (used by RAG triage)
  - a small number of COMPLETED / RETRY_SCHEDULED queue tasks + AI logs so
    the dashboards show meaningful non-zero numbers immediately

The seeder is safe to run repeatedly: it is skipped wholesale when the users
table already contains rows.
"""
from __future__ import annotations

import random
from datetime import datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.ai_log import AILog
from app.db.models.campaign import Campaign, CampaignStatus
from app.db.models.condition import Condition
from app.db.models.encounter import Encounter, RiskTier
from app.db.models.hospital import Hospital
from app.db.models.observation import Observation
from app.db.models.patient import Patient
from app.db.models.protocol_doc import ProtocolDocument
from app.db.models.queue_task import QueueTask, QueueTaskStatus
from app.db.models.user import User, UserRole
from app.services.eligibility_engine import compute_risk_tier
from app.services.priority_calculator import calculate_priority_score

DEMO_PASSWORD = "Demo@123"
PLATFORM_ADMIN_EMAIL = "admin@platform.local"

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Susan", "Richard", "Jessica", "Joseph", "Sarah",
    "Thomas", "Karen", "Charles", "Nancy", "Christopher", "Lisa", "Daniel", "Margaret",
    "Matthew", "Betty", "Anthony", "Sandra", "Mark", "Ashley", "Donald", "Dorothy",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White",
    "Harris", "Clark", "Lewis", "Robinson", "Walker", "Young", "Hall", "Allen", "King",
]

CONDITIONS_BY_TIER = {
    RiskTier.LOW: [("I10", "Hypertension"), ("E11", "Type 2 diabetes"),
                   ("M25", "Joint pain"), ("Z00", "Routine post-operative check")],
    RiskTier.MEDIUM: [("I48", "Cardiac dysrhythmia"), ("J45", "Asthma"),
                      ("I63", "Cerebral infarction"), ("N18", "Chronic kidney disease")],
    RiskTier.HIGH: [("I21", "Acute myocardial infarction"), ("J81", "Pulmonary oedema"),
                    ("I61", "Intracerebral haemorrhage"), ("E10", "Type 1 diabetes")],
    RiskTier.CRITICAL: [("I21", "Acute myocardial infarction"), ("R57", "Shock"),
                        ("I61", "Intracerebral haemorrhage"), ("J96", "Respiratory failure")],
}

PROTOCOLS = [
    (
        "Cardiac Discharge Follow-up Protocol",
        "Post-discharge follow-up within 48 hours. Red-flag symptoms requiring "
        "escalation: new or worsening chest pain, shortness of breath at rest, "
        "rapid heart rate, dizziness or fainting, bleeding from the incision site. "
        "Confirm medication adherence and schedule a follow-up in 7 days.",
    ),
    (
        "General Post-Operative Care Protocol",
        "Ask about pain level, surgical site (warmth, redness, discharge), temperature, "
        "appetite and activity. Escalate for fever above 100.4F, uncontrolled pain, "
        "wound drainage or inability to eat/drink. Reinforce discharge instructions.",
    ),
    (
        "Respiratory Discharge Follow-up Protocol",
        "Ask about breathing, cough, medication use and oxygen needs. Escalate for "
        "worsening shortness of breath, chest tightness, blue lips or fingernails, "
        "or worsening cough with fever.",
    ),
]


def _make_hospital(db: Session, name: str, seed: int, domain: str) -> Hospital:
    rng = random.Random(seed)
    hospital = Hospital(
        name=name,
        timezone="America/New_York",
        max_concurrent_calls=8,
        retry_limit=3,
        calling_hours_start=time(9, 0),
        calling_hours_end=time(19, 0),
    )
    db.add(hospital)
    db.flush()

    roles = [
        (f"admin@{domain}", "Hospital Admin", UserRole.HOSPITAL_ADMIN),
        (f"campaign@{domain}", "Campaign Manager", UserRole.CAMPAIGN_MANAGER),
        (f"clinical@{domain}", "Clinical Reviewer", UserRole.CLINICAL_REVIEWER),
    ]
    for email, full_name, role in roles:
        db.add(User(hospital_id=hospital.id, email=email, hashed_password=hash_password(DEMO_PASSWORD), full_name=full_name, role=role))
    db.flush()

    # Patients with encounters scattered across the last ~40h so they sit inside
    # the default 48h follow-up window and are immediately eligible.
    now = datetime.now(timezone.utc)
    tier_pool = [RiskTier.LOW] * 18 + [RiskTier.MEDIUM] * 20 + [RiskTier.HIGH] * 14 + [RiskTier.CRITICAL] * 8
    for i in range(60):
        mrn = f"{seed:02d}-{1000 + i}"
        patient = Patient(
            hospital_id=hospital.id,
            mrn=mrn,
            first_name=rng.choice(FIRST_NAMES),
            last_name=rng.choice(LAST_NAMES),
            phone_number=f"+1 (555) {100 + rng.randint(100, 899)}-{rng.randint(1000, 9999)}",
            date_of_birth=datetime(1945 + rng.randint(0, 60), rng.randint(1, 12), rng.randint(1, 28)).date(),
            preferred_language=rng.choices(["en", "es", "en", "en"], weights=[4, 1, 3, 2])[0],
            consent_status=rng.random() > 0.08,
        )
        db.add(patient)
        db.flush()

        risk_score = float(rng.randint(20, 95))
        tier = compute_risk_tier(risk_score)
        if tier not in tier_pool:
            tier = rng.choice(tier_pool)
        discharge = now - timedelta(hours=rng.uniform(1, 40))
        conditions = CONDITIONS_BY_TIER.get(tier, CONDITIONS_BY_TIER[RiskTier.LOW])
        chosen = [conditions[0]] + [extra for extra in conditions[1:] if rng.random() < 0.35]
        encounter = Encounter(
            hospital_id=hospital.id,
            patient_id=patient.id,
            discharge_timestamp=discharge,
            care_setting=rng.choice(["inpatient", "inpatient", "surgical", "observation"]),
            risk_score=risk_score,
            risk_tier=tier,
            discharge_instructions="Call your care team if you experience new or worsening symptoms. "
            "Take medications as prescribed and attend your follow-up appointment.",
            follow_up_window_hours=48,
        )
        db.add(encounter)
        db.flush()

        for idx, (code, description) in enumerate(chosen):
            db.add(Condition(patient_id=patient.id, code=code, description=description))
            db.add(Observation(
                patient_id=patient.id,
                encounter_id=encounter.id,
                observation_type="vital-sign" if idx == 0 else "symptom",
                value=f"{description.lower()} management",
                recorded_at=discharge,
            ))
    db.flush()
    return hospital
def _add_campaign_and_queue(db: Session, hospital: Hospital, seed: int) -> None:
    """Create one draft campaign per hospital plus a populated queue slice."""
    rng = random.Random(seed + 7)
    now = datetime.now(timezone.utc)

    campaign = Campaign(
        hospital_id=hospital.id,
        name=f"{hospital.name} — Discharge Follow-Up Cohort",
        status=CampaignStatus.DRAFT,
        follow_up_window_hours=48,
        max_retries=3,
        campaign_priority=3,
    )
    db.add(campaign)
    db.flush()

    for title, content in PROTOCOLS:
        db.add(ProtocolDocument(hospital_id=hospital.id, title=title, content=content, embedding=[]))

    patients = db.query(Patient).filter(Patient.hospital_id == hospital.id, Patient.consent_status.is_(True)).all()
    for j, patient in enumerate(patients):
        encounter = db.query(Encounter).filter(
            Encounter.patient_id == patient.id, Encounter.hospital_id == hospital.id
        ).first()
        if j % 9 == 0:
            status, retry_count = QueueTaskStatus.COMPLETED, rng.randint(0, 2)
        elif j % 9 == 4:
            status, retry_count = QueueTaskStatus.RETRY_SCHEDULED, 1
        else:
            status, retry_count = QueueTaskStatus.PENDING, 0
        db.add(QueueTask(
            hospital_id=hospital.id,
            campaign_id=campaign.id,
            patient_id=patient.id,
            status=status,
            retry_count=retry_count,
            priority_score=calculate_priority_score(
                risk_score=encounter.risk_score,
                time_remaining_hours=36.0,
                total_followup_window_hours=48,
                campaign_priority=3,
            ),
            scheduled_for=None if status in (QueueTaskStatus.PENDING, QueueTaskStatus.COMPLETED)
            else now + timedelta(minutes=rng.randint(5, 120)),
        ))
    db.flush()
    _add_ai_logs(db, hospital, rng)


def _add_ai_logs(db: Session, hospital: Hospital, rng: random.Random) -> None:
    for k in range(4):
        db.add(AILog(
            hospital_id=hospital.id,
            call_id=None,
            agent_name=rng.choice(["consensus_council", "clinical_triage", "documentation_agent"]),
            model_used="deterministic",
            prompt_tokens=120 + k * 13,
            completion_tokens=8 + k * 2,
            latency_ms=rng.randint(4, 40),
            estimated_cost=0.0,
            structured_output={"scenario": "seed"},
            consensus_disagreement=k % 3 == 0,
        ))
    db.flush()


def seed_demo_data(db: Session) -> dict:
    """Seed demo data if the users table is empty. Returns a summary dict."""
    existing = db.query(User).first()
    if existing is not None:
        return {"seeded": False, "reason": "users table already populated"}

    platform_admin = User(
        hospital_id=None,
        email=PLATFORM_ADMIN_EMAIL,
        hashed_password=hash_password(DEMO_PASSWORD),
        full_name="Platform Administrator",
        role=UserRole.PLATFORM_ADMIN,
    )
    db.add(platform_admin)
    db.flush()

    h1 = _make_hospital(db, "St. Mary's General Hospital", seed=11, domain="stmarys.demo")
    h2 = _make_hospital(db, "Riverside Medical Center", seed=22, domain="riverside.demo")
    _add_campaign_and_queue(db, h1, 11)
    _add_campaign_and_queue(db, h2, 22)

    db.commit()
    return {
        "seeded": True,
        "platform_admin": PLATFORM_ADMIN_EMAIL,
        "demo_password": DEMO_PASSWORD,
        "hospitals": [
            {"id": str(h1.id), "name": h1.name},
            {"id": str(h2.id), "name": h2.name},
        ],
    }


def run_seed() -> dict:
    """Convenience runner for CLI use with a fresh session."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return seed_demo_data(db)
    finally:
        db.close()


if __name__ == "__main__":
    result = run_seed()
    print(result)