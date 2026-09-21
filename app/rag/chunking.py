"""
Chunking strategy. 

Chunck size/overlap chosen base don inspecting the actual source docs:
- each policy PDF is approx 1 page , I believe under 1600 chars? with numbered sections 
e.g. 1. Purpose , 2. Membership, etc.) A aprox of 500 char chunck with aprox 80 char overlap
roughly aligns one chuncl to one policy clause /section. 
Thus a questions like "how mani leave days" retrieves the relevant clause rather than the whole doc. 
Splits on paragraph boundaries first, falling back to hard character slicing only if a paragraph is unusually long. 
"""

CHUNK_SIZE_CHARS = 550
CHUNK_OVERLAP_CHARS = 80


def chunk_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = f"{current} {para}".strip() if current else para

        if len(candidate) <= CHUNK_SIZE_CHARS:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(para) <= CHUNK_SIZE_CHARS:
            current = para
        else:
            start = 0
            while start < len(para):
                end = start + CHUNK_SIZE_CHARS
                chunks.append(para[start:end])
                start = end - CHUNK_OVERLAP_CHARS
            current = ""

    if current:
        chunks.append(current)

    # add overlap between adjacent chunks
    result = []
    for i, c in enumerate(chunks):
        if i == 0:
            result.append(c)
        else:
            prev_tail = chunks[i - 1][-CHUNK_OVERLAP_CHARS:]
            result.append(f"{prev_tail} {c}")

    return result