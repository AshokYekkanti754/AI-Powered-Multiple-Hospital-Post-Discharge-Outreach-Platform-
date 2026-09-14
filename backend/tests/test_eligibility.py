"""
Unit tests: eligibility engine scoring rules (risk tiers, follow-up window,
consent gating).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.db.models.encounter import RiskTier
from app.services.eligibility_engine import compute_risk_tier, evaluate_eligibility


@pytest.mark.parametrize("score,expected", [
    (10, RiskTier.LOW),
    (34.9, RiskTier.LOW),
    (35, RiskTier.MEDIUM),
    (64.9, RiskTier.MEDIUM),
    (65, RiskTier.HIGH),
    (84.9, RiskTier.HIGH),
    (85, RiskTier.CRITICAL),
    (100, RiskTier.CRITICAL),
])
def test_compute_risk_tier_thresholds(score, expected):
    assert compute_risk_tier(score) == expected


def test_compute_risk_tier_rejects_out_of_range():
    with pytest.raises(ValueError):
        compute_risk_tier(-1)
    with pytest.raises(ValueError):
        compute_risk_tier(101)


def test_high_risk_patient_within_window_is_eligible():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    discharge = now - timedelta(hours=10)
    result = evaluate_eligibility(
        encounter_id="e1", patient_id="p1",
        discharge_timestamp=discharge, follow_up_window_hours=48,
        risk_score=90, consent_status=True, now=now,
    )
    assert result.eligible is True
    assert result.risk_tier == RiskTier.CRITICAL
    assert result.reason == "within_follow_up_window"


def test_routine_patient_with_expired_window_is_not_eligible():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    discharge = now - timedelta(hours=100)
    result = evaluate_eligibility(
        encounter_id="e2", patient_id="p2",
        discharge_timestamp=discharge, follow_up_window_hours=48,
        risk_score=20, consent_status=True, now=now,
    )
    assert result.eligible is False
    assert result.reason == "follow_up_window_expired"
    assert result.risk_tier == RiskTier.LOW


def test_high_risk_patient_scores_eligible_and_low_risk_expired_is_not():
    """Direct comparison: a high-risk patient still in-window is eligible
    while a routine patient past the window is not — proving risk tier and
    window expiry are evaluated independently, as the milestone requires."""
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    high_risk = evaluate_eligibility(
        encounter_id="e3", patient_id="p3",
        discharge_timestamp=now - timedelta(hours=5), follow_up_window_hours=48,
        risk_score=92, consent_status=True, now=now,
    )
    expired_routine = evaluate_eligibility(
        encounter_id="e4", patient_id="p4",
        discharge_timestamp=now - timedelta(hours=72), follow_up_window_hours=48,
        risk_score=15, consent_status=True, now=now,
    )
    assert high_risk.eligible is True
    assert expired_routine.eligible is False


def test_patient_without_consent_is_never_eligible_even_if_critical():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    result = evaluate_eligibility(
        encounter_id="e5", patient_id="p5",
        discharge_timestamp=now - timedelta(hours=1), follow_up_window_hours=48,
        risk_score=99, consent_status=False, now=now,
    )
    assert result.eligible is False
    assert result.reason == "patient_has_not_consented"


def test_future_discharge_timestamp_is_not_eligible():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    result = evaluate_eligibility(
        encounter_id="e6", patient_id="p6",
        discharge_timestamp=now + timedelta(hours=2), follow_up_window_hours=48,
        risk_score=50, consent_status=True, now=now,
    )
    assert result.eligible is False
    assert result.reason == "discharge_is_in_the_future"
