# refsync/dedupe.py
import os
import hashlib
import shutil

def compute_pdf_hash(path: str, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def quarantine_file(src_path: str, duplicates_dir: str, new_basename: str | None = None) -> str:
    """
    Move src_path into duplicates_dir. If new_basename is provided, rename to that;
    otherwise keep the original basename. Avoid overwriting by appending _2, _3, ...
    Returns the final destination path.
    """
    ensure_dir(duplicates_dir)

    # Choose the target name
    base = new_basename if new_basename else os.path.basename(src_path)
    name, ext = os.path.splitext(base)
    if not ext:  # ensure it keeps its extension, default to .pdf
        ext = os.path.splitext(src_path)[1] or ".pdf"

    dst = os.path.join(duplicates_dir, name + ext)

    # Avoid overwriting collisions
    i = 2
    while os.path.exists(dst) and os.path.abspath(dst) != os.path.abspath(src_path):
        dst = os.path.join(duplicates_dir, f"{name}_{i}{ext}")
        i += 1

    shutil.move(src_path, dst)
    return dst
