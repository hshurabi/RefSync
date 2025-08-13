# Usage (extended)

- Install locally with `pip install -e .`
- Run: `refsync /path/to/folder --verbose`
- See CLI flags via `refsync -h`



## Tracker mode

- Default: uses `.refsync-tracker.json` to remember processed PDFs.

- Skip logic:

  1) If a PDF is already linked in the bib's `file` field → **skip**.

  2) Else if it appears in tracker → **skip**.

  3) Otherwise → process and add to tracker.



Commands:

```bash
# Rebuild tracker solely from bib links and exit
refsync /path/to/folder --rebuild-tracker --verbose

# Process while ignoring tracker (but still skip already-linked entries)
refsync /path/to/folder --no-tracker --verbose
```


### Duplicate sources of the same paper
refsync tackles duplicates in two ways:
1) **Hash-based**: exact same file → deduped by SHA256.
2) **DOI-based**: same paper (same DOI) already in your bib with a linked file → duplicate quarantined/skipped.

Use:
```bash
# Default: quarantine duplicate copies into ./_duplicates
refsync /path --dedupe quarantine

# Skip duplicates entirely
refsync /path --dedupe skip

# Choose a custom quarantine folder
refsync /path --dedupe quarantine --duplicates-dir "DUPLICATES"
```
