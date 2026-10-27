"""Where uploaded files live: the local disk or an S3-compatible object store.

Every file the site keeps — crests, sailor photos, the media library, waiver scans,
receipts, personal documents — is a **key** like ``clubs/3.png`` or
``media/<name>-960.webp``, and goes through :func:`storage` and nothing else.
``SBL_STORAGE`` picks the backend: ``local`` (the default) writes under
``SBL_UPLOADS_DIR`` exactly as before, ``s3`` writes to ``SBL_S3_BUCKET`` at
``SBL_S3_ENDPOINT_URL`` (SeaweedFS in ``deploy/compose/``, any S3 elsewhere).

Both backends answer the same few questions, so a caller never knows which it has. Two
things differ underneath and are handled here, not at the callers:

* **Serving.** A local file is handed to ``FileResponse`` (ranges, ETag, streamed); an
  object is read and answered as bytes. The site's files are small — 10 MB at most — and
  every one of them is served through an endpoint that checks who asks, so the bytes
  pass through the API either way; there are no presigned links to a private file.
* **Asking whether a file exists is a network request on S3.** A club's crest is looked
  up on every serialized club (``ClubOut``), so the S3 backend keeps what it learned
  about each key — written, deleted, or asked — for ``SBL_S3_CACHE_SECONDS``. The API is
  one process (``app/live.py``), so its own writes are always current; the timeout only
  bounds how long a change made *outside* it goes unseen.

The calls are synchronous like the disk calls they replaced; a route that serves a file
does it through :func:`respond`, which runs them off the event loop.
"""

from __future__ import annotations

import asyncio
import threading
import time
from functools import cache
from pathlib import Path
from typing import NamedTuple, Protocol
from urllib.parse import quote

from fastapi.responses import FileResponse, Response

from app.config import StorageBackend, settings


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def exists(self, key: str) -> bool: ...
    def stamp(self, key: str) -> int | None:
        """When the file was last written, in whole seconds — ``None`` when there is none.
        A cache key for a URL that stays the same across replacements (a crest)."""
        ...

    def delete(self, key: str) -> None:
        """Deleting what is not there is not an error."""
        ...

    def keys(self, prefix: str) -> list[str]:
        """Every key starting with ``prefix``, sorted."""
        ...

    def response(
        self, key: str, media_type: str, headers: dict[str, str] | None = None
    ) -> Response | None:
        """The file as an HTTP response, or ``None`` when there is none."""
        ...


def valid_name(name: str | None) -> bool:
    """A stored name is one path segment — never a way out of its directory or prefix."""
    return bool(name) and "/" not in name and "\\" not in name and not name.startswith(".")


class LocalStorage:
    """Files under one directory — ``SBL_UPLOADS_DIR``, the key its relative path."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def stamp(self, key: str) -> int | None:
        path = self._path(key)
        return int(path.stat().st_mtime) if path.is_file() else None

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def keys(self, prefix: str) -> list[str]:
        # A plain string prefix, as S3 has it: `media` covers `media/…` and
        # `media-originals/…` alike. Only the directory the prefix names is walked.
        base = self.root / prefix.rpartition("/")[0]
        if not base.is_dir():
            return []
        found = (path.relative_to(self.root).as_posix() for path in base.rglob("*"))
        return sorted(key for key in found if key.startswith(prefix) and self.exists(key))

    def response(
        self, key: str, media_type: str, headers: dict[str, str] | None = None
    ) -> Response | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return FileResponse(path, media_type=media_type, headers=headers)


class _Known(NamedTuple):
    stamp: int | None  # None: the object is not there
    until: float


class S3Storage:
    """Objects in one bucket, the key prefixed with ``SBL_S3_PREFIX``."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key_id: str = "",
        secret_access_key: str = "",
        prefix: str = "",
        cache_seconds: float = 300,
        client=None,
    ) -> None:
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                region_name=region,
                aws_access_key_id=access_key_id or None,
                aws_secret_access_key=secret_access_key or None,
                # Path-style: SeaweedFS and MinIO answer at one host, not one per bucket.
                config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
            )
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        self.cache_seconds = cache_seconds
        self._known: dict[str, _Known] = {}
        self._lock = threading.Lock()
        self._bucket_ready = False
        self._bucket_lock = threading.Lock()

    def _key(self, key: str) -> str:
        return self.prefix + key

    def _remember(self, key: str, stamp: int | None) -> None:
        with self._lock:
            self._known[key] = _Known(stamp, time.monotonic() + self.cache_seconds)

    def _missing(self, error: Exception) -> bool:
        code = getattr(error, "response", {}).get("Error", {}).get("Code", "")
        return code in {"404", "NoSuchKey", "NotFound"}

    def ensure_bucket(self) -> None:
        """Creates the bucket on first use, so a fresh object store needs no setup step.

        Before *any* call, not only the first write: SeaweedFS (3.97) remembers a bucket it
        was asked about while it did not exist, and answers every later read with
        ``NoSuchBucket`` although the bucket was created since and writes to it succeed —
        so the first look for a crest on a fresh store would leave every upload unreadable.
        ``head_bucket`` does not leave that mark; ``head_object`` does."""
        if self._bucket_ready:
            return
        from botocore.exceptions import ClientError

        with self._bucket_lock:
            if self._bucket_ready:
                return
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError as error:
                if not self._missing(error) and "NoSuchBucket" not in str(error):
                    raise
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                except ClientError as taken:
                    # Another process (the init container) made it a moment ago.
                    code = taken.response.get("Error", {}).get("Code", "")
                    if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                        raise
            self._bucket_ready = True

    def put(self, key: str, data: bytes) -> None:
        self.ensure_bucket()
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data)
        self._remember(key, int(time.time()))

    def get(self, key: str) -> bytes | None:
        from botocore.exceptions import ClientError

        self.ensure_bucket()
        try:
            answer = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        except ClientError as error:
            if self._missing(error) or "NoSuchBucket" in str(error):
                self._remember(key, None)
                return None
            raise
        return answer["Body"].read()

    def stamp(self, key: str) -> int | None:
        with self._lock:
            known = self._known.get(key)
        if known is not None and known.until > time.monotonic():
            return known.stamp
        from botocore.exceptions import ClientError

        self.ensure_bucket()
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            stamp: int | None = int(head["LastModified"].timestamp())
        except ClientError as error:
            if not self._missing(error) and "NoSuchBucket" not in str(error):
                raise
            stamp = None
        self._remember(key, stamp)
        return stamp

    def exists(self, key: str) -> bool:
        return self.stamp(key) is not None

    def delete(self, key: str) -> None:
        from botocore.exceptions import ClientError

        self.ensure_bucket()
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(key))
        except ClientError as error:
            if not self._missing(error) and "NoSuchBucket" not in str(error):
                raise
        self._remember(key, None)

    def keys(self, prefix: str) -> list[str]:
        from botocore.exceptions import ClientError

        self.ensure_bucket()
        found: list[str] = []
        try:
            pages = self.client.get_paginator("list_objects_v2").paginate(
                Bucket=self.bucket, Prefix=self._key(prefix)
            )
            for page in pages:
                found.extend(item["Key"][len(self.prefix) :] for item in page.get("Contents", []))
        except ClientError as error:
            if "NoSuchBucket" not in str(error):
                raise
        return sorted(found)

    def response(
        self, key: str, media_type: str, headers: dict[str, str] | None = None
    ) -> Response | None:
        data = self.get(key)
        if data is None:
            return None
        return Response(data, media_type=media_type, headers=headers)


@cache
def storage() -> Storage:
    """The configured backend — one per process."""
    if settings.storage == StorageBackend.S3:
        if not settings.s3_bucket:
            raise RuntimeError("SBL_STORAGE=s3 needs SBL_S3_BUCKET")
        return S3Storage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            prefix=settings.s3_prefix,
            cache_seconds=settings.s3_cache_seconds,
        )
    return LocalStorage(settings.uploads_dir)


def disposition(filename: str, kind: str = "inline") -> dict[str, str]:
    """A ``Content-Disposition`` header, written the way Starlette's ``FileResponse``
    writes it — so a download is named the same whichever backend served it."""
    quoted = quote(filename)
    if quoted != filename:
        return {"Content-Disposition": f"{kind}; filename*=utf-8''{quoted}"}
    return {"Content-Disposition": f'{kind}; filename="{filename}"'}


async def respond(
    key: str, media_type: str, headers: dict[str, str] | None = None
) -> Response | None:
    """The stored file as a response, read off the event loop — ``None`` when it is gone."""
    return await asyncio.to_thread(storage().response, key, media_type, headers)
