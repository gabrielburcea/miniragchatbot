"""Ingestion pipeline: extract PDF text (with OCR fallback), chunk, embed, store.

Access-level mapping is hardcoded per the assignment spec, since department
and access_level cannot be reliably inferred from PDF content alone.
"""

from pathlib import Path

import pymupdf
from pypdf import PdfReader
import pytesseract
from PIL import Image
import io

from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_texts
from app.rag.vectorstore import delete_by_source_file, ensure_collection, upsert_chunks

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

# file name -> (department, access_level), per README spec
ACCESS_LEVEL_MAP = {
    "leave_policy.pdf": ("hr", 1),
    "code_of_conduct.pdf": ("hr", 1),
    "performance_review.pdf": ("hr", 2),
    "expense_policy.pdf": ("finance", 1),
    "travel_reimbursement.pdf": ("finance", 1),
    "compensation_committee.pdf": ("exec", 3),
    "strategic_plan.pdf": ("exec", 3),
}

# below this many extracted characters, treat the page as scanned and OCR it
OCR_FALLBACK_THRESHOLD = 20


def extract_page_text(pdf_path: Path, page_index: int, page) -> str:
    text = page.extract_text() or ""
    if len(text.strip()) >= OCR_FALLBACK_THRESHOLD:
        return text

    # fallback: render the page as an image (via PyMuPDF) and OCR it
    doc = pymupdf.open(str(pdf_path))
    pix = doc[page_index].get_pixmap(dpi=200)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    ocr_text = pytesseract.image_to_string(image)
    doc.close()
    return ocr_text


def ingest_file(pdf_path: Path) -> int:
    """Process one PDF file: extract, chunk, embed, upsert. Returns chunk count."""
    filename = pdf_path.name
    if filename not in ACCESS_LEVEL_MAP:
        print(f"  skipping {filename}: not in access-level mapping")
        return 0

    department, access_level = ACCESS_LEVEL_MAP[filename]
    reader = PdfReader(str(pdf_path))

    delete_by_source_file(filename)

    all_chunks: list[dict] = []
    for page_index, page in enumerate(reader.pages):
        page_text = extract_page_text(pdf_path, page_index, page)
        for chunk in chunk_text(page_text):
            all_chunks.append(
                {
                    "text": chunk,
                    "department": department,
                    "access_level": access_level,
                    "source_file": filename,
                    "page": page_index + 1,
                }
            )

    if not all_chunks:
        print(f"  warning: no chunks produced for {filename}")
        return 0

    vectors = embed_texts([c["text"] for c in all_chunks])
    for c, v in zip(all_chunks, vectors):
        c["embedding"] = v

    upsert_chunks(all_chunks)
    return len(all_chunks)


def run_ingestion() -> None:
    ensure_collection()
    total_files = 0
    total_chunks = 0

    for pdf_path in sorted(DOCS_DIR.glob("**/*.pdf")):
        print(f"Ingesting {pdf_path.relative_to(DOCS_DIR)}...")
        count = ingest_file(pdf_path)
        print(f"  -> {count} chunks")
        total_files += 1
        total_chunks += count

    print(f"\nDone. Processed {total_files} files, {total_chunks} chunks total.")


if __name__ == "__main__":
    run_ingestion()