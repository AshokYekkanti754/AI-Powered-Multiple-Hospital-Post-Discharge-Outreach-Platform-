"""
Eligibility engine (PRD §17-18).

A patient/encounter is "eligible" for outreach when:
  - it's within its follow_up_window_hours of discharge_timestamp (not expired), and
  - the hospital hasn't disabled contact (consent_status on the patient).

Risk tiers are assigned from risk_score using fixed thresholds. This module
is pure logic (no DB session, no I/O) so it's trivially unit-testable and
reusable by the future queue engine (Milestone 2.1) without modification.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.models.encounter import RiskTier


def compute_risk_tier(risk_score: float) -> RiskTier:
    if risk_score < 0 or risk_score > 100:
        raise ValueError("risk_score must be between 0 and 100")
    if risk_score >= 85:
        return RiskTier.CRITICAL
    if risk_score >= 65:
        return RiskTier.HIGH
    if risk_score >= 35:
        return RiskTier.MEDIUM
    return RiskTier.LOW


@dataclass
class EligibilityResult:
    encounter_id: str
    patient_id: str
    eligible: bool
    reason: str
    hours_since_discharge: float
    hours_remaining_in_window: float
    risk_tier: RiskTier


def evaluate_eligibility(
    *,
    encounter_id: str,
    patient_id: str,
    discharge_timestamp: datetime,
    follow_up_window_hours: int,
    risk_score: float,
    consent_status: bool,
    now: datetime | None = None,
) -> EligibilityResult:
    now = now or datetime.now(timezone.utc)
    if discharge_timestamp.tzinfo is None:
        discharge_timestamp = discharge_timestamp.replace(tzinfo=timezone.utc)

    hours_since = (now - discharge_timestamp).total_seconds() / 3600.0
    hours_remaining = follow_up_window_hours - hours_since
    risk_tier = compute_risk_tier(risk_score)

    if not consent_status:
        return EligibilityResult(
            encounter_id, patient_id, False, "patient_has_not_consented",
            hours_since, hours_remaining, risk_tier,
        )
    if hours_since < 0:
        return EligibilityResult(
            encounter_id, patient_id, False, "discharge_is_in_the_future",
            hours_since, hours_remaining, risk_tier,
        )
    if hours_remaining <= 0:
        return EligibilityResult(
            encounter_id, patient_id, False, "follow_up_window_expired",
            hours_since, hours_remaining, risk_tier,
        )
    return EligibilityResult(
        encounter_id, patient_id, True, "within_follow_up_window",
        hours_since, hours_remaining, risk_tier,
    )
