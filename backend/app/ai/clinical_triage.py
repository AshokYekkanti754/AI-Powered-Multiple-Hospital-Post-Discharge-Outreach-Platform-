from app.ai.consensus_council import TriageDecision, TriageStatus
from app.ai.rag.protocol_retriever import retrieve_protocols


URGENT_TERMS = {"chest pain", "severe bleeding", "cannot breathe", "loss of consciousness"}


def triage_with_protocols(db, *, hospital_id, transcript: str) -> TriageDecision:
    protocols = retrieve_protocols(db, hospital_id=hospital_id, query=transcript)
    lowered = transcript.lower()
    status = TriageStatus.URGENT if any(term in lowered for term in URGENT_TERMS) else TriageStatus.ROUTINE
    if not protocols:
        status = TriageStatus.UNCERTAIN if status is TriageStatus.ROUTINE else status
    return TriageDecision(status=status, rationale="Deterministic safety adapter", protocol_citations=[str(doc.id) for doc in protocols])
