# refsync/core.py
import os
from .config import BIB_FILENAME
from .metadata_extraction import read_pdf_metadata, guess_title_from_first_page
from .crossref_client import (
    best_crossref_match, bibtex_from_doi,
    first_author_lastname, year_from_item, words_of_title
)
from .bib_utils import (
    parse_bibtex_to_entry, upsert_bib_entry, safe_bib_key,
    add_or_update_file_field, get_linked_pdf_basenames, bib_has_doi_with_file
)
from .file_utils import rename_pdf, build_unique_stem
from .tracker import load_tracker, save_tracker, is_tracked, mark_processed, mark_hash, seen_hash
from .dedupe import compute_pdf_hash, quarantine_file


def process_pdf(pdf_path: str, bib_path: str, dry_run=False, verbose=False,
                dedupe_mode: str = 'quarantine', duplicates_dir: str = '_duplicates', skipped_dir: str = '_skipped'):
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
            quarantine_file(pdf_path, os.path.join(os.path.dirname(pdf_path), duplicates_dir))
            return
        # 'replace' falls through (not implemented yet)

    # Metadata & lookup
    title_md, author_md, first_page = read_pdf_metadata(pdf_path)
    candidate_title = title_md or guess_title_from_first_page(first_page)
    candidate_author = author_md

    if not candidate_title:
        if verbose:
            print("  Could not guess a title; moving to skipped folder.")
        if not dry_run:
            # reuse the same move helper we use for duplicates
            from .dedupe import quarantine_file
            target_dir = os.path.join(os.path.dirname(pdf_path), skipped_dir)
            quarantine_file(pdf_path, target_dir)
        return

    item = best_crossref_match(candidate_title, candidate_author)
    if not item:
        if verbose: print("  No Crossref match; skipping.")
        return

    doi = item.get("DOI")
    if not doi:
        if verbose: print("  No DOI; skipping.")
        return

    # DOI-based dedupe
    has_doi, linked_base = bib_has_doi_with_file(bib_path, doi)
    if has_doi and linked_base:
        if verbose:
            print(f"  [dup] DOI already in bib with linked file: {linked_base}")
        if dedupe_mode == 'skip':
            return
        elif dedupe_mode == 'quarantine' and not dry_run:
            quarantine_file(pdf_path, os.path.join(os.path.dirname(pdf_path), duplicates_dir))
            return

    bib_str = bibtex_from_doi(doi)
    entry = parse_bibtex_to_entry(bib_str)
    if not entry:
        if verbose: print("  Failed to parse BibTeX; skipping.")
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

    # Bib entry ID + file link
    if "ID" not in entry or not entry["ID"]:
        entry["ID"] = safe_bib_key(entry)
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
