import json
from tenacity import retry, stop_after_attempt, wait_exponential
import requests
from .config import CROSSREF_WORKS_URL, DOI_CONTENT_NEGOTIATION_URL, USER_AGENT, SEMANTIC_SCHOLAR_URL, OPENALEX_URL
import re
import time

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})
_crossref_cache = {}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def crossref_query(bibliographic: str, rows: int = 5) -> dict:
    resp = SESSION.get(CROSSREF_WORKS_URL, params={"query.bibliographic": bibliographic, "rows": rows}, timeout=20)
    resp.raise_for_status()
    return resp.json()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=10))
def semantic_scholar_query(title: str, limit: int = 1):
    params = {
        "query": title.strip(),
        "fields": "title,authors,year,externalIds,url",
        "limit": limit
    }
    headers = {"Accept": "application/json"}
    time.sleep(1)
    resp = SESSION.get(SEMANTIC_SCHOLAR_URL, params=params, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    return []

def openalex_query(title: str, limit: int = 1):
    params = {
        "search": title,
        "per-page": limit
    }
    resp = SESSION.get(OPENALEX_URL, params=params)
    if resp.status_code == 200:
        return resp.json().get("results", [])
    return []

def _score_item(it: dict, candidate_title: str, candidate_author: str) -> int:
    t = " ".join(it.get("title") or []).lower()
    s = 0
    for w in set(candidate_title.lower().split()):
        if len(w) > 3 and w in t:
            s += 1
    if candidate_author and (candidate_author.lower() in json.dumps(it.get("author", [])).lower()):
        s += 1
    return s

def normalize_title(title: str) -> str:
    ligatures = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "ﬅ": "ft",
        "ﬆ": "st"
    }
    for lig, repl in ligatures.items():
        title = title.replace(lig, repl)
    # Lowercase, remove punctuation, collapse whitespace
    return re.sub(r'\W+', ' ', title.lower()).strip()

def normalize_semantic_item(item: dict) -> dict:
    """Convert Semantic Scholar item to Crossref-like format (fields as lists)."""
    norm = {}
    # Title as list
    title = item.get("title", "")
    norm["title"] = [title] if isinstance(title, str) else title
    # Authors as list of dicts with 'family' and 'given'
    authors = item.get("authors", [])
    norm["author"] = []
    for a in authors:
        name = a.get("name", "").strip()
        if name:
            parts = name.split()
            family = parts[-1]
            given = " ".join(parts[:-1]) if len(parts) > 1 else ""
            norm["author"].append({"family": family, "given": given})
        else:
            norm["author"].append({"family": "", "given": ""})
    # Year as string
    norm["year"] = str(item.get("year", ""))
    # DOI as string if present
    norm["DOI"] = item.get("externalIds", {}).get("DOI", "")
    # Add other fields as needed (url, etc.)
    norm["URL"] = item.get("url", "")
    return norm

def best_metadata_match(candidate_title: str, candidate_author: str = "") -> dict | None:
    normalized_candidate = normalize_title(candidate_title)
    candidate_words = normalized_candidate.split()
    q = f"{normalized_candidate} {candidate_author}".strip()

    
    # Use cache if available
    if q in _crossref_cache:
        crossref_data = _crossref_cache[q]
    else:
        # Get 3 from Crossref
        crossref_data = crossref_query(q, rows=3)
        _crossref_cache[q] = crossref_data

    items = crossref_data.get("message", {}).get("items", [])

    # Get 1 from Semantic Scholar
    semsch_items = semantic_scholar_query(normalized_candidate, limit=1)

    # Combine results
    if len(semsch_items) > 0:
        items =  items + [normalize_semantic_item(semsch_items[0])]
    items.sort(key=lambda it: _score_item(it, normalized_candidate, candidate_author), reverse=True)
    for item in items:
        crossref_title = item.get("title", [""])[0]
        normalized_crossref = normalize_title(crossref_title)
        if normalized_candidate == normalized_crossref:
            item["_title_match_flag"] = True
            return item  # return exact match
        crossref_words = normalized_crossref.split()
        m = min(len(candidate_words), len(crossref_words))
        if m == 0:
            continue
        # Compare first m words in order
        if candidate_words[:m] == crossref_words[:m]:
            item["_title_match_flag"] = False
            return item
    return None

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

def _clean_title_words(t: str) -> list[str]:
    import re
    if needs_title_case_fix(t):
        t = fix_title_case(t)
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

def fix_title_case(title: str) -> str:
    words = title.split()
    if not words:
        return title
    # Capitalize first word, lowercase the rest
    return " ".join([words[0].capitalize()] + [w.lower() for w in words[1:]])
def needs_title_case_fix(title: str) -> bool:
    words = title.split()
    count_upper = sum(1 for w in words if w and w[0].isupper())
    return count_upper > 3