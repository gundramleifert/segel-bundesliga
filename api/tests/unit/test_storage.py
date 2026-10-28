"""The upload store answers the same on local disk and on S3 (`app/storage.py`).

One contract, run against both backends: the S3 one against moto's in-memory S3, never a
live service. A caller that works on one backend must work on the other — that is the
whole point of `SBL_STORAGE` being a setting rather than a code change.
"""

from __future__ import annotations

import time

import boto3
import pytest
from moto import mock_aws

from app.storage import LocalStorage, S3Storage, copy_all, disposition, valid_name


@pytest.fixture(params=["local", "s3"])
def store(request, tmp_path):
    if request.param == "local":
        yield LocalStorage(tmp_path)
        return
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        # The bucket is not created here: the backend makes it on its first write.
        yield S3Storage(bucket="uploads", prefix="site", client=client)


def test_a_written_file_reads_back(store):
    store.put("clubs/3.png", b"crest")
    assert store.get("clubs/3.png") == b"crest"
    assert store.exists("clubs/3.png")
    assert store.stamp("clubs/3.png") == pytest.approx(time.time(), abs=5)


def test_a_missing_file_is_none_not_an_error(store):
    assert store.get("clubs/4.png") is None
    assert not store.exists("clubs/4.png")
    assert store.stamp("clubs/4.png") is None
    assert store.response("clubs/4.png", "image/png") is None
    store.delete("clubs/4.png")


def test_a_deleted_file_is_gone(store):
    store.put("sailors/1.jpg", b"photo")
    store.delete("sailors/1.jpg")
    assert not store.exists("sailors/1.jpg")
    assert store.get("sailors/1.jpg") is None


def test_keys_are_listed_by_a_plain_prefix(store):
    for key in ["media/abc-480.webp", "media/abc-960.webp", "media/abd-480.webp"]:
        store.put(key, b"x")
    store.put("media-originals/abc.jpg", b"x")
    assert store.keys("media/abc") == ["media/abc-480.webp", "media/abc-960.webp"]
    assert store.keys("media-originals/abc.") == ["media-originals/abc.jpg"]
    assert store.keys("waivers/") == []
    assert store.keys("media") == [
        "media-originals/abc.jpg",
        "media/abc-480.webp",
        "media/abc-960.webp",
        "media/abd-480.webp",
    ]


def test_a_response_carries_the_bytes_and_the_headers(store):
    store.put("expenses/r.pdf", b"%PDF-1.4")
    response = store.response("expenses/r.pdf", "application/pdf", disposition("Beleg ä.pdf"))
    assert response is not None
    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"] == "inline; filename*=utf-8''Beleg%20%C3%A4.pdf"


def test_a_stored_name_never_leaves_its_directory():
    assert valid_name("0123abcd.pdf")
    for name in [None, "", "../x.pdf", "a/b.pdf", "a\\b.pdf", ".hidden"]:
        assert not valid_name(name)


def test_the_s3_backend_keeps_what_it_learned_about_a_key():
    """A crest's existence is asked on every serialized club; within the cache time only
    the first question goes to the object store."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        store = S3Storage(bucket="uploads", client=client, cache_seconds=60)
        store.put("clubs/1.png", b"crest")
        calls: list[str] = []
        client.meta.events.register("before-call.s3.HeadObject", lambda **_: calls.append("head"))
        for _ in range(5):
            assert store.exists("clubs/1.png")
            assert not store.exists("clubs/2.png")
        assert calls == ["head"]  # clubs/1 was written here, clubs/2 asked once


def test_the_bucket_is_made_before_the_first_question_about_a_key():
    """SeaweedFS remembers a bucket that was asked about before it existed and keeps
    answering reads with NoSuchBucket after it is created — so the first call of any kind
    creates the bucket, before it looks for a key in it."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        calls: list[str] = []
        client.meta.events.register("before-call.s3", lambda model, **_: calls.append(model.name))
        store = S3Storage(bucket="fresh", client=client)
        assert not store.exists("clubs/1.png")
        assert calls == ["HeadBucket", "CreateBucket", "HeadObject"]


def test_every_file_copies_to_the_other_backend(store, tmp_path):
    """Moving the uploads between the disk and S3, or between two providers, is a copy
    under the same keys — and a copy into a directory is a backup (`app/storage_copy.py`)."""
    store.put("clubs/3.png", b"crest")
    store.put("media-originals/abc.jpg", b"original")
    store.put("waivers/0123abcd.pdf", b"%PDF")
    backup = LocalStorage(tmp_path / "backup")
    assert copy_all(store, backup) == 3
    assert backup.get("media-originals/abc.jpg") == b"original"
    with mock_aws():
        client = boto3.client("s3", region_name="eu-central-1")
        other = S3Storage(bucket="moved", region="eu-central-1", client=client)
        assert copy_all(backup, other) == 3
        assert other.keys("") == ["clubs/3.png", "media-originals/abc.jpg", "waivers/0123abcd.pdf"]
        assert other.get("waivers/0123abcd.pdf") == b"%PDF"


def test_a_bucket_outside_us_east_1_is_created_where_it_belongs():
    """AWS refuses a CreateBucket without a location everywhere but us-east-1."""
    with mock_aws():
        client = boto3.client("s3", region_name="eu-central-1")
        store = S3Storage(bucket="frankfurt", region="eu-central-1", client=client)
        store.put("clubs/1.png", b"crest")
        assert (
            client.get_bucket_location(Bucket="frankfurt")["LocationConstraint"] == "eu-central-1"
        )
