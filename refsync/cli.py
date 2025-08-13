import argparse
from .core import process_folder

def build_parser():
    p = argparse.ArgumentParser(description="Rename PDFs and sync BibTeX (JabRef-friendly).")
    p.add_argument("path", help="Path to folder containing PDFs")
    p.add_argument("--bib", default="library.bib", help="Bib file name to create/update (default: library.bib)")
    p.add_argument("--dry-run", action="store_true", help="Preview actions without writing changes")
    p.add_argument("--verbose", action="store_true", help="Verbose output")
    return p

def main():
    args = build_parser().parse_args()
    process_folder(args.path, bib_filename=args.bib, dry_run=args.dry_run, verbose=args.verbose)

if __name__ == "__main__":
    main()
