#!/usr/bin/env python3
"""Back up DOCX files from a folder before review mutation."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing DOCX files")
    parser.add_argument("--out-dir", type=Path, help="Backup folder to create")
    parser.add_argument("--recursive", action="store_true", help="Include subfolders")
    args = parser.parse_args()

    source = args.folder.expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"Not a folder: {source}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = (args.out_dir or source / f"docx-backup-{stamp}").expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=False)

    pattern = "**/*.docx" if args.recursive else "*.docx"
    copied = []
    for docx in sorted(source.glob(pattern)):
        if docx.is_file() and not docx.name.startswith("~$"):
            rel = docx.relative_to(source)
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(docx, dest)
            copied.append(str(rel))

    print(f"backup_dir={out_dir}")
    print(f"copied={len(copied)}")
    for item in copied:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
