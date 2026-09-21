from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.rag.embeddings import embed_texts
from app.rag.vectorstore import (
    delete_by_source_file,
    ensure_collection,
    query,
    upsert_chunks,
)


def test_ensure_collection_is_idempotent():
    ensure_collection()
    ensure_collection()  # calling twice should not raise


def test_upsert_and_query_roundtrip():
    ensure_collection()
    delete_by_source_file("test_doc.pdf")

    texts = ["Employees get 22 leave days per year.", "Expense reports are due monthly."]
    vectors = embed_texts(texts)

    chunks = [
        {
            "text": texts[0],
            "embedding": vectors[0],
            "department": "hr",
            "access_level": 1,
            "source_file": "test_doc.pdf",
            "page": 1,
        },
        {
            "text": texts[1],
            "embedding": vectors[1],
            "department": "finance",
            "access_level": 1,
            "source_file": "test_doc.pdf",
            "page": 1,
        },
    ]
    upsert_chunks(chunks)

    query_vector = embed_texts(["How many leave days do I get?"])[0]
    rbac_filter = Filter(
        must=[FieldCondition(key="department", match=MatchValue(value="hr"))]
    )
    results = query(query_vector, rbac_filter, k=5)

    assert len(results) >= 1
    assert all(r["department"] == "hr" for r in results)
    assert any("leave" in r["text"].lower() for r in results)

    delete_by_source_file("test_doc.pdf")