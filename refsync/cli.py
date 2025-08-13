# refsync/cli.py
import argparse
from .core import process_folder

def build_parser():
    p = argparse.ArgumentParser(
        description="Rename PDFs and sync BibTeX (JabRef-friendly)."
    )
    # Path is optional; default = current directory
    p.add_argument("path", nargs="?", default=".", help="Folder to process (default: current directory)")
    p.add_argument("--bib", default="library.bib", help="Bib file name to create/update (default: library.bib)")
    p.add_argument("--dry-run", action="store_true", help="Preview actions without writing changes")
    p.add_argument("--verbose", action="store_true", help="Verbose output")
    # Tracker controls
    p.add_argument("--no-tracker", action="store_true", help="Disable tracker; process all PDFs not linked in bib")
    p.add_argument("--rebuild-tracker", action="store_true", help="Rebuild tracker from existing BibTeX links and exit")
    # Duplicate handling
    p.add_argument("--dedupe", choices=["skip", "quarantine", "replace"],
                   default="quarantine", help="How to handle duplicate PDFs (default: quarantine)")
    p.add_argument("--duplicates-dir", default="_duplicates", help="Folder name for quarantined duplicates (default: _duplicates)")
    # Skipped PDFs
    p.add_argument("--skipped-dir", default="_skipped", help="Folder name for PDFs skipped due to missing title (default: _skipped)")

    return p

def main():
    args = build_parser().parse_args()
    process_folder(
        args.path,
        bib_filename=args.bib,
        dry_run=args.dry_run,
        verbose=args.verbose,
        use_tracker=not args.no_tracker,
        rebuild_tracker=args.rebuild_tracker,
        dedupe_mode=args.dedupe,
        duplicates_dir=args.duplicates_dir,
        skipped_dir=args.skipped_dir
    )

if __name__ == "__main__":
    main()
