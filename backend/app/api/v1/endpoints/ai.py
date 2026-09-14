import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.ai.clinical_triage import triage_with_protocols
from app.ai.consensus_council import TriageDecision, TriageStatus, run_consensus
from app.ai.llm_provider import assess as llm_assess, active_model
from app.ai.rag.protocol_retriever import embed_text
from app.api.v1.deps import db_session, get_current_context, require_roles
from app.db.models.ai_log import AILog
from app.db.models.protocol_doc import ProtocolDocument
from app.db.models.user import UserRole
from app.middleware.tenant import TenantContext
from app.services.ai_observability import metrics, record_ai_log

router = APIRouter()


class ProtocolUpload(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class TriageRequest(BaseModel):
    transcript: str = Field(min_length=1)
    call_id: uuid.UUID | None = None


class ProviderStatus(BaseModel):
    provider: str
    mode: str
    model: str
    hint: str | None = None
    chain: list[dict] = []


@router.get("/provider-status", response_model=ProviderStatus)
def provider_status(context: TenantContext = Depends(get_current_context)):
    from app.ai.llm_provider import provider_status as _status
    return ProviderStatus(**_status())


@router.post("/protocols/upload", status_code=201)
def upload_protocol(payload: ProtocolUpload, db: Session = Depends(db_session), context: TenantContext = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.CLINICAL_REVIEWER))):
    document = ProtocolDocument(hospital_id=context.hospital_id, title=payload.title, content=payload.content, embedding=embed_text(payload.content))
    db.add(document); db.commit(); db.refresh(document)
    return {"id": str(document.id), "title": document.title}


@router.get("/protocols")
def list_protocols(db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    rows = db.query(ProtocolDocument).filter(ProtocolDocument.hospital_id == context.hospital_id).order_by(ProtocolDocument.created_at.desc()).all()
    return [{"id": str(r.id), "title": r.title, "content": r.content[:400]} for r in rows]


def _assessor(name: str):
    def _fn(text: str) -> TriageDecision:
        out = llm_assess(text, agent_name=name)
        return TriageDecision(status=TriageStatus(out["status"]), rationale=out["rationale"])
    _fn.__name__ = name
    return _fn


@router.post("/triage/evaluate")
def evaluate(payload: TriageRequest, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    base = triage_with_protocols(db, hospital_id=context.hospital_id, transcript=payload.transcript)
    result = run_consensus(payload.transcript, [_assessor("assessor_a"), _assessor("assessor_b"), lambda text: base])
    record_ai_log(db, hospital_id=context.hospital_id, call_id=payload.call_id, agent_name="consensus_council", model_used=active_model(), prompt_tokens=len(payload.transcript.split()), completion_tokens=1, latency_ms=0, structured_output=result.model_dump(mode="json"), disagreement=result.disagreement)
    db.commit()
    return result.model_dump(mode="json")


@router.get("/metrics")
def ai_metrics(db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    return metrics(db, hospital_id=context.hospital_id)


@router.get("/logs")
def ai_logs(limit: int = 50, db: Session = Depends(db_session), context: TenantContext = Depends(get_current_context)):
    query = db.query(AILog)
    if context.hospital_id is not None:
        query = query.filter(AILog.hospital_id == context.hospital_id)
    rows = query.order_by(AILog.created_at.desc()).limit(limit).all()
    return [{"id": str(r.id), "agent": r.agent_name, "model": r.model_used, "tokens": [r.prompt_tokens, r.completion_tokens],
             "cost": r.estimated_cost, "disagreement": r.consensus_disagreement,
             "output": r.structured_output, "at": r.created_at} for r in rows]

