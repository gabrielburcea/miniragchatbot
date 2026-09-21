from app.rag.chunking import chunk_text, CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS

def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []

def test_short_text_returns_single_chunk():
    text = "This is a short text."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text 

def test_long_text_produces_multiple_chunks():
    # build text longer then CHUNK_SIZE_CHARS across several paragraps 
    paragraph = "This is a sentence about company policy. " * 5
    text = "\n".join([paragraph] * 5)  # 5 paragraphs
    chunks = chunk_text(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= CHUNK_SIZE_CHARS + CHUNK_OVERLAP_CHARS + 5 # small  tolerance for overlap prefix

def test_no_chunk_exceeds_size_plus_overlap():
    text = ("Clause number " + "x" * 40 + ". ") * 30 
    chunks = chunk_text(text)
    for c in chunks:
        assert len(c) <= CHUNK_SIZE_CHARS + CHUNK_OVERLAP_CHARS + 10  

def test_adjacent_chunks_have_overlap():
   paragraph = "Alpha beta gamma delta epsilon zeta eta theta. " * 10
   text = "\n".join([paragraph] * 3)
   chunks = chunk_text(text)
   if len(chunks) > 1:
    prev_tail = chunks[0][-CHUNK_OVERLAP_CHARS:]
    assert prev_tail.strip()[:20] in chunks[1]