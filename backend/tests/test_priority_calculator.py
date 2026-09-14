import pytest
from app.services.priority_calculator import calculate_priority_score


def test_high_risk_and_urgent_patient_outranks_routine_patient():
    high = calculate_priority_score(risk_score=0.95, time_remaining_hours=2, total_followup_window_hours=48, campaign_priority=5)
    routine = calculate_priority_score(risk_score=0.10, time_remaining_hours=40, total_followup_window_hours=48, campaign_priority=1)
    assert high > routine + 20


def test_priority_clamps_urgency_and_normalizes_percentage_risk():
    assert calculate_priority_score(risk_score=100, time_remaining_hours=-1, total_followup_window_hours=48, campaign_priority=5) == 90
    assert calculate_priority_score(risk_score=0, time_remaining_hours=100, total_followup_window_hours=48, campaign_priority=1) == 3


def test_invalid_priority_inputs_raise():
    with pytest.raises(ValueError):
        calculate_priority_score(risk_score=0.5, time_remaining_hours=1, total_followup_window_hours=0, campaign_priority=3)
