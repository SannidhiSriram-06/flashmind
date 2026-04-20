import os
import pdfplumber

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def extract_text_chunks(pdf_path: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """Extract text from a PDF and split into overlapping chunks.

    Raises:
        ValueError: for password-protected, image-only, oversized, or too-short PDFs.
    """
    if os.path.getsize(pdf_path) > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 10 MB size limit")

    chunks = []
    chunk_id = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if not text or not text.strip():
                    continue

                text = text.strip()
                start = 0
                while start < len(text):
                    end = start + chunk_size
                    chunk_text = text[start:end].strip()
                    if chunk_text:
                        chunks.append({
                            "chunk_id": str(chunk_id),
                            "text": chunk_text,
                            "page": page_num,
                        })
                        chunk_id += 1
                    start = end - overlap

    except Exception as e:
        msg = str(e).lower()
        if any(w in msg for w in ("password", "encrypt", "decrypt", "pdfencrypt")):
            raise ValueError(
                "This PDF is password-protected. Please remove the password and try again."
            ) from e
        raise

    if not chunks:
        raise ValueError(
            "No extractable text found in this PDF. "
            "It may be a scanned image-only document — try a PDF with selectable text."
        )

    return chunks
