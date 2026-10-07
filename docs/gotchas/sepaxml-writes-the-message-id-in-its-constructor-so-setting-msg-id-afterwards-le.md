# sepaxml writes the message id in its constructor, so setting msg_id afterwards leaves a random one in the file

**Symptom** — Downloading the same payment run twice gave two different `<MsgId>`s
(`20261007095826-832862293131`, then `20261007095827-27fea0848792`), although the code
set `transfer.msg_id = run.message_id` before exporting. No error; the file validated.

**Cause** — `SepaPaymentInitn.__init__` calls `_create_header()`, which copies
`self.msg_id` into the XML tree right then. Assigning the attribute after construction
changes the Python object, not the document. What misled: `msg_id` looks like a plain
setting read at `export()`, and the README shows no other way to pass one.

**Rule** — A fixed message id goes in through `_create_header` (subclass, set
`self.msg_id`, call `super()`). Keep the test that downloads a run twice and compares the
ids: a random id per download is invisible otherwise, and it is what lets a bank accept
the same run twice and pay everyone double.

**Evidence** — `api/app/services/payments.py::_RunTransfer`;
`api/tests/stories/test_payment_runs.py::TestExportingARun::test_the_file_is_pain_001_09_with_the_clubs_account`
failed before the subclass; `.venv/.../sepaxml/shared.py` (`__init__` → `_create_header`),
sepaxml 2.7.0.

**Seen** — 2026-10-07
