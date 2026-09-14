from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from pydantic import BaseModel


class TriageStatus(str, Enum):
    ROUTINE = "routine"
    CONCERNING = "concerning"
    URGENT = "urgent"
    UNCERTAIN = "uncertain"
    ESCALATED = "escalated"


class TriageDecision(BaseModel):
    status: TriageStatus
    rationale: str = ""
    protocol_citations: list[str] = []


class ConsensusResult(BaseModel):
    final_status: TriageStatus
    decisions: list[TriageDecision]
    disagreement: bool
    human_escalation: bool
    arbiter_used: bool = False


def run_consensus(transcript: str, assessors: list, arbiter=None) -> ConsensusResult:
    if len(assessors) != 3:
        raise ValueError("consensus council requires exactly three assessors")
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            decisions = list(pool.map(lambda assessor: assessor(transcript), assessors))
        decisions = [item if isinstance(item, TriageDecision) else TriageDecision.model_validate(item) for item in decisions]
    except Exception as exc:
        return ConsensusResult(final_status=TriageStatus.ESCALATED, decisions=[], disagreement=True, human_escalation=True, arbiter_used=False)
    statuses = [decision.status for decision in decisions]
    disagreement = len(set(statuses)) != 1
    requires_escalation = disagreement or any(status in {TriageStatus.URGENT, TriageStatus.CONCERNING, TriageStatus.UNCERTAIN} for status in statuses)
    if requires_escalation and arbiter is not None:
        try:
            result = arbiter(decisions)
            final = result if isinstance(result, TriageStatus) else TriageStatus(result)
            return ConsensusResult(final_status=final, decisions=decisions, disagreement=disagreement, human_escalation=True, arbiter_used=True)
        except Exception:
            pass
    if requires_escalation:
        return ConsensusResult(final_status=TriageStatus.ESCALATED, decisions=decisions, disagreement=disagreement, human_escalation=True)
    return ConsensusResult(final_status=TriageStatus.ROUTINE, decisions=decisions, disagreement=False, human_escalation=False)
