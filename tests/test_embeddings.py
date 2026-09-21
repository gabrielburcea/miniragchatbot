from app.rag.embeddings import embed_texts, embed_query


def test_embed_texts_returns_correct_count():
    vectors = embed_texts(["Hello world", "goodbye world"])
    assert len(vectors) == 2

def test_embed_texts_empty_list_returns_empty():
    assert embed_texts([]) == []

def test_embed_vectors_have_consistent_dimensions():
    vectors = embed_texts(("one", "two", "three"))
    dims = {len(v) for v in vectors}
    assert len(dims) == 1  # All vectors should have the same dimension

def test_embed_query_returns_vector():
    vector = embed_query("How many leave days do I get")
    assert isinstance(vector, list)
    assert len(vector) > 0  # The vector should not be empty

def test_similar_texts_have_higher_similarity_than_unrelatted():
    import numpy as np

    v1 = embed_query("How many vacation days do employees get?")
    v2 = embed_query("What is the annual leave policy?")
    v3 = embed_query("How do I file an expense report?")
    sim_related = np.dot(v1, v2) 
    sim_unrelated = np.dot(v1, v3)
    assert sim_related > sim_unrelated