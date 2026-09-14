from __future__ import annotations
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models.ai_log import AILog

MODEL_COST_PER_1K = {"deterministic": 0.0, "gpt-4o-mini": 0.00015}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    return ((prompt_tokens + completion_tokens) / 1000.0) * MODEL_COST_PER_1K.get(model, 0.0)


def record_ai_log(db: Session, *, hospital_id, agent_name: str, model_used: str, prompt_tokens: int, completion_tokens: int, latency_ms: int, structured_output: dict, disagreement: bool = False, call_id=None) -> AILog:
    row = AILog(hospital_id=hospital_id, call_id=call_id, agent_name=agent_name, model_used=model_used, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, latency_ms=latency_ms, estimated_cost=estimate_cost(model_used, prompt_tokens, completion_tokens), structured_output=structured_output, consensus_disagreement=disagreement)
    db.add(row)
    return row


def metrics(db: Session, *, hospital_id) -> dict:
    query = db.query(AILog)
    if hospital_id is not None:
        query = query.filter(AILog.hospital_id == hospital_id)
    rows = query.all()
    return {"requests": len(rows), "prompt_tokens": sum(row.prompt_tokens for row in rows), "completion_tokens": sum(row.completion_tokens for row in rows), "estimated_cost": sum(row.estimated_cost for row in rows), "disagreements": sum(1 for row in rows if row.consensus_disagreement), "disagreement_rate": (sum(1 for row in rows if row.consensus_disagreement) / len(rows)) if rows else 0.0}
