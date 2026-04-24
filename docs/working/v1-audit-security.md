# Security audit (v1 readiness)

**Auditor:** Claude (red-team mode)
**Date:** 2026-04-24
**Repo:** `dendra` @ `main` (v0.2.0)
**Scope:** pre-public-launch security + claim-reality check

## Summary

Dendra's architectural story (rule floor, shadow isolation, circuit
breaker, safety_critical cap) is mostly sound **at the semantic
level** but the implementation has **three CRITICAL** bugs that make
the marketed security guarantees bypassable by anyone with in-process
code access — and two of the three are also reachable from what the
README positions as legitimate user code. The 100%-jailbreak / 100%-
PII claims are **not lies** but they are **not what a reader would
reasonably assume** — see "overstated claims" below.

**Biggest risks for a public launch:**

1. Path traversal in `FileStorage` via attacker-controlled
   `switch_name` (verified — writes escape `base_path`).
2. `safety_critical=True` is trivially bypassable by mutating
   `switch.config.starting_phase = Phase.ML_PRIMARY` post-construction.
   There is no enforcement on the hot path (`_classify_impl`)
   beyond reading `self.config.starting_phase` fresh on every call.
3. The "20-pattern jailbreak corpus" uses a **hard-coded
   `JailbrokenLLM` that always returns `PUBLIC`** and the inputs are
   **pre-loaded with real `EXPORT_CONTROLLED` markers** before the
   rule sees them. The test proves a tautology: a keyword-rule
   matches keywords. None of the 20 patterns are adversarial inputs
   that might fool the *rule*; they are inputs that test whether the
   *shadow LLM* is allowed to override. It is not. That is a phase-0
   invariant (rule is the only decider at MODEL_SHADOW), not a
   jailbreak-resistance claim.

Recommend: **do not ship v1 as-is with current marketing language.**
Either fix the findings below *or* tone down the "survives jailbreaks"
framing to what the code actually delivers ("shadow LLM output cannot
alter rule-phase decisions" — true, but much less impressive).

---

## Findings

### F-01 — FileStorage path traversal via `switch_name`
- **Category:** Injection / Privilege
- **Severity:** CRITICAL
- **Location:** `src/dendra/storage.py:420-421` (`_switch_dir`),
  `src/dendra/storage.py:474-497` (`append_record`)
- **Attack scenario:**
  1. Deployment exposes any control plane (admin UI, multi-tenant
     router, migration tool) where `switch_name` flows from input
     (tenant ID, function name via `dendra init` on a user-uploaded
     file, etc.).
  2. Attacker supplies `switch_name = "../../etc/cron.d/pwn"` or
     `"../../.ssh/authorized_keys"`.
  3. `FileStorage.append_record` calls `self._base / switch_name`,
     `mkdir(parents=True, exist_ok=True)`, then writes JSONL there.
  4. I confirmed this writes to an arbitrary path under the process's
     permissions (see exploit below). The outcome-record JSON becomes
     attacker-controlled bytes on disk at an arbitrary location.
- **Verified:** ran locally against current `main`:
  ```python
  s = FileStorage("/tmp/basepath")
  s.append_record("../pwned", rec)  # creates /tmp/pwned/outcomes.jsonl
  ```
- **Impact:** arbitrary-file-write under the Dendra process's
  permissions. If `fsync=True` on a shared host, this is a primitive
  for privesc (cron drop, SSH key injection, supply-chain poisoning
  of a neighbor switch's log).
- **Fix:** validate `switch_name` against `^[A-Za-z0-9_\-.]{1,128}$`
  (or similar) in `StorageBase.__init_subclass__` helper, AND re-check
  in each built-in backend. At minimum, reject names containing `..`,
  path separators, or absolute paths. The same validation belongs in
  `LearnedSwitch.__init__` — silently writing under a traversed dir
  is worse than a loud `ValueError`.

### F-02 — `safety_critical=True` bypassable by config mutation
- **Category:** Privilege / Claim-Reality Drift
- **Severity:** CRITICAL
- **Location:** `src/dendra/core.py:199-277` (SwitchConfig is a
  plain `@dataclass`, not frozen); `src/dendra/core.py:951-957`
  (`phase()` just reads `self.config.starting_phase`)
- **Attack scenario:**
  1. A switch is constructed with `safety_critical=True`,
     `phase_limit=ML_WITH_FALLBACK`.
  2. Any in-process code path (including a misbehaving rule, an
     imported plugin, a debugging REPL, or a later refactor) does
     `switch.config.starting_phase = Phase.ML_PRIMARY` or
     `switch.config.phase_limit = Phase.ML_PRIMARY` or
     `switch.config.safety_critical = False`.
  3. Next call to `classify()` routes through ML with no rule floor.
     Verified locally: after mutation, `switch.phase()` returns
     `Phase.ML_PRIMARY` with zero error.
- **Impact:** the marketed "refuses to construct in ML_PRIMARY"
  guarantee is a construction-time check only. The README
  ("the rule floor can never be removed") is false in-process.
  Post-incident forensics cannot prove a safety_critical switch
  *stayed* safety_critical across its lifetime.
- **Fix:** freeze `SwitchConfig` (frozen=True) OR make `safety_critical`
  and `phase_limit` private on the switch and enforce the ML_PRIMARY
  refusal inside `_classify_impl` itself, not just construction.
  Add a `_construction_safety_critical: bool` that cannot be unset;
  the hot-path checks it before routing to ML. Consider a
  `ClassificationRecord.config_fingerprint` field so tamper is
  detectable in the audit log.

### F-03 — Rule function is hot-swappable
- **Category:** Privilege
- **Severity:** HIGH
- **Location:** `src/dendra/core.py:489` (`self._rule = rule`, no slots / freeze)
- **Attack scenario:** `switch._rule = lambda x: "PUBLIC"` replaces the
  rule floor silently. Not a "public API" but Python has no private
  attrs; anything in-process can do it.
- **Impact:** the paper's "rule is code, not a prompt" guarantee is
  attached to a mutable attribute. An attacker who can run Python in
  the process (malicious package, compromised dep, pickle load of a
  classify input) can swap the rule for a permissive stub.
- **Fix:** `__slots__` + no setter, or a `_rule_sig: hashlib.sha256` of
  `inspect.getsource(rule)` captured at construction, checked on
  every classify. Budget: ~500 ns, same order as the current overhead.

### F-04 — 20-pattern jailbreak corpus tests a tautology
- **Category:** Claim-Reality Drift
- **Severity:** HIGH (for marketing claims; the code is fine)
- **Location:** `tests/test_security_benchmarks.py:249-278`
- **What the test does:**
  - 20 "jailbreak" strings are prepended with a literal
    `"EXPORT_CONTROLLED marker: "`.
  - A `JailbrokenLLM` hard-coded to return `"PUBLIC"` runs in
    `MODEL_SHADOW`.
  - The test asserts every call returns `"EXPORT_CONTROLLED"`.
  - Since the rule just greps for the literal token
    `"export_controlled"` and the test **prepends the token to
    every input**, the rule is guaranteed to return EXPORT_CONTROLLED
    for every input regardless of anything else.
- **What the test does NOT prove:**
  - That the rule catches any of the 20 patterns on its own (none
    of them contain EXPORT_CONTROLLED / ITAR / samsung_internal /
    classified markers).
  - That a cleverly-crafted input can't make the *rule* emit
    `"PUBLIC"`. (Trivial: any input without the four magic tokens
    does. The rule is a 4-keyword allowlist.)
  - That Dendra has any jailbreak-resistance property beyond
    "MODEL_SHADOW ignores the LLM output". That property is
    architectural, not earned by this test.
- **Impact:** README, applicability doc, and patent filing
  ([0095]-[0098]) all cite "100% rule-floor preserved on 20-pattern
  jailbreak corpus." This is technically true but highly misleading:
  the test proves the rule preempts the LLM when the rule fires,
  which it always does by construction. A reviewer reading the
  claim expects evidence that Dendra defeats actual prompt-injection
  vectors; the test does not supply that evidence.
- **Fix:** either
  - (a) rebuild the corpus so each pattern is a *real* attempt to
    make the rule emit the wrong label (e.g., input that evades
    the keyword match but still means "this is restricted"), and
    measure rule recall honestly (it will be low — that's the
    point; the LLM-shadow is supposed to cover what the rule misses);
  - (b) rename the test to what it actually is
    (`test_shadow_llm_cannot_override_rule_when_rule_fires`) and
    drop the "jailbreak corpus" framing everywhere it appears.
  - Preferably (a): the honest story is *"rule floor is narrow but
    auditable; LLM-shadow extends coverage; ML-graduation closes
    the gap"*. That story is defensible. The current framing isn't.

### F-05 — 25-item PII corpus: rule is tuned to the corpus
- **Category:** Claim-Reality Drift
- **Severity:** MEDIUM
- **Location:** `tests/test_security_benchmarks.py:96-196`,
  marketing doc `docs/marketing/industry-applicability.md:912-914`
- **What the test does:** the 25-item corpus was hand-written
  alongside regexes that detect exactly those 25 items. Assertion is
  `recall >= 0.80, precision >= 0.85`, and the current numbers
  happen to hit 100%. README and marketing cite "100% recall,
  100% precision".
- **Impact:** the claim is "Dendra's PII rule catches all PII on a
  25-item corpus we wrote." That is not a generalizable
  capability claim. Real-world PII (international phone formats,
  UK NI numbers, EU tax IDs, non-hyphenated SSNs, SINs, etc.) is
  not tested. Any independent reviewer running `mimesis`- or
  `Faker`-generated PII through this rule will find ≪ 100%.
- **Fix:** drop the "100%" number from public-facing docs or replace
  the corpus with an adversarial fuzzer generating N≥500 PII variants
  of each type and report honest recall. The patent specification
  [0097] uses the 25-item number as prior art evidence; this will
  not survive adversarial amendment and may undermine broader
  claims if challenged.

### F-06 — `Label.on=callable` fires with raw classifier input
- **Category:** Injection
- **Severity:** MEDIUM (becomes HIGH in multi-tenant deployments)
- **Location:** `src/dendra/core.py:651-658`
- **Attack scenario:** when `labels` is supplied via config (YAML,
  DB-backed registry, `dendra init` with attacker-influenced
  source), the `on=` callables run under the switch process's
  privilege with the raw input. If input is untrusted (public API
  request) and the `on=` action is e.g. `subprocess.run(...)` or a
  DB write, the action runs before any auth check downstream.
- **Impact:** unsanitized request data reaches side-effectful code
  through a mechanism the Label framing ("label-based conditional
  expression") makes look like a pure-functional dispatch. Readers
  familiar with pattern-match dispatch may not realize the handler
  fires inside Dendra's hot path.
- **Fix:** document the execution contract explicitly in `Label`'s
  docstring: "`on` runs in-process with the raw classifier input;
  treat the input as untrusted inside the handler." Consider
  adding a `strict=True` mode that refuses `on=` callables unless
  the caller passes `i_acknowledge_untrusted_input=True`.

### F-07 — Author field is trivially spoofable
- **Category:** Claim-Reality Drift / Audit Integrity
- **Severity:** MEDIUM
- **Location:** `src/dendra/core.py:288-318` (`_derive_author`)
- **Attack scenario:** verified:
  ```python
  def rule(x): ...
  rule.__module__ = "compliance_team.approved"
  s = LearnedSwitch(name="authz", rule=rule)
  assert s.author == "@compliance_team.approved:authz"
  ```
  Any caller can set `rule.__module__` before constructing the
  switch. The auto-derived author is therefore not evidence of
  identity.
- **Impact:** "unspoofable without editing the source that defines the
  switch" (docstring line 296) is false. Log tampering + spoofed
  author together defeat the "tamper-evident audit trail" claim.
- **Fix:** either
  - document honestly ("author is a best-effort provenance hint,
    not an identity assertion"), or
  - derive from `inspect.getsourcefile(rule)` instead of
    `__module__` (harder to spoof without FS access), or
  - require explicit `author=` for any safety-critical switch
    (refuse auto-derivation when `safety_critical=True`).

### F-08 — Outcome log serializes raw input verbatim
- **Category:** Leakage
- **Severity:** HIGH (for HIPAA / PII use cases explicitly marketed)
- **Location:** `src/dendra/core.py:919-935` (`record_verdict`
  writes `input=input` straight through), `src/dendra/storage.py:173`
  (`serialize_record` JSON-encodes with `default=str`)
- **Attack scenario:** user marketed the library for HIPAA-bound
  triage and PII classification. Today every `record_verdict`
  call persists the full `input` to disk (FileStorage) or SQLite,
  in plaintext, with no redaction hook.
  1. Medical intake form with patient MRN flows into `classify()`.
  2. Operator calls `record_verdict(input=intake_form, ...)`.
  3. `runtime/dendra/<switch>/outcomes.jsonl` now contains the
     MRN in plaintext. Backups pick it up. Splunk ingests it.
- **Impact:** directly contradicts the "PII corpus 100% recall"
  marketing — Dendra can *detect* PII but then *persists the
  raw PII in its own outcome log*. HIPAA / GDPR exposure.
- **Fix:** add a `record_redactor: Callable[[Any], Any] | None`
  hook on `LearnedSwitch` that runs before serialization. Default
  to a no-op with a `DeprecationWarning` that ships for a major
  version cycle telling users to supply one. Or: default to
  storing a hash of the input + a length, only storing the raw
  input when `log_raw_input=True` is explicitly set. Document
  both choices in `docs/marketing/industry-applicability.md` §8.7
  where HIPAA is mentioned.

### F-09 — `reset_circuit_breaker()` has no authorization check
- **Category:** Privilege
- **Severity:** MEDIUM
- **Location:** `src/dendra/core.py:1078-1085`
- **Attack scenario:** the README says "only explicit operator
  reset restores ML routing." In code, `reset_circuit_breaker()`
  is a public method that any in-process caller can invoke. If an
  attacker triggers ML failures to trip the breaker (to force
  rule-fallback, e.g., to evade ML-based content moderation), and
  later wants to re-enable ML (to exploit a poisoned head), nothing
  stops them from calling `switch.reset_circuit_breaker()` — or
  from calling it every classification to keep the breaker useless.
- **Impact:** the breaker is "advisory" rather than "authorized."
  Marketing ("bounds the blast radius") overstates what the
  primitive enforces.
- **Fix:** add an `operator_token` parameter or an optional
  `authorize: Callable[[], bool]` hook; the default behavior
  stays permissive, but safety_critical switches should require
  explicit authorization. At minimum: log every reset to
  telemetry (currently does not emit a `breaker_reset` event)
  and the outcome log so post-incident forensics can see it.

### F-10 — `advance()` has no authorization check either
- **Category:** Privilege
- **Severity:** MEDIUM
- **Location:** `src/dendra/core.py:963-1038`
- **Attack scenario:** anyone in-process can call
  `switch.advance()` and mutate `config.starting_phase`. The
  McNemarGate guards on statistical evidence, but an attacker who
  can also call `record_verdict` can *fabricate* outcome records
  that pass McNemar's test and graduate a safety_critical switch
  out of rule mode. (The safety_critical cap still holds —
  can't reach ML_PRIMARY — but reaching ML_WITH_FALLBACK is still
  a substantial capability uplift.)
- **Impact:** `advance()` is part of the published API;
  the README shows no authorization pattern. In a multi-team
  deployment, any team's code can graduate another team's switch.
- **Fix:** same pattern as F-09 — `authorize=` hook, telemetry event,
  outcome-log record of every successful advance so the audit
  chain captures every phase mutation.

### F-11 — `telemetry.emit` exceptions swallowed silently
- **Category:** Leakage / Observability
- **Severity:** LOW
- **Location:** `src/dendra/core.py:602-603`, `635-636`, `948-949`,
  `1034-1036`
- **Attack scenario:** the pattern is `try: emit; except Exception: pass`.
  An attacker planting a telemetry backdoor that raises on specific
  payloads (e.g., to mask audit trail when certain inputs appear)
  has their exception swallowed, including the entire trace. No
  signal that telemetry is broken.
- **Impact:** silent audit-chain hole. Low on its own but combines
  with F-07 and F-02 to make tamper detection impossible.
- **Fix:** on emit failure, write a record to a local "telemetry
  deadletter" in the outcome log itself (not just swallow). Or
  raise on `TelemetryEmitter` init failure so deployments configure
  the hook they expected to configure.

### F-12 — `_SWITCH_REGISTRY` collision check uses `id(storage)`
- **Category:** Privilege / Claim-Reality Drift
- **Severity:** LOW
- **Location:** `src/dendra/core.py:321-327`, `515-537`
- **Issue:** collision detection fires when two switches share
  `(id(storage), name)`. Two separate `FileStorage("runtime/dendra")`
  instances have different `id()` but write to the same directory;
  the registry misses this entirely. A silent shared outcome log —
  the exact thing this code is supposed to prevent — is still
  achievable with two lines.
- **Fix:** backends should expose a stable identity key (e.g.,
  `_storage_identity()` returning the resolved path or DB URI);
  registry keys on that.

### F-13 — ROI CLI reads from attacker-controlled FileStorage path
- **Category:** Injection (low blast-radius)
- **Severity:** LOW
- **Location:** `src/dendra/cli.py:209-242`
  (`cmd_roi`), which does `FileStorage(args.storage)` and then
  calls `load_records` for every discovered switch name. `FileStorage.switch_names()` iterates `_base.iterdir()` — any
  directory name under `args.storage` becomes a `switch_name` that
  gets fed back into `load_records`. Combined with F-01, if an
  attacker can plant a symlink dir named `..` (or worse, an FS-level
  symlink pointing at `/etc`) inside the ROI path, the ROI CLI
  opens files outside the intended base.
- **Fix:** `_read_segment` should verify each segment path is inside
  `self._base.resolve()` before opening.

---

## Security claims verified

These claims **are** backed by real tests that actually prove them:

- **Shadow-phase exception cannot contaminate decision** — verified by
  `test_shadow_exception_never_reaches_caller`. The try/except in
  `_classify_impl` around `self._model.classify(...)` is genuine and
  discards the prediction on any exception.
- **`safety_critical=True` at construction refuses `ML_PRIMARY`** —
  verified; `__init__` raises `ValueError`. (But see F-02 — can be
  undone after construction.)
- **Circuit breaker trips on ML exception and stays tripped across
  calls until `reset_circuit_breaker()`** — verified by
  `test_ml_exception_trips_breaker_and_stays_tripped` and the
  stress test. Genuine. (But see F-09 — anyone can reset.)
- **`MODEL_PRIMARY` below-threshold confidence falls back to rule** —
  verified by `test_llm_primary_still_enforces_rule_fallback_on_low_confidence`
  and the `_classify_impl` MODEL_PRIMARY branch.
- **Zero required runtime dependencies** — verified in `pyproject.toml`;
  `dependencies = []`. Optional extras are appropriate.
- **FileStorage flock serialization under contention** — verified by
  `test_no_data_loss_under_contention` and
  `test_no_data_loss_with_frequent_rotation`. Actual multi-process
  writers, actual assertion of 1000 records intact.

## Security claims that are overstated

- **"20-pattern jailbreak corpus: 100% rule-floor preserved"** —
  see F-04. The corpus is synthetic, the rule is keyword-based,
  the inputs are pre-loaded with the trigger keyword. The test
  proves MODEL_SHADOW ignores the LLM (it does — architectural);
  it does not prove the rule survives adversarial input.
- **"PII corpus: 100% recall, 100% precision"** — see F-05. The
  rule and the corpus were written together. Generalization claim
  unsupported.
- **"Rule floor can never be removed"** — see F-02. Bypassable by
  one line of post-construction mutation.
- **"Tamper-evident audit trail"** — see F-07 (author spoof), F-08
  (raw input leak, paradoxically makes the log *less* auditable
  if PII has to be purged), and F-11 (silent telemetry drop). The
  log is an append log; it isn't cryptographically sealed, not
  chained by hash, and not signed. "Tamper-evident" is not what
  most readers will understand by that phrase.
- **"Safety floor that survives jailbreaks, silent ML failures, and
  unbounded token bills"** (README line 16-17). Of the three:
  - silent ML failures: TRUE (circuit breaker, verified)
  - unbounded token bills: TRUE (LLM only runs when phase asks)
  - jailbreaks: OVERSTATED per F-04
- **"Unspoofable without editing the source that defines the switch"**
  (author docstring) — see F-07, falsified in 2 lines.

## Recommended red-team tests to add

Before v1 public launch, add these tests (each corresponds to a
fix above):

1. `test_switch_name_rejects_path_traversal` — assert
   `FileStorage.append_record("../x", rec)` raises.
2. `test_safety_critical_survives_config_mutation` — construct
   `safety_critical=True`, mutate `config.starting_phase = ML_PRIMARY`,
   assert `classify()` still routes through the rule (and/or raises).
3. `test_rule_cannot_be_swapped_after_construction` — attempting
   `switch._rule = attacker_rule` raises or is detected on next call.
4. `test_record_prediction_redacts_pii_when_redactor_set` — with a
   redactor configured, PII does not appear in the stored record.
5. `test_adversarial_jailbreak_rule_honest` — 20 patterns where the
   rule output *without* the prepended trigger is measured against
   a ground-truth label, so the reported recall is honest.
6. `test_author_spoofing_refused_for_safety_critical` — constructing
   `safety_critical=True` without explicit `author=` raises, or
   attempts to set `rule.__module__` to a caller-chosen value before
   construction are either detected or ignored.
7. `test_circuit_breaker_reset_logged_to_outcomes` — every call to
   `reset_circuit_breaker()` emits a telemetry event and appends a
   record to the outcome log.
8. `test_advance_logged_with_mutation_details` — every successful
   and unsuccessful `advance()` persists to the outcome log (not
   just to telemetry, which can be swallowed).
9. `test_telemetry_emit_failures_are_not_silent` — a failing emitter
   should surface (at minimum via `warnings.warn`), not be
   swallowed.
10. `test_fuzzed_pii_corpus_recall` — N=500 fuzzer-generated PII
    variants per type; report real recall numbers; update marketing
    doc with whatever the fuzzer produces, not with "100%".
11. `test_sqlite_storage_rejects_path_traversal_in_switch_name` —
    SQL is parameterized (safe) but the SwitchName path pattern
    used by operators (`SELECT ... WHERE switch_name=?`) is
    attacker-controllable; add ingest-side validation and test.
12. `test_two_filestorage_instances_same_path_collide` — verify
    F-12 is fixed — two separate `FileStorage("runtime/dendra")`
    objects cannot register the same name without colliding.

## Appendix: quick prioritization

| ID | Sev | Ship-blocker? |
|---|---|---|
| F-01 FileStorage traversal | CRITICAL | YES |
| F-02 safety_critical mutation bypass | CRITICAL | YES |
| F-04 jailbreak claim misleading | HIGH | YES (fix docs minimum) |
| F-08 PII leak to outcome log | HIGH | YES for HIPAA positioning |
| F-03 rule hot-swap | HIGH | v1.1 acceptable if documented |
| F-06 Label.on dispatches raw input | MEDIUM | documented-only for v1 |
| F-07 author spoofing | MEDIUM | documented-only for v1 |
| F-09 reset_circuit_breaker unauth | MEDIUM | v1.1 acceptable |
| F-10 advance unauth | MEDIUM | v1.1 acceptable |
| F-05 PII corpus tuned to rule | MEDIUM | fix marketing language |
| F-11 telemetry silent failure | LOW | v1.1 |
| F-12 storage id collision | LOW | v1.1 |
| F-13 ROI CLI symlink risk | LOW | v1.1 |
