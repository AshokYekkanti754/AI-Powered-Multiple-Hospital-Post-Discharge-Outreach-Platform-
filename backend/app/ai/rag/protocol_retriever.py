from __future__ import annotations
import math
import re
from sqlalchemy.orm import Session
from app.db.models.protocol_doc import ProtocolDocument


def embed_text(text: str, dimensions: int = 32) -> list[float]:
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        vector[hash(token) % dimensions] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def retrieve_protocols(db: Session, *, hospital_id, query: str, limit: int = 3) -> list[ProtocolDocument]:
    query_embedding = embed_text(query)
    documents = db.query(ProtocolDocument).filter(ProtocolDocument.hospital_id == hospital_id).all()
    return sorted(documents, key=lambda doc: _cosine(query_embedding, doc.embedding), reverse=True)[:limit]
