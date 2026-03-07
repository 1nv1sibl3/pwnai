#!/usr/bin/env python3
"""
Convert the shellphish/how2heap repository into a simple RAG-ready corpus.

For each source file, this script prepends:
- GLIBC version: derived from the parent folder name (e.g. glibc_2.27)
- Technique name: derived from the file name (e.g. house_of_storm.c -> house_of_storm)

Then it appends the exact original file contents unchanged.

Example output document for:
how2heap/glibc_2.27/house_of_storm.c

becomes:

GLIBC version: glibc_2.27
Technique name: house_of_storm

<exact original file contents>

Usage:
    python build_how2heap_rag.py /path/to/how2heap /path/to/output_corpus

Optional:
    python build_how2heap_rag.py /path/to/how2heap /path/to/output_corpus --jsonl rag_documents.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


TEXT_EXTENSIONS = {
    ".c",
    ".cpp",
    ".cc",
    ".h",
    ".hpp",
    ".txt",
    ".md",
    ".py",
    ".sh",
}


def is_candidate_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.startswith("."):
        return False
    return path.suffix.lower() in TEXT_EXTENSIONS


def find_glibc_version(path: Path, repo_root: Path) -> str:
    rel_parts = path.relative_to(repo_root).parts
    for part in rel_parts:
        if part.startswith("glibc_"):
            return part
    return "unknown"


def technique_name_from_file(path: Path) -> str:
    return path.stem


def build_document(glibc_version: str, technique_name: str, original_content: str) -> str:
    return (
        f"GLIBC version: {glibc_version}\n"
        f"Technique name: {technique_name}\n\n"
        f"{original_content}"
    )


def iter_source_files(repo_root: Path) -> Iterable[Path]:
    for path in repo_root.rglob("*"):
        if is_candidate_file(path):
            yield path


def convert_repo(repo_root: Path, output_root: Path, jsonl_path: Path | None = None) -> None:
    repo_root = repo_root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    jsonl_file = None
    if jsonl_path is not None:
        jsonl_path = jsonl_path.resolve()
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl_file = jsonl_path.open("w", encoding="utf-8")

    count = 0

    try:
        for src_path in iter_source_files(repo_root):
            rel_path = src_path.relative_to(repo_root)
            glibc_version = find_glibc_version(src_path, repo_root)
            technique_name = technique_name_from_file(src_path)

            original_content = src_path.read_text(encoding="utf-8", errors="replace")
            new_content = build_document(glibc_version, technique_name, original_content)

            out_path = output_root / rel_path.with_suffix(".txt")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(new_content, encoding="utf-8")

            if jsonl_file is not None:
                record = {
                    "id": str(rel_path.with_suffix("")),
                    "source_path": str(rel_path),
                    "glibc_version": glibc_version,
                    "technique_name": technique_name,
                    "content": new_content,
                }
                jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")

            count += 1

    finally:
        if jsonl_file is not None:
            jsonl_file.close()

    print(f"Converted {count} documents into: {output_root}")
    if jsonl_path is not None:
        print(f"JSONL written to: {jsonl_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert how2heap into a RAG-ready corpus with prepended metadata."
    )
    parser.add_argument("repo_root", type=Path, help="Path to the how2heap repository")
    parser.add_argument("output_root", type=Path, help="Path to output processed documents")
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Optional path to write a JSONL file containing all processed documents",
    )
    args = parser.parse_args()

    if not args.repo_root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {args.repo_root}")
    if not args.repo_root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {args.repo_root}")

    convert_repo(args.repo_root, args.output_root, args.jsonl)


if __name__ == "__main__":
    main()