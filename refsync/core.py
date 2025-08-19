# refsync/core.py
import os
from turtle import title
from .config import BIB_FILENAME
from .metadata_extraction import read_pdf_metadata, guess_title_from_first_page, title_from_filename
from .ref_client import (
    best_metadata_match, bibtex_from_doi,
    first_author_lastname, year_from_item, words_of_title, needs_title_case_fix, fix_title_case
)
from .bib_utils import (
    parse_bibtex_to_entry, upsert_bib_entry, safe_bib_key,
    add_or_update_file_field, get_linked_pdf_basenames, bib_has_doi_with_file
)
from .file_utils import rename_pdf, build_unique_stem
from .tracker import load_tracker, save_tracker, is_tracked, mark_processed, mark_hash, seen_hash
from .dedupe import compute_pdf_hash, quarantine_file, ensure_dir


def process_pdf(pdf_path: str, bib_path: str, dry_run=False, verbose=False,
                dedupe_mode: str = 'quarantine', duplicates_dir: str = '_duplicates', skipped_dir: str = '_skipped'):
    def _move_to_skipped() -> None:
        if verbose:
            print("  Moving to skipped folder.")
        if not dry_run:
            target_dir = os.path.join(os.path.dirname(pdf_path), skipped_dir)
            ensure_dir(target_dir)
            quarantine_file(pdf_path, target_dir)  # keeps original basename, avoids overwrite

    if verbose:
        print(f"[PDF] {pdf_path}")

    # Hash-based dedupe
    h = compute_pdf_hash(pdf_path)
    if seen_hash(os.path.dirname(pdf_path), h):
        if verbose:
            print("  [dup] Same file hash seen before.")
        if dedupe_mode == 'skip':
            return
        elif dedupe_mode == 'quarantine' and not dry_run:
            dup_dir = os.path.join(os.path.dirname(pdf_path), duplicates_dir)
            # Use the original processed basename from tracker (already in your structured format)
            data = load_tracker(os.path.dirname(pdf_path))
            desired = (data.get("hashes", {}) or {}).get(h)  # e.g., "Smith2021DeepLearning.pdf"
            quarantine_file(pdf_path, dup_dir, new_basename=desired)
            return

    def _is_plausible_title(title: str) -> bool:
        # Heuristic: at least 5 words, not all caps, not mostly digits, not too short
        words = title.split()
        return (
            len(words) >= 5 and
            not title.isupper() and
            sum(c.isdigit() for c in title) < 5 and
            sum(c.isalpha() for c in title) > 10
        )

    # Metadata & lookup
    candidate_title, candidate_author, first_page = read_pdf_metadata(pdf_path)
    found_match = False
    if _is_plausible_title(candidate_title):
        item = best_metadata_match(candidate_title, candidate_author)
        if item and item.get("_title_match_flag"):
            found_match = True
    else:
        candidate_title = title_from_filename(pdf_path)
        if _is_plausible_title(candidate_title):
            item = best_metadata_match(candidate_title, candidate_author)
            if item and item.get("_title_match_flag"):
                found_match = True
        else:
            candidate_title = None

    if not found_match:
        lines = [line.strip() for line in first_page.split('\n') if line.strip()]
        max_lines = min(10, len(lines))
        for start in range(max_lines):
            # Try with just this line
            title_try = lines[start]
            words = title_try.split()
            if (len(words) >= 4 and
                sum(c.isdigit() for c in title_try) < 5 and
                sum(c.isalpha() for c in title_try) > 10 and
                not any(w.lower() in ["copyright", "doi"] for w in words[:3])
                ):
                item = best_metadata_match(title_try, candidate_author)
                if item and item.get("_title_match_flag"):
                    candidate_title = title_try
                    found_match = True
                    break
                elif item and not item.get("_title_match_flag"):
                    # Try with next line added
                    if start + 1 < len(lines):
                        combined_title = title_try + " " + lines[start + 1]
                        item2 = best_metadata_match(combined_title, candidate_author)
                        if item2 and item2.get("_title_match_flag"):
                            candidate_title = combined_title
                            item = item2
                            found_match = True
                            break
                        elif item2 and not item2.get("_title_match_flag"):
                            # Try with next line added
                            if start + 1 < len(lines):
                                combined_title = combined_title + " " + lines[start + 1]
                                item3 = best_metadata_match(combined_title, candidate_author)
                                if item3 and item3.get("_title_match_flag"):
                                    candidate_title = combined_title
                                    item = item3
                                    found_match = True
                                    break

        
    if not found_match:
        if verbose:
            print("  Could not guess a plausible title with good Crossref match; moving to skipped folder.")
        _move_to_skipped()
        return

    if not candidate_title:
        if verbose:
            print("  Could not guess a title; moving to skipped folder.")
        _move_to_skipped()
        return

    doi = item.get("DOI")
    if not doi:
        if verbose: print("  No DOI; building BibTeX from metadata.")
        # Build BibTeX entry from item metadata
        entry = {
            "ID": safe_bib_key(item),
            "ENTRYTYPE": "article",
            "title": item.get("title", [""])[0] if item.get("title") else "",
            "author": " and ".join(
                [f"{a.get('family','')}, {a.get('given','')}".strip(", ") for a in item.get("author", []) if a]
            ),
            "year": year_from_item(item) or item.get("year", ""),
            "file": os.path.basename(pdf_path),
            "_title_match_flag": "true" if item.get("_title_match_flag") else "false",
            "_manual_entry_flag": "true"
        }
    else:
        bib_str = bibtex_from_doi(doi)
        entry = parse_bibtex_to_entry(bib_str)
        if not entry:
            if verbose: print("  Failed to parse BibTeX; skipping.")
            _move_to_skipped()
            return
    
    # Fix uppercased titles
    if entry and entry.get("title", "") and needs_title_case_fix(entry["title"]):
        entry["title"] = fix_title_case(entry["title"])
    # dedupe
    dup_flag = False
    has_doi, linked_base = bib_has_doi_with_file(bib_path, doi)
    if has_doi and linked_base:
        if verbose:
            print(f"  [dup] DOI already in bib with linked file: {linked_base}")
            dup_flag = True
    elif linked_base:
        # Check for existing entry with same title and author
        with open(bib_path, "r", encoding="utf-8") as f:
            bib_content = f.read()
        # Parse all entries
        entries = [parse_bibtex_to_entry(e) for e in bib_content.split("@") if e.strip()]
        for e in entries:
            if (
                e.get("title", "").strip().lower() == entry.get("title", "").strip().lower() and
                e.get("author", "").strip().lower() == entry.get("author", "").strip().lower()
            ):
                if verbose:
                    print(f"  [debug] Title+author already in bib: {e.get('ID', '')}")
                    dup_flag = True
    if dup_flag and dedupe_mode == 'quarantine' and not dry_run:
        dup_dir = os.path.join(os.path.dirname(pdf_path), duplicates_dir)
        ensure_dir(dup_dir)  # so we can check existing stems in that folder

        # Build a structured stem from Crossref metadata for the duplicate
        flast = first_author_lastname(item) or "Unknown"
        y = year_from_item(item) or ""
        twords = words_of_title(item) or ["Untitled"]

        # Build a unique stem *within the duplicates folder*
        stem = build_unique_stem(dup_dir, (flast, y), twords)

        # Move+rename to something like Smith2021DeepLearning.pdf under _duplicates/
        quarantine_file(pdf_path, dup_dir, new_basename=stem + ".pdf")
        return
    

    # Ensure key fields
    if "year" not in entry or not entry["year"]:
        entry["year"] = year_from_item(item) or ""
    if "author" not in entry or not entry["author"]:
        authors = item.get("author") or []
        entry["author"] = " and ".join(
            [f"{a.get('family','')}, {a.get('given','')}".strip(", ") for a in authors if a]
        )

    # Unique stem using title words (with duplicate-word cleanup done upstream)
    flast = first_author_lastname(item) or "Unknown"
    y = entry.get("year", "") or year_from_item(item) or ""
    twords = words_of_title(item) or ["Untitled"]
    stem = build_unique_stem(os.path.dirname(pdf_path), (flast, y), twords)
    new_pdf_path, key_stem = rename_pdf(pdf_path, (stem, "", ""), dry_run=dry_run)

    
    # Always same structure for bibtex key
    # if "ID" not in entry or not entry["ID"]:
    entry["ID"] = key_stem
    # Bib file link
    rel_path = os.path.relpath(new_pdf_path, os.path.dirname(bib_path))
    add_or_update_file_field(entry, rel_path)

    upsert_bib_entry(bib_path, entry, dry_run=dry_run)

    if not dry_run:
        mark_hash(os.path.dirname(pdf_path), h, os.path.basename(new_pdf_path))

    if verbose:
        action = "(dry-run) " if dry_run else ""
        print(f"  {action}Renamed -> {os.path.basename(new_pdf_path)}")
        print(f"  {action}Updated {os.path.basename(bib_path)} with key {entry['ID']}")


def process_folder(folder_path: str, bib_filename: str = BIB_FILENAME, dry_run=False, verbose=False,
                   use_tracker: bool = True, rebuild_tracker: bool = False,
                   dedupe_mode: str = 'quarantine', duplicates_dir: str = '_duplicates', skipped_dir: str = '_skipped'):
    print(f"Processing folder: {folder_path}")  # Add this line
    bib_path = os.path.join(folder_path, bib_filename)
    linked = get_linked_pdf_basenames(bib_path)

    if rebuild_tracker:
        processed = []
        for name in sorted(os.listdir(folder_path)):
            if name.lower().endswith('.pdf') and name.lower() in linked:
                processed.append(name)
        save_tracker(folder_path, {"processed": processed, "hashes": {}})
        if verbose:
            print(f"[tracker] Rebuilt with {len(processed)} entries from BibTeX links.")
        return

    for name in sorted(os.listdir(folder_path)):
        if not name.lower().endswith('.pdf'):
            continue
        if name.lower() in linked:
            if verbose:
                print(f"[skip] Already linked in {bib_filename}: {name}")
            continue
        if use_tracker and is_tracked(folder_path, name):
            if verbose:
                print(f"[skip] Listed in tracker: {name}")
            continue

        pdf_path = os.path.join(folder_path, name)
        try:
            process_pdf(pdf_path, bib_path, dry_run=dry_run, verbose=verbose,
                        dedupe_mode=dedupe_mode, duplicates_dir=duplicates_dir, skipped_dir=skipped_dir)
            if use_tracker and not dry_run:
                mark_processed(folder_path, name)
        except Exception as e:
            print(f"  !! Error on {pdf_path}: {e}")
