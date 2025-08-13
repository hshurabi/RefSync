# RefSync

**RefSync** organizes your scholarly PDFs and BibTeX library automatically:

- Renames PDFs to a clean, predictable format:
  ```
  <LastName><YYYY><FirstWord[+SecondWord[+Third...]]>.pdf
  ```
  (expands title words to avoid collisions; removes repeated consecutive words like “Deep Deep”.)
- Looks up canonical metadata via **Crossref** → DOI → clean **BibTeX**.
- Adds a JabRef-friendly `file = {}` field so your reference manager can open the PDF directly.
- Skips items you’ve already curated (linked in `.bib`) and remembers what it processed with a tracker file.
- Dedupe logic catches both **exact-file duplicates** and **same-paper duplicates** (same DOI).

---

## Table of Contents

- [Features](#features)  
- [Installation](#installation)  
- [Quick Start](#quick-start)  
- [How It Works](#how-it-works)  
- [Naming & Collision Rules](#naming--collision-rules)  
- [Skip & Tracker Logic](#skip--tracker-logic)  
- [Duplicate PDFs (Hash & DOI)](#duplicate-pdfs-hash--doi)  
- [JabRef Integration](#jabref-integration)  
- [Configuration](#configuration)  
- [CLI Reference](#cli-reference)  
- [Examples](#examples)  
- [Development](#development)  
- [Roadmap](#roadmap)  
- [License](#license)

---

## Features

- 🔍 **Metadata retrieval** via Crossref (DOI → BibTeX).
- ✏️ **Smart renaming** with multi-word stems to avoid same-name collisions.
- 📑 **BibTeX upsert** into a per-folder library (default `library.bib`).
- 🔗 **JabRef `file` field** linking to the local PDF.
- 🧭 **Skips curated entries** already linked in the `.bib`.
- 🧾 **Tracker file** to remember processed PDFs per folder.
- 🧹 **Duplicate handling**:
  - **Hash-based**: same file content → skip/quarantine.
  - **DOI-based**: same paper already in `.bib` with a file link → skip/quarantine.
- 🧠 Optional **GROBID** integration for messy PDFs.

---

## Installation

```bash
git clone https://github.com/hshurabi/RefSync.git
cd refsync
pip install -e .
```

Requires **Python 3.9+**.  
Dependencies are managed via `pyproject.toml`.

---

## Quick Start

```bash
# Process a folder containing PDFs
refsync /path/to/pdf/folder --verbose

# Preview changes only
refsync /path/to/pdf/folder --dry-run

# Use a custom bib filename
refsync /path/to/pdf/folder --bib mylibrary.bib
```

**First-time tip:** Build the tracker from your current `.bib` links, then process new files:
```bash
refsync /path/to/pdf/folder --rebuild-tracker --verbose
refsync /path/to/pdf/folder --verbose
```

---

## How It Works

1. **Scan PDFs** in the target folder.  
2. **Skip** PDFs already linked in the `.bib`, then skip anything listed in the tracker.  
3. **Compute hash** → if seen, treat as duplicate (policy).  
4. Extract a **candidate title/author** from PDF metadata/first page and query **Crossref**.  
5. If DOI found → fetch **clean BibTeX** (content negotiation).  
6. **Build a unique filename stem** `<LastName><Year><FirstWord[+Second...]>`.  
7. **Rename** the PDF and **upsert** the BibTeX (with `file={:relative/path:PDF}`).
8. **Record** the file’s hash and basename in the tracker.

---

## Naming & Collision Rules

- Base convention:  
  ```
  <LastName><YYYY><FirstWord>.pdf
  ```
- If that **collides**, we extend to two words, then three, up to 6 words:
  ```
  <LastName><YYYY><FirstWord><SecondWord><ThirdWord>...
  ```
- **Consecutive duplicates** in titles are removed (e.g., “Deep Deep Learning” → `Deep Learning`).  
- Filenames are **sanitized** (alphanumeric only).  
- If still colliding after 6 words, a numeric suffix (`_2`, `_3`, …) is appended.

> This strategy avoids ambiguous filenames like `Smith2021Deep.pdf` when there are multiple “Deep …” papers in the same year.

---

## Skip & Tracker Logic

Per folder, RefSync uses two layers to avoid touching curated entries:

1. **Skip if already linked in the `.bib`** (`file` field exists for that PDF basename).  
2. **Skip if listed in the tracker**:  
   - Tracker file: `.refsync-tracker.json` (created/updated automatically).  
   - Backward-compatible: will read old `.refsync-tracker.json` if present.  
   - Stores processed basenames and content hashes.  

**Helpful commands:**
```bash
# Rebuild tracker from current bib links and exit
refsync /path --rebuild-tracker

# Ignore tracker (but still skip bib-linked items)
refsync /path --no-tracker
```

---

## Duplicate PDFs (Hash & DOI)

It’s common to download the same paper from multiple sources (publisher, arXiv, author site). RefSync prevents duplicate clutter:

- **Hash-based:** If the **SHA-256** of a PDF matches a previously seen file in this folder, it’s the same file → follow dedupe policy.
- **DOI-based:** If the DOI already exists in your `.bib` **with a linked file**, the new PDF is treated as a duplicate copy.

**Policies:**
```bash
# Default: quarantine duplicates to ./_duplicates
refsync /path --dedupe quarantine

# Skip duplicates entirely
refsync /path --dedupe skip

# Choose a custom quarantine folder name
refsync /path --dedupe quarantine --duplicates-dir "DUPLICATES_BIN"
```

> `--dedupe replace` is reserved for a future “replace-with-better-copy” heuristic (page count, text OCR, publisher version, etc.).

---

## JabRef Integration

- Open the generated/updated **`library.bib`** in JabRef.
- In JabRef: `Options → Preferences → Linked Files` → use **relative paths**.
- Each entry includes a `file` field:
  ```
  file = {:relative/path/to/Paper.pdf:PDF}
  ```
- Double-clicking the entry opens the linked PDF.

---

## Configuration

Edit `refsync/config.py`:

```python
BIB_FILENAME = "library.bib"

# GROBID (optional; improves metadata for messy PDFs)
USE_GROBID = False
GROBID_URL = "http://localhost:8070/api/processHeaderDocument"

# HTTP headers / endpoints
USER_AGENT = "refsync/0.1 (mailto:you@example.com)"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
DOI_CONTENT_NEGOTIATION_URL = "https://doi.org/{doi}"
```

To use GROBID, run it locally (Docker) and set `USE_GROBID = True`.

---

## CLI Reference

```bash
refsync PATH [options]

Positional:
  PATH                     Folder to process (contains PDFs)

Options:
  --bib FILE               Bib file name (default: library.bib)
  --dry-run                Preview actions; no writes
  --verbose                Verbose logs

  --no-tracker             Disable tracker (still skips bib-linked entries)
  --rebuild-tracker        Rebuild tracker from current bib links, then exit

  --dedupe {skip,quarantine,replace}
                           Duplicate policy (default: quarantine)
  --duplicates-dir NAME    Folder for quarantined duplicates (default: _duplicates)

  --skipped-dir NAME       Folder for skipped files (default: _skipped)
```

---

## Examples

**Before**
```
paper123.pdf
another_paper_final_version.pdf
library.bib
```

**After**
```
Smith2021DeepLearning.pdf
Garcia2020Bayesian.pdf
library.bib
.refsync-tracker.json
_duplicates/  (if duplicates were quarantined)
_skipped/ (if any error occured files moved here)
```

Example entry:
```bibtex
@article{Smith2021DeepLearning,
  title={Deep Learning for X},
  author={Smith, John and Doe, Jane},
  year={2021},
  doi={10.xxxx/yyyy},
  file={:Smith2021DeepLearning.pdf:PDF}
}
```

---

## Development

```bash
pip install -r requirements.txt
pytest
```

Key modules:
- `core.py` – orchestrates folder/PDF processing.
- `crossref_client.py` – Crossref queries, title tokenization.
- `metadata_extraction.py` – PDF metadata + first-page heuristics.
- `bib_utils.py` – BibTeX parsing/upsert, linked-file detection.
- `file_utils.py` – Renaming, unique stem builder.
- `tracker.py` – Per-folder processed list + content hashes.
- `dedupe.py` – Hashing/quarantine helpers.

---

## Roadmap

- Semantic Scholar fallback (API) for resiliency.  
- “Replace with better copy” policy (publisher PDF, OCR quality, page count).  
- Parallel processing for large folders.  
- Optional multi-file linking (keep both arXiv + publisher in `file` separated by `;`).  
- GUI wrapper for non-technical users.

---

## License

MIT – see [LICENSE](LICENSE).
