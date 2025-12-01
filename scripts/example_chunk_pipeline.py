from __future__ import annotations

import argparse
from pathlib import Path

from alfred.services.chunking import ChunkingService
from alfred.services.text_cleaning import TextCleaningService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean and chunk a markdown document")
    parser.add_argument("path", type=Path, help="Path to the markdown or text file")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=500,
        help="Approximate max tokens (words) per chunk",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=100,
        help="Approximate number of overlapping words between chunks",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.path.exists():
        raise SystemExit(f"File not found: {args.path}")

    raw_text = args.path.read_text(encoding="utf-8")
    cleaner = TextCleaningService()
    cleaned_text = cleaner.clean(raw_text)

    chunk_service = ChunkingService()
    chunks = chunk_service.chunk(
        cleaned_text,
        max_tokens=args.max_tokens,
        overlap=args.overlap,
    )

    if not chunks:
        print("No chunks generated")
        return

    print(f"Generated {len(chunks)} chunks from {args.path}")
    for chunk in chunks:
        start, end = chunk.char_start, chunk.char_end
        length = (end - start) if (start is not None and end is not None) else len(chunk.text)
        preview = chunk.text.strip().replace("\n", " ")[:120]
        section = chunk.section or "-"
        print(
            f"[{chunk.idx}] section={section} words={chunk.tokens or len(chunk.text.split())} chars={length}"
        )
        print(f"    preview: {preview}")


if __name__ == "__main__":
    main()
