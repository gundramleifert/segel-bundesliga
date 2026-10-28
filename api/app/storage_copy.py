"""Copy every upload between the configured store and a directory (`app/storage.py`).

    uv run python -m app.storage_copy export /backup/uploads   # store -> directory
    uv run python -m app.storage_copy import /old/uploads      # directory -> store

The configured store is whatever ``SBL_STORAGE`` and the ``SBL_S3_*`` settings say. So:

* **From the disk to S3** — ``import`` the old ``SBL_UPLOADS_DIR`` with ``SBL_STORAGE=s3``.
* **From one S3 provider to another** — ``export`` with the old provider's settings,
  ``import`` the same directory with the new one's.
* **A backup of every upload** — ``export``; restoring it is ``import``.

A directory holds the files under their keys (``clubs/3.png``), which is exactly what
``SBL_STORAGE=local`` keeps, so either side can also be a live uploads directory.
"""

from __future__ import annotations

import argparse
import sys

from app.storage import LocalStorage, copy_all, storage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.storage_copy", description=__doc__.split("\n")[0]
    )
    parser.add_argument(
        "direction",
        choices=["export", "import"],
        help="export: store -> directory, import: directory -> store",
    )
    parser.add_argument("directory")
    args = parser.parse_args(argv)
    directory = LocalStorage(args.directory)
    if args.direction == "export":
        count = copy_all(storage(), directory)
    else:
        if not directory.root.is_dir():
            parser.error(f"{args.directory} is not a directory")
        count = copy_all(directory, storage())
    print(f"{args.direction}: {count} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
