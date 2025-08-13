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

def quarantine_file(src_path: str, duplicates_dir: str) -> str:
    ensure_dir(uplicates_dir := duplicates_dir)
    base = os.path.basename(src_path)
    dst = os.path.join(duplicates_dir, base)
    if os.path.abspath(src_path) == os.path.abspath(dst):
        return dst
    if os.path.exists(dst):
        i = 2
        name, ext = os.path.splitext(base)
        while True:
            cand = os.path.join(duplicates_dir, f"{name}_{i}{ext}")
            if not os.path.exists(cand):
                dst = cand
                break
            i += 1
    import shutil
    shutil.move(src_path, dst)
    return dst
