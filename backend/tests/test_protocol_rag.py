from datetime import date
from app.db.models.patient import Patient
from app.db.models.protocol_doc import ProtocolDocument
from app.ai.rag.protocol_retriever import embed_text, retrieve_protocols


def test_protocol_retrieval_is_tenant_isolated(db_session, make_hospital):
    hospital_a = make_hospital(name="A")
    hospital_b = make_hospital(name="B")
    db_session.add_all([
        ProtocolDocument(hospital_id=hospital_a.id, title="A protocol", content="chest pain pathway", embedding=embed_text("chest pain pathway")),
        ProtocolDocument(hospital_id=hospital_b.id, title="B protocol", content="chest pain pathway", embedding=embed_text("chest pain pathway")),
    ])
    db_session.commit()
    result = retrieve_protocols(db_session, hospital_id=hospital_a.id, query="chest pain")
    assert [doc.title for doc in result] == ["A protocol"]
