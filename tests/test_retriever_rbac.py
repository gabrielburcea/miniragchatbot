from app.rag.embeddings import embed_texts
from app.rag.retriever import retrieve_chunks
from app.rag.vectorstore import delete_by_source_file, ensure_collection, upsert_chunks

TEST_SOURCE = "rbac_test_doc.pdf"


def _seed_chunks():
    """Inserts one chunk per department/level combo used by the RBAC rules."""
    texts = [
        "hr level 1 chunk about leave policy",
        "hr level 2 chunk about performance reviews",
        "finance level 1 chunk about expenses",
        "exec level 3 chunk about strategic plan",
    ]
    vectors = embed_texts(texts)
    chunks = [
        {"text": texts[0], "embedding": vectors[0], "department": "hr", "access_level": 1, "source_file": TEST_SOURCE, "page": 1},
        {"text": texts[1], "embedding": vectors[1], "department": "hr", "access_level": 2, "source_file": TEST_SOURCE, "page": 1},
        {"text": texts[2], "embedding": vectors[2], "department": "finance", "access_level": 1, "source_file": TEST_SOURCE, "page": 1},
        {"text": texts[3], "embedding": vectors[3], "department": "exec", "access_level": 3, "source_file": TEST_SOURCE, "page": 1},
    ]
    upsert_chunks(chunks)


def setup_function():
    ensure_collection()
    delete_by_source_file(TEST_SOURCE)
    _seed_chunks()


def teardown_function():
    delete_by_source_file(TEST_SOURCE)


def test_hr_level1_sees_only_hr_level1():
    """HR user at level 1 must only retrieve hr chunks at or below level 1."""
    results = retrieve_chunks("policy", department="hr", level=1, top_k=50)
    depts_levels = {(r["department"], r["access_level"]) for r in results if r["source_file"] == TEST_SOURCE}
    assert depts_levels == {("hr", 1)}


def test_finance_level1_sees_finance_and_hr_level1_not_exec():
    """Finance user must see own department plus hr, never exec content."""
    results = retrieve_chunks("policy", department="finance", level=1, top_k=50)
    depts_levels = {(r["department"], r["access_level"]) for r in results if r["source_file"] == TEST_SOURCE}
    assert depts_levels == {("finance", 1), ("hr", 1)}


def test_exec_level3_sees_exec_and_all_hr_not_finance():
    """Exec user gets own department and all hr levels, never finance."""
    results = retrieve_chunks("policy", department="exec", level=3, top_k=50)
    depts_levels = {(r["department"], r["access_level"]) for r in results if r["source_file"] == TEST_SOURCE}
    assert depts_levels == {("exec", 3), ("hr", 1), ("hr", 2)}


def test_hr_level1_never_sees_hr_level2():
    """Access level filtering must be strictly less-than-or-equal, not unbounded."""
    results = retrieve_chunks("policy", department="hr", level=1, top_k=50)
    levels = {r["access_level"] for r in results if r["source_file"] == TEST_SOURCE and r["department"] == "hr"}
    assert 2 not in levels