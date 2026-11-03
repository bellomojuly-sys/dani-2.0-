# [DL] How does the trace decide a field is sensitive, and what replaces it?

Date: 2026-11-03 · Microphase: D2-023 · Study objective: F6 (Observability and evals)

## Context — what made the decision necessary

M04 builds an observable trace of every run: D2-021 adds the envelope (run ID,
timestamps) and D2-022 records, per tool call, the name, arguments, status and
duration. The trace is persisted so a third person can reconstruct one run from
evidence (Gate M04), and F6 requires that sensitive data be obscured.

Today the API key lives only in `main.py` (client construction) and never
enters the trace. But the trace now carries tool `arguments` and results, and
those *could* one day hold a secret — a key passed by mistake as a tool
argument, or the secret iCal address that M12 will read and that could come
back inside a result. Before the trace persists anything, we must decide **how
redaction identifies a sensitive value** and **what it leaves in its place**.

## Options

**How a field is judged sensitive**

- **A — by field name.** Redact the value of any key whose name is in an
  explicit sensitive list (`api_key`, `token`, `secret`, `password`,
  `authorization`, …). Deterministic, predictable, explainable in one sentence,
  trivial to test. Cost: it misses a secret that sits in a field with an
  innocent name, or inside free text.
- **B — by value pattern.** Scan every value for secret-shaped patterns (e.g.
  anything matching `sk-…`). Catches a secret regardless of the field name.
  Cost: more complex, produces false positives, the pattern list is a moving
  target, and it is harder to explain and to test.

**What replaces the value**

- **`[REDACTED]` marker.** Keep the field, replace only its value. A reader
  still sees that the field existed and was hidden, so the run stays
  reconstructable — the whole point of the trace.
- **Remove the field.** Drops the information that a field was ever present.

## Decision

Option **A** (redact by field name), and the sensitive value is replaced by the
string **`[REDACTED]`** — the field is kept, only its value changes.

## Why

- **One new concept per microphase.** A is a single, bounded rule; Giulia can
  explain it in one sentence.
- **Testable (F1).** A deterministic name list gives a clean accepted case and
  clear refusal cases: a fake key in a sensitive field disappears, a
  non-sensitive field is untouched, and a deliberate break makes the right test
  fail.
- **Reconstructability (Gate M04).** `[REDACTED]` preserves the shape of the
  trace, so a third person can still follow the run; removing the field would
  lose that.
- B is not thrown away: if a real secret ever slips through a field with a
  non-obvious name, value-pattern redaction becomes a new roadmap row, not a
  silent change here.

## Consequences

- Redaction is a **safety net**, not the primary defence. The primary rule is
  still that secrets should not reach the trace at all.
- **Known, accepted limit:** a secret in a field with a non-sensitive name, or
  buried in free text, is **not** caught by A. This is to be revisited (the B
  row above) if M12's iCal address, or any real secret, can land in a traced
  value under an innocent name.
- The sensitive-name list must be kept current as new tools add new fields; a
  new sensitive field name is a one-line change plus its test.

## Evidence

*To be completed when D2-023 closes (it is blocked until D2-022's trace is in
the branch).* Planned proof: a test that injects a fake key
`sk-FAKE1234567890` into a traced field and asserts (1) the fake value is
**absent** from the serialized safe trace, (2) `[REDACTED]` is **present** in
its place, (3) a non-sensitive field is **unchanged**; plus the deliberate-break
check (F1). Commit hash to be recorded here and in the README Decisions and
Traceability tables at close.
