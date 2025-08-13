import os
import re

def sanitize_stem(stem: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]", "", stem) or "unnamed"
    return stem

def rename_pdf(pdf_path: str, stem_components: tuple[str, str, str], dry_run=False) -> tuple[str, str]:
    parent = os.path.dirname(pdf_path)
    stem = "".join(stem_components).strip()
    stem = sanitize_stem(stem)
    new_name = stem + ".pdf"
    new_path = os.path.join(parent, new_name)

    if os.path.abspath(new_path) == os.path.abspath(pdf_path):
        return pdf_path, stem

    if os.path.exists(new_path):
        i = 2
        while True:
            alt = os.path.join(parent, f"{stem}_{i}.pdf")
            if not os.path.exists(alt):
                new_path = alt
                break
            i += 1

    if not dry_run:
        os.rename(pdf_path, new_path)

    return new_path, stem

def existing_pdf_stems(folder_path: str) -> set[str]:
    stems = set()
    for name in os.listdir(folder_path):
        if name.lower().endswith(".pdf"):
            stem, _ = os.path.splitext(name)
            stems.add(stem.lower())
    return stems

def build_unique_stem(folder_path: str, prefix_components: tuple[str, str], title_words: list[str], max_words: int = 6) -> str:
    """Try increasing number of title words until the stem is unique in the folder.
    prefix_components -> (LastName, Year)
    title_words -> cleaned, de-duplicated words from title
    """
    last, year = prefix_components
    words = [w for w in title_words if w] or ["Untitled"]
    existing = existing_pdf_stems(folder_path)
    # try 1..max_words words
    for k in range(1, min(max_words, len(words)) + 1):
        stem = sanitize_stem(f"{last}{year}{''.join(words[:k])}")
        if stem.lower() not in existing:
            return stem
    # if all collide, append an index-free version and let rename_pdf handle suffixing
    return sanitize_stem(f"{last}{year}{''.join(words[:max_words])}")
