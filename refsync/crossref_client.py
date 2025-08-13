import json
from tenacity import retry, stop_after_attempt, wait_exponential
import requests
from .config import CROSSREF_WORKS_URL, DOI_CONTENT_NEGOTIATION_URL, USER_AGENT

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def crossref_query(bibliographic: str, rows: int = 5) -> dict:
    r = SESSION.get(CROSSREF_WORKS_URL, params={"query.bibliographic": bibliographic, "rows": rows}, timeout=20)
    r.raise_for_status()
    return r.json()

def _score_item(it: dict, candidate_title: str, candidate_author: str) -> int:
    t = " ".join(it.get("title") or []).lower()
    s = 0
    for w in set(candidate_title.lower().split()):
        if len(w) > 3 and w in t:
            s += 1
    if candidate_author and (candidate_author.lower() in json.dumps(it.get("author", [])).lower()):
        s += 1
    return s

def best_crossref_match(candidate_title: str, candidate_author: str = "") -> dict | None:
    q = f"{candidate_title} {candidate_author}".strip()
    data = crossref_query(q, rows=5)
    items = data.get("message", {}).get("items", [])
    items.sort(key=lambda it: _score_item(it, candidate_title, candidate_author), reverse=True)
    return items[0] if items else None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def bibtex_from_doi(doi: str) -> str:
    url = DOI_CONTENT_NEGOTIATION_URL.format(doi=doi)
    headers = {"Accept": "application/x-bibtex"}
    r = SESSION.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.text

def first_author_lastname(item: dict) -> str:
    authors = item.get("author") or []
    if not authors:
        return ""
    fa = authors[0]
    return (fa.get("family") or fa.get("name") or "").replace("-", "")

def year_from_item(item: dict) -> str:
    for k in ("published-print", "published-online", "issued"):
        v = item.get(k)
        if v and v.get("date-parts"):
            return str(v["date-parts"][0][0])
    return ""

def first_word_of_title(item: dict) -> str:
    titles = item.get("title") or []
    if not titles:
        return ""
    t = titles[0]
    import re
    w = re.sub(r"[^A-Za-z0-9]+", " ", t).strip().split()
    return (w[0] if w else "")

def _clean_title_words(t: str) -> list[str]:
    import re
    # keep alnum words, strip punctuation, title-case the first letter
    words = re.sub(r"[^A-Za-z0-9]+", " ", t).strip().split()
    # remove consecutive duplicates (Deep Deep Learning -> Deep Learning)
    cleaned = []
    prev = None
    for w in words:
        if prev is None or w.lower() != prev.lower():
            cleaned.append(w)
            prev = w
    return cleaned

def words_of_title(item: dict) -> list[str]:
    titles = item.get("title") or []
    if not titles:
        return []
    t = titles[0]
    return _clean_title_words(t)
