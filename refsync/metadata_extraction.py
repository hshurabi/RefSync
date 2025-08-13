import fitz  # PyMuPDF

def read_pdf_metadata(pdf_path: str):
    doc = fitz.open(pdf_path)
    md = doc.metadata or {}
    title = (md.get("title") or "").strip()
    author = (md.get("author") or "").strip()
    text_first_page = ""
    if doc.page_count > 0:
        text_first_page = doc[0].get_text("text")
    doc.close()
    return title, author, text_first_page

def guess_title_from_first_page(text_first_page: str) -> str:
    if not text_first_page:
        return ""
    lines = [l.strip() for l in text_first_page.splitlines()]
    candidates = [l for l in lines if 8 <= len(l) <= 200 and not l.isupper()]
    return candidates[0] if candidates else ""
