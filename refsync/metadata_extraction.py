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

def guess_title_from_first_page(text_first_page: str, start_line: int = 1) -> str:
   
    if not text_first_page:
        return ""
    lines = [line.strip() for line in text_first_page.split('\n') if line.strip()]
    # Heuristic: skip first 2 lines, look for plausible title lines
    title_lines = []
    for line in lines[start_line:10]:  
        words = line.split()
        if (
            len(words) >= 4 and
            sum(c.isdigit() for c in line) < 5 and
            sum(c.isalpha() for c in line) > 10 and
            not any(w.lower() in ["copyright", "doi"] for w in words[:3])
        ):
            title_lines.append(line)
            # If the next line also looks plausible, add it
            next_idx = lines.index(line) + 1
            if next_idx < len(lines):
                next_line = lines[next_idx]
                next_words = next_line.split()
                if (
                    len(next_words) >= 3 and
                    not next_line.isupper() and
                    sum(c.isdigit() for c in next_line) < 5 and
                    sum(c.isalpha() for c in next_line) > 5
                ):
                    title_lines.append(next_line)
            break  # Stop after finding the first plausible title block
    if title_lines:
        return " ".join(title_lines)
    # Fallback: longest line in first 10 lines
    candidates = [
        l for l in lines[:10]
        if not l.isupper() and sum(c.isdigit() for c in l) < 5 and len(l.split()) >= 4
    ]
    if candidates:
        return max(candidates, key=len)
    return ""