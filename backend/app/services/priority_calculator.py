"""Pure priority calculation for outbound queue tasks."""


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def calculate_priority_score(*, risk_score: float, time_remaining_hours: float, total_followup_window_hours: float, campaign_priority: int, retry_count: int = 0) -> float:
    if total_followup_window_hours <= 0:
        raise ValueError("total_followup_window_hours must be greater than zero")
    if not 1 <= campaign_priority <= 5:
        raise ValueError("campaign_priority must be between 1 and 5")
    if retry_count < 0:
        raise ValueError("retry_count cannot be negative")
    normalized_risk = _clamp(risk_score if risk_score <= 1 else risk_score / 100.0)
    urgency = _clamp(1.0 - (time_remaining_hours / total_followup_window_hours))
    normalized_campaign_priority = campaign_priority / 5.0
    return (normalized_risk * 40.0) + (urgency * 35.0) + (normalized_campaign_priority * 15.0) - (retry_count * 10.0)


priority_score = calculate_priority_score
