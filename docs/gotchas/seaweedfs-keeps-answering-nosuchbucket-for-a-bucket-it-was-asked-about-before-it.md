# SeaweedFS keeps answering NoSuchBucket for a bucket it was asked about before it existed

**Symptom** — with `SBL_STORAGE=s3`, an upload answers 200 and `has_photo` is true, but
fetching it is a 404. The object store's `GetObject` says `NoSuchBucket` while
`ListObjectsV2` on the same bucket lists the object, and `PutObject` keeps succeeding.
Its log: `getEncryptionConfiguration: … bucket directory not found <bucket>`.

**Cause** — SeaweedFS 3.97's S3 gateway remembers a bucket that a `HeadObject` asked
about while the bucket did not exist, and keeps refusing reads after the bucket is
created (seconds later, and still after minutes). The story tests hit it because their
first call on a fresh store is "is there a photo?", before any upload creates the bucket.
It looked like a disk-full or prefix bug first: a full disk happened in the same hour
(see the preallocation note), and a hand-run script that wrote first worked fine.
`HeadBucket` does not leave the mark.

**Rule** — create the bucket before the first call of *any* kind, not only before the
first write: `S3Storage.ensure_bucket` runs at the head of every operation
(`app/storage.py`). A bucket that is already poisoned stays so — use a new one.

**Evidence** — `head_object(Bucket="poison1")` → 404; `create_bucket`; `put_object` →
200; `get_object` → `NoSuchBucket`, three times over ten seconds. Guarded by
`tests/unit/test_storage.py::test_the_bucket_is_made_before_the_first_question_about_a_key`.

**Seen** — 2026-10-27, branch `compose-setup`.
