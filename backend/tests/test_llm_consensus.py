from app.ai.consensus_council import TriageDecision, TriageStatus, run_consensus


def test_one_urgent_agent_triggers_human_escalation():
    assessors = [
        lambda _: TriageDecision(status=TriageStatus.ROUTINE),
        lambda _: TriageDecision(status=TriageStatus.URGENT),
        lambda _: TriageDecision(status=TriageStatus.ROUTINE),
    ]
    result = run_consensus("symptoms", assessors)
    assert result.human_escalation is True
    assert result.disagreement is True
    assert result.final_status is TriageStatus.ESCALATED


def test_unanimous_routine_is_not_escalated():
    result = run_consensus("symptoms", [lambda _: {"status": "routine"}] * 3)
    assert result.final_status is TriageStatus.ROUTINE
    assert result.human_escalation is False
