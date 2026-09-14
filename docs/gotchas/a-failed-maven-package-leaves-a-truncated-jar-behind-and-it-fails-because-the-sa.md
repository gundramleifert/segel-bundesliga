# A failed maven package leaves a truncated jar behind, and it fails because the sandbox denies /tmp

**Symptom** — `mvn -o -DskipTests package` in `reference/PairingList` ends with
`IOException when zipping ...: Read-only file system` and, one line earlier,
`/tmp/jansi-...-libjansi.so.lck (Read-only file system)`. The build says FAILED, but
`target/pairing-list-1.0-SNAPSHOT-jar-with-dependencies.jar` is still there with a fresh
timestamp — 9.9 MB where it used to be 13 MB. Anything run against it afterwards fails for
reasons that have nothing to do with the failure.

**Cause** — the sandbox allows writes to `$TMPDIR`, not to `/tmp`, and the JVM's
`java.io.tmpdir` still points at `/tmp`. The maven-assembly-plugin builds the fat jar
through a temporary file, so it dies **partway through writing**, leaving a jar that exists,
opens as a zip, and is missing classes. What misled me: the jar's timestamp had updated, so
it looked rebuilt — the next command's error was read as a code problem rather than as the
build never having finished.

**Rule** — build Java here with `MAVEN_OPTS="-Djava.io.tmpdir=$TMPDIR" mvn -o -DskipTests
package`, and after any failed build check the jar's **size**, not its timestamp, before
using it. The same applies to any tool that writes through a temp file: a sandbox denial
shows up as a half-written output, not as a missing one.

**Evidence** — the failing run and the sizes are reproducible:
`ls -la reference/PairingList/target/*jar-with-dependencies.jar` reports 13,020,463 bytes
after a successful build and 9,916,412 after the denied one.

**Seen** — 2026-09-14, while adding `PdfExport` to the pairing tool.
