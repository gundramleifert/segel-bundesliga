# weed server preallocates every volume unless told not to, whatever its help says

**Symptom** — the machine's disk runs full while testing against SeaweedFS
(`deploy/compose/`), with only a few kilobytes uploaded; tools fail with "No space left
on device".

**Cause** — `weed server` grows seven volumes per bucket (a bucket is a collection) and
preallocates each to `-master.volumeSizeLimitMB` — 1 GB here — with `fallocate`. `ls`
shows 8-byte `.dat` files, `du` shows the gigabytes. `weed server -h` lists
`-master.volumePreallocate` as off by default, which is why nobody suspects it; a few test
buckets took tens of gigabytes.

**Rule** — pass `-master.volumePreallocate=false` explicitly (`deploy/compose/compose.yaml`
does), and use one bucket, a prefix per test run, rather than a bucket per run.

**Evidence** — two buckets holding one 3-byte object each: `du -sh /data` 14.0G without the
flag, 288K with it.

**Seen** — 2026-10-27, branch `compose-setup`.
