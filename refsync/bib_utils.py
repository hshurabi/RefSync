import os
import re
import bibtexparser
STOPWORDS = {"a", "an", "the", "of", "in", "on", "for", "and", "to", "at", "by", "with", "from"}


def parse_bibtex_to_entry(bib_str: str):
    db = bibtexparser.loads(bib_str)
    if not db.entries:
        return None
    return db.entries[0]

def upsert_bib_entry(bib_path: str, new_entry: dict, dry_run=False):
    db = bibtexparser.loads("")
    if os.path.exists(bib_path):
        with open(bib_path, "r", encoding="utf-8") as f:
            db = bibtexparser.load(f)

    doi_new = (new_entry.get("doi") or "").lower().strip()
    replaced = False
    for e in db.entries:
        if (e.get("doi") or "").lower().strip() == doi_new and doi_new:
            e.update(new_entry)
            replaced = True
            break

    if not replaced:
        db.entries.append(new_entry)

    if not dry_run:
        with open(bib_path, "w", encoding="utf-8") as f:
            bibtexparser.dump(db, f)

def safe_bib_key(entry: dict) -> str:
    year = entry.get("year", "")
    title = entry.get("title", "")[0]
    authors = entry.get("author", [])
    author_strs = []
    for a in authors:
        family = a.get("family", "").strip()
        given = a.get("given", "").strip()
        author_strs.append(f"{family}, {given}".strip(", "))

    last = ""
    if author_strs:
        last = re.split(r"\band\b", author_strs[0])[0].strip().lower()
        last = re.split(r"[ ,]", last)[-1]
    words = re.sub(r"[^A-Za-z0-9]+", " ", title).strip().split()
    if words:
        fw = words[0].lower()
        if fw in STOPWORDS and len(words) > 1:
            fw = fw + "_" + words[1].lower()
    else:
        fw = ""
    key = f"{last}{year}{fw}".replace(" ", "")
    return key or "unnamed"

def add_or_update_file_field(entry: dict, pdf_rel_path: str):
    entry["file"] = "{:" + pdf_rel_path.replace("\\", "/") + ":PDF}"

def get_linked_pdf_basenames(bib_path: str) -> set[str]:
    linked = set()
    if not os.path.exists(bib_path):
        return linked
    with open(bib_path, "r", encoding="utf-8") as f:
        db = bibtexparser.load(f)
    for e in db.entries:
        fval = e.get("file")
        if not fval:
            continue
        parts = [p.strip() for p in fval.split(';') if p.strip()]
        for part in parts:
            pv = part.strip()
            if pv.startswith("{") and pv.endswith("}"):
                pv = pv[1:-1]
            chunks = pv.split(':')
            if len(chunks) >= 2:
                path = chunks[-2].strip()
                if path:
                    base = os.path.basename(path)
                    if base.lower().endswith(".pdf"):
                        linked.add(base.lower())
    return linked

def bib_has_doi_with_file(bib_path: str, doi: str) -> tuple[bool, str]:
    if not os.path.exists(bib_path) or not doi:
        return False, ""
    with open(bib_path, "r", encoding="utf-8") as f:
        db = bibtexparser.load(f)
    doi = doi.lower().strip()
    for e in db.entries:
        if (e.get("doi") or "").lower().strip() == doi:
            fval = e.get("file")
            if fval:
                bases = list(get_linked_pdf_basenames(bib_path))
                for b in bases:
                    return True, b
            return True, ""
    return False, ""
