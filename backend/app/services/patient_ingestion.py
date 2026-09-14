"""
Bulk discharge ingestion (PRD §9).

Accepts a list of raw discharge dicts (from JSON or a parsed CSV) and, per
record: validates required fields, maps into Patient/Encounter/Condition/
Observation rows, and persists them scoped to a single hospital_id.

A malformed record never aborts the whole batch — it's logged to the
returned IngestionReport.errors and skipped, per the milestone's error
handling requirement.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.condition import Condition
from app.db.models.encounter import Encounter
from app.db.models.observation import Observation
from app.db.models.patient import Patient
from app.services.eligibility_engine import compute_risk_tier

REQUIRED_FIELDS = ["mrn", "first_name", "last_name", "phone_number", "date_of_birth", "discharge_timestamp", "risk_score"]


@dataclass
class IngestionError:
    index: int
    mrn: str | None
    error: str


@dataclass
class IngestionReport:
    hospital_id: str
    total_submitted: int
    ingested: int = 0
    failed: int = 0
    errors: list[IngestionError] = field(default_factory=list)
    patient_ids: list[str] = field(default_factory=list)


def _parse_date(value):
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def ingest_discharge_batch(db: Session, *, hospital_id: uuid.UUID, records: list[dict]) -> IngestionReport:
    report = IngestionReport(hospital_id=str(hospital_id), total_submitted=len(records))

    for idx, record in enumerate(records):
        mrn = record.get("mrn")
        try:
            missing = [f for f in REQUIRED_FIELDS if record.get(f) in (None, "")]
            if missing:
                raise ValueError(f"missing required fields: {', '.join(missing)}")

            dob = _parse_date(record["date_of_birth"]).date() if isinstance(record["date_of_birth"], str) else record["date_of_birth"]
            discharge_ts = _parse_date(record["discharge_timestamp"])
            if discharge_ts.tzinfo is None:
                discharge_ts = discharge_ts.replace(tzinfo=timezone.utc)

            risk_score = float(record["risk_score"])
            risk_tier = compute_risk_tier(risk_score)

            patient = Patient(
                hospital_id=hospital_id,
                mrn=str(mrn),
                first_name=record["first_name"],
                last_name=record["last_name"],
                phone_number=record["phone_number"],
                date_of_birth=dob,
                preferred_language=record.get("preferred_language", "en"),
                consent_status=record.get("consent_status", True),
            )
            db.add(patient)
            db.flush()

            encounter = Encounter(
                hospital_id=hospital_id,
                patient_id=patient.id,
                discharge_timestamp=discharge_ts,
                care_setting=record.get("care_setting", "inpatient"),
                risk_score=risk_score,
                risk_tier=risk_tier,
                discharge_instructions=record.get("discharge_instructions", ""),
                follow_up_window_hours=int(record.get("follow_up_window_hours", 48)),
            )
            db.add(encounter)
            db.flush()

            for cond in record.get("conditions", []):
                db.add(Condition(patient_id=patient.id, code=cond.get("code", ""), description=cond.get("description", "")))

            for obs in record.get("observations", []):
                recorded_at = _parse_date(obs.get("recorded_at")) or discharge_ts
                if recorded_at.tzinfo is None:
                    recorded_at = recorded_at.replace(tzinfo=timezone.utc)
                db.add(Observation(
                    patient_id=patient.id,
                    encounter_id=encounter.id,
                    observation_type=obs.get("observation_type", "unknown"),
                    value=str(obs.get("value", "")),
                    recorded_at=recorded_at,
                ))

            report.ingested += 1
            report.patient_ids.append(str(patient.id))
        except Exception as exc:  # noqa: BLE001 - deliberately broad: one bad record must not abort the batch
            report.failed += 1
            report.errors.append(IngestionError(index=idx, mrn=mrn, error=str(exc)))

    db.commit()
    return report
