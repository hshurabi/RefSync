import os
import json

TRACKER_FILENAME = ".refsync-tracker.json"

def _tracker_path(folder_path: str) -> str:
    return os.path.join(folder_path, TRACKER_FILENAME)

def load_tracker(folder_path: str) -> dict:
    path = _tracker_path(folder_path)
    # LEGACY support: read old .bibsync-tracker.json if present
    legacy = os.path.join(folder_path, ".bibsync-tracker.json")
    if not os.path.exists(path) and os.path.exists(legacy):
        path = legacy
    if not os.path.exists(path):
        return {"processed": [], "hashes": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"processed": [], "hashes": {}}

def save_tracker(folder_path: str, data: dict):
    path = _tracker_path(folder_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def mark_processed(folder_path: str, pdf_basename: str):
    data = load_tracker(folder_path)
    b = pdf_basename.lower()
    if b not in [x.lower() for x in data.get("processed", [])]:
        data.setdefault("processed", []).append(pdf_basename)
        save_tracker(folder_path, data)

def is_tracked(folder_path: str, pdf_basename: str) -> bool:
    data = load_tracker(folder_path)
    return pdf_basename.lower() in [x.lower() for x in data.get("processed", [])]

def mark_hash(folder_path: str, pdf_hash: str, pdf_basename: str):
    data = load_tracker(folder_path)
    data.setdefault("hashes", {})
    data["hashes"][pdf_hash] = pdf_basename
    save_tracker(folder_path, data)

def seen_hash(folder_path: str, pdf_hash: str) -> bool:
    data = load_tracker(folder_path)
    return pdf_hash in data.get("hashes", {})
