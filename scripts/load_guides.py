import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import pdfplumber
from config import DATABASE_URL, CAREER_GUIDES_DIR

MAX_CHUNK_CHARS = 4000


def extract_text_from_pdf(pdf_path: Path) -> list[tuple[int, str]]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append((i, text.strip()))
    return pages


def chunk_text(text: str, page_num: int) -> list[tuple[int, int, str]]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [(page_num, page_num, text)]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + MAX_CHUNK_CHARS, len(text))
        # Try to break at paragraph
        if end < len(text):
            for sep in ["\n\n", "\n", ". "]:
                idx = text.rfind(sep, start, end + 1)
                if idx > start:
                    end = idx + len(sep)
                    break
        chunks.append((page_num, page_num, text[start:end].strip()))
        start = end
    return chunks


def load_pdf_into_db(pdf_path: Path, conn) -> int:
    title = pdf_path.stem
    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        return 0
    cur = conn.cursor()
    count = 0
    chunk_id = 0
    for page_num, text in pages:
        for page_start, page_end, chunk in chunk_text(text, page_num):
            chunk_id += 1
            cur.execute(
                """
                INSERT INTO guides (title, section, chunk_id, text, page_start, page_end, source_pdf)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (title, chunk_id) DO UPDATE SET text = EXCLUDED.text
                """,
                (title, None, chunk_id, chunk, page_start, page_end, pdf_path.name),
            )
            count += 1
    cur.close()
    return count


def main():
    if not CAREER_GUIDES_DIR.exists():
        print("Career guides directory not found:", CAREER_GUIDES_DIR)
        sys.exit(1)
    pdfs = list(CAREER_GUIDES_DIR.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in", CAREER_GUIDES_DIR)
        sys.exit(1)
    conn = psycopg2.connect(DATABASE_URL)
    total = 0
    for pdf_path in sorted(pdfs):
        n = load_pdf_into_db(pdf_path, conn)
        total += n
        print("Loaded", pdf_path.name, "->", n, "chunks")
    conn.commit()
    conn.close()
    print("Total chunks loaded:", total)


if __name__ == "__main__":
    main()
