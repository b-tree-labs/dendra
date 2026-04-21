# PROVISIONAL PATENT APPLICATION

**Title of Invention:**

**SYSTEM AND METHOD FOR GRADUATED-AUTONOMY CLASSIFICATION WITH
STATISTICALLY-GATED PHASE TRANSITIONS, AND COMPANION ANALYZER
SYSTEM FOR IDENTIFYING CLASSIFICATION SITES IN PRODUCTION
CODEBASES**

---

**Inventor:** Benjamin Booth
**Address:** 1060 Hidden Hills Drive, Dripping Springs, TX 78620
**Citizenship:** US
**Filing Date:** [LEFT BLANK — to be stamped by USPTO Patent Center]
**Entity Status Claimed:** Micro entity (37 CFR 1.29)
**Intended Assignee:** B-Tree Ventures, LLC

**Filing type:** Provisional Patent Application (35 USC 111(b)).

---

> **Note to self / future utility-conversion attorney.** This
> provisional specification is intentionally over-inclusive. Every
> variation, alternative, and embodiment described herein is
> intended to establish priority under 35 USC 119(e) for later
> utility-application claims that may read on any described
> subject matter. Per the guidance at §11a.3 of the accompanying
> patent-strategy analysis, insufficient disclosure is the single
> largest pro se filing failure mode. This document addresses that
> by over-describing.
>
> No formal patent claims are included — claims are optional in a
> provisional (37 CFR 1.53(c)) and will be drafted with attorney
> assistance during utility conversion. A non-limiting "Claim
> Concepts" section at §12 guides that future drafting.

---

## 1. TECHNICAL FIELD

[0001] This disclosure relates generally to production-deployed
classification systems — software systems that assign one of a
fixed set of labels to an input, based on a rule, a large language
model ("LLM"), or a machine-learned model ("ML head"). More
specifically, this disclosure describes: (a) a graduated-autonomy
classification system comprising six operational phases, each
associated with a specific routing among classifier tiers, wherein
advancement between phases is gated by statistical evidence drawn
from an append-only, self-rotating outcome log; and (b) a static-and-dynamic code-analysis system for identifying classification
decision points in production codebases and projecting quantified
per-site economic benefit from converting each such point to the
graduated-autonomy system.

## 2. BACKGROUND AND PROBLEM STATEMENT

### 2.1 Universality of classification decision points

[0002] Every non-trivial software system contains classification
decision points — locations in code where the program selects one
of a finite set of outcomes based on the shape or content of an
input. Examples include, without limitation: routing a customer-support ticket to a handling category; assigning an intent label
to a conversational turn; determining whether a piece of content
requires moderator review; selecting a retrieval strategy for a
semantic search; classifying a network request as safe, suspicious,
or known-malicious; scoring a financial transaction against a fraud
taxonomy; or classifying an LLM-generated response as safe, toxic,
leaking personally identifiable information (PII), or containing
confidential content.

### 2.2 The rule-to-ML migration problem

[0003] At the moment a classification decision point is first
introduced in production, training data sufficient to support a
machine-learned classifier does not yet exist. Engineers
therefore ship hand-written rules — if/else dispatchers, keyword
matchers, regular-expression lookups, and similar deterministic
heuristics — as the initial implementation. Over time, outcome
data accumulates: each classification is followed, eventually,
by some signal (user correction, downstream resolution success,
audit disposition, manually-reviewed ground-truth label) that
retrospectively resolves whether the classification was correct.

[0004] Once sufficient outcome data has accumulated, a machine-learned classifier trained on that data typically outperforms
the rule on held-out evaluation. The technical question
addressed by the present invention is *when and how* to
transition between classifier tiers such that three concurrent
technical properties hold:

1. **Bounded regression probability.** The probability that any
   phase transition produces a classifier with mean accuracy
   worse than the rule's mean accuracy, measured over the post-transition window, is bounded above by a configurable value.
2. **Bounded storage.** The outcome record store does not grow
   without bound regardless of classification volume or runtime
   duration.
3. **Failure-domain isolation.** Failures of observational or
   higher-autonomy classifier tiers do not propagate into the
   user-visible decision path.

[0005] Prior art achieves each of these properties individually
in disparate contexts but does not achieve them jointly as a
single architectural composition. Representative prior-art
contexts are addressed in §2.3.

### 2.3 Technical prior art and its limits

[0006] **Shadow-mode deployment.** Prior-art "shadow mode" runs a
candidate classifier alongside a production classifier for
observation, typically with the shadow's output logged for
offline comparison. However, prior-art shadow-mode
implementations do not architecturally isolate the shadow from
the decision path; an exception or timeout in the shadow
classifier can, in typical implementations, block or contaminate
the decision-maker's output. Prior art therefore does not
achieve failure-domain isolation ([0004] property 3).

[0007] **Try-ML-else-fallback patterns.** A widespread production
pattern wraps an ML classifier call in an exception-handling
construct, falling back to a rule on failure. This provides a
one-time fallback but does not (a) persist the fallback state
across subsequent calls (so failures recur), (b) gate the
activation of the ML tier on statistical evidence, or (c) bound
the probability of worse-than-rule operation in the steady
state. Prior art therefore does not achieve bounded regression
probability ([0004] property 1).

[0008] **Canary / gradual rollout.** Prior-art canary systems
route a percentage of traffic to a new implementation and
increase the percentage over time. Rollout percentages are
typically chosen by operator judgment or traffic-proportional
scheduling, not by hypothesis tests against observed outcomes.
Prior art therefore does not supply a formal mechanism for
bounded regression probability ([0004] property 1).

[0009] **AutoML and automated model-selection platforms.**
Prior-art AutoML systems select a model given training data;
they do not operate on the rule-to-ML transition problem, do
not provide a deterministic rule safety floor, and do not
provide shadow-phase isolation.

[0010] **Online-learning systems.** Prior-art online learners
(e.g., Vowpal Wabbit, adaptive models) update model parameters
continuously from observed data. They do not provide a
separate deterministic rule floor for safety-critical
authorization classes, nor statistical gating of transitions
between autonomy levels.

[0011] **Circuit-breaker patterns.** Prior-art circuit breakers
(as described by Nygard 2007 and implemented in libraries such
as Netflix Hystrix, resilience4j, and equivalents) detect
downstream-service failures and route traffic to fallbacks.
Prior-art circuit breakers operate on service-call failures in
general; they do not operate in the context of a multi-tier
classifier with statistical phase gating, nor do they
structurally enforce a safety-critical cap that prevents the
highest-autonomy phase from being reached under specified
conditions.

[0012] **Log-rotation utilities.** Prior-art log-rotation
utilities (logrotate, log4j rolling files, etc.) bound log
storage growth. They are general-purpose utilities and are not
integrated with classification-outcome semantics or with
statistical phase gating; they alone do not support the
invention's ([0004]) joint property set.

[0013] The present invention is distinguished from prior art by
providing, in a single architectural composition, all three
technical properties of [0004] simultaneously, together with
additional architectural properties (safety-critical cap,
persistent-recovery state, and shadow isolation) described in
detail below. The non-obviousness of the combination derives
from the fact that the three properties of [0004] are not
jointly provided by any combination of the prior-art
components described in [0006]–[0012]: naively combining
shadow-mode + try-ML-else-fallback + log-rotation does not
produce a bounded regression probability, because neither
shadow-mode nor try-ML-else-fallback provides a statistical
gating mechanism, and log-rotation alone does not provide any
classification semantics.

### 2.4 What the present invention does

[0014] The present invention provides, in one or more preferred
embodiments:

- **A graduated-autonomy classification system** (§3)
  comprising a plurality of ordered classifier tiers, phase-dependent routing among the tiers, statistical gating of
  phase transitions against an outcome record store with
  bounded retention, architectural enforcement of a safety-critical invariant preventing the highest-autonomy phase
  under configured conditions, and a persistent-recovery
  mechanism from the highest-autonomy phase upon detected
  failure.
- **A companion static-and-dynamic analyzer** (§4) that
  identifies classification decision points in production
  codebases, measures their traffic characteristics non-invasively, and projects quantified per-site technical
  benefit from conversion.

## 3. SUMMARY OF THE INVENTION — GRADUATED-AUTONOMY SYSTEM

### 3.1 Core components

[0015] In one embodiment, the graduated-autonomy classification
system comprises at least the following components:

- **A switch instance** (any discrete unit of state carrying at
  minimum a phase, a rule tier, and an outcome log; see §15
  for functional definition).
- **A phase selector** taking values from an ordered finite set
  of at least two phases; the preferred embodiment uses a
  six-phase ordered set (§3.2), but alternative phase sets of
  other cardinalities and names are within scope (§14, §15).
- **A rule tier**, being a deterministic function from input to
  label, supplied by the user.
- **One or more learned classifier tiers**, each satisfying a
  classification protocol that maps input to a label and a
  confidence value; preferred embodiment includes an LLM tier
  and a machine-learned tier, each optional.
- **An outcome record store** providing durable storage of
  classification records with bounded retention (achieved by
  any mechanism — size-based rotation, time-based rotation,
  log compaction, bounded-retention replication, or equivalent).
- **A configuration record** specifying at least the current
  phase and a safety-critical flag; preferred embodiment also
  specifies a confidence threshold.
- **A transition gate** permitting phase advancement only when
  evidence drawn from the outcome record store satisfies a
  configured criterion (§3.3, §15).
- **A telemetry emitter**, optional, for external monitoring.

### 3.2 Phase semantics

[0016] Each phase defines a specific classification-routing
semantic. The preferred embodiment uses six ordered phases;
alternative embodiments use other phase counts per §14. The
ordered preferred-embodiment phases are:

- **RULE**: the rule tier alone produces the classification; no
  learned tier is invoked.
- **LLM_SHADOW**: the rule tier produces the classification;
  the LLM tier is invoked observationally. Observational
  invocations are architecturally isolated from the decision
  path (§3.7) — their failures (exceptions, timeouts, invalid
  outputs, etc.) do not propagate to the caller.
- **LLM_PRIMARY**: the LLM tier produces the classification
  when a decision-acceptance predicate is satisfied (in the
  preferred embodiment, a confidence threshold; alternatives
  in §13, §14); otherwise the rule tier's output serves as a
  fallback. Detected LLM failure triggers rule-fallback.
- **ML_SHADOW**: primary decision follows LLM_PRIMARY semantics
  (or RULE if no LLM is configured); the machine-learned tier
  is invoked observationally.
- **ML_WITH_FALLBACK**: the machine-learned tier produces the
  classification when the acceptance predicate is satisfied;
  otherwise rule-fallback.
- **ML_PRIMARY**: the machine-learned tier produces the
  classification unconditionally, subject to the recovery
  mechanism of §3.5. Detected failure of the tier activates
  the recovery mechanism, routing subsequent classifications
  to the rule tier until the recovery condition (§3.5) is met.

### 3.3 Evidence-based transition gate

[0017] Advancement from a lower phase to a higher phase is
gated by a configured evidence-based criterion applied to the
outcome record store. In the preferred embodiment, the
criterion is a paired-proportion hypothesis test (McNemar's
exact test or equivalent) over per-example correctness vectors,
with a configurable one-sided significance level alpha (typical
alpha = 0.01); advancement is permitted when the p-value falls
below alpha. Alternative criteria per §13.5 and §14.3 include
unpaired two-proportion tests, Wilson interval comparison,
Bayesian posterior comparison, accuracy-margin criteria, cost-weighted expected-value criteria, operator-approved criteria,
sequential-probability-ratio tests, and equivalents; each such
criterion is within scope.

[0018] **Technical improvement.** When the transition gate is a
paired-proportion hypothesis test at significance level alpha, the
probability that any single permitted phase transition produces
a classifier whose mean accuracy on the post-transition
distribution is worse than the rule's mean accuracy on the same
distribution is bounded above by alpha (the Type-I error rate of
the test). For k transitions in the lifetime of an instance of
the system, the family-wise error rate is bounded above by k·alpha
under independence, or by a tighter bound (e.g., alpha/k by
Bonferroni correction) under stricter multiple-testing
controls. This bounded-regression-probability property is a
distinguishing technical improvement of the invention relative
to the prior art described in §2.3.

### 3.4 Outcome record store

[0019] The outcome record store is a durable record of
classification events. Each record captures at minimum: an
indicator of the input, the output produced by the system, and
an indicator of the ground-truth outcome as it was
retrospectively determined. Preferred embodiments capture
additional fields including timestamp, source tier, confidence
score, and shadow observations (rule / LLM / ML outputs captured
in parallel when the phase so prescribes).

[0020] The outcome record store is retained with bounded
storage. "Bounded storage" means that the store does not grow
without limit as a function of classification volume or elapsed
time; it is maintained at a configurable upper size by any
mechanism including without limitation: size-triggered segment
rotation with segment-count-based retention; time-triggered
segment rotation; log compaction (coalescing duplicate-input
entries); LRU eviction; bounded-retention replication to a
separate store; or equivalent. The preferred embodiment uses
size-triggered segment rotation with segment-count-based
retention, achieving a predictable upper storage bound computed
as (max_bytes_per_segment x (max_rotated_segments + 1)); the
preferred default values are illustrative (64 MB x 9 = ~576 MB)
and not limiting. See
§5.4.4 for the formal proof sketch.

### 3.5 Persistent-recovery mechanism

[0021] In the highest-autonomy phase (ML_PRIMARY in the
preferred embodiment), the learned tier produces the
classification subject to a persistent-recovery mechanism.
Upon detection of a classifier failure — an exception, a
timeout, an invalid output outside the configured label set,
or any other detectable fault — the mechanism transitions into
a reverted state in which classification requests route to the
rule tier. The reverted state persists across subsequent
classification calls, preventing automatic retry of the
failing tier, until a recovery condition is met. The recovery
condition may be an explicit operator signal, a time-based
probe, a half-open probe attempting a single test call, a
rate-limited gradual traffic return, or equivalent; preferred
embodiment requires an explicit operator signal, and
alternatives per §14.6 are within scope.

### 3.6 Safety-critical architectural invariant

[0022] The configuration includes a **safety_critical** attribute.
When true, the system architecturally refuses to operate in the
highest-autonomy phase (ML_PRIMARY). The refusal is enforced at
an architectural point — preferred embodiment at switch
construction time (producing a construction-time error when the
configuration requests the highest phase with safety_critical =
true), alternative embodiments per §14.5 at runtime validation,
configuration-load time, static analysis time, policy-engine
evaluation, or cryptographic attestation. The safety-critical
invariant protects classifications whose correctness carries
regulatory, safety, or fiduciary weight (content moderation,
export-control routing, fraud blocking, clinical coding,
authorization) from entering a state where no deterministic
rule tier serves as the decision-maker.

### 3.7 Shadow-path isolation

[0023] Observational classifier invocations (phases in which a
tier runs alongside the decision-maker for observation only)
are architecturally isolated from the decision path. Isolation
may be synchronous (the observational invocation is wrapped in
a failure-absorbing construct), asynchronous (the observational
invocation runs on a separate thread, process, or background
queue and correlates to the outcome record out-of-band),
separated by message-bus topic (decision and observation on
distinct topics with separate subscribers), or equivalent. The
invariant is that no failure — exception, timeout, invalid
output, adversarial input — of any observational tier can
affect the user-visible decision or block the decision path.

### 3.8 Public API (reference implementation)

[0024] In one embodiment, the switch is exposed to application
code through a decorator that wraps a user function; in
alternative embodiments, through direct class instantiation,
through a service endpoint (REST/gRPC), through configuration-driven framework integration, or any equivalent surface (see
§14.9). The API surface is not a limitation of the invention;
the reference implementation uses a Python decorator for
illustration only.

### 3.9 Host-application integration via optional adapter

[0028] For integration into host applications that wish to be
"classification-primitive-ready" without taking on a hard
dependency on the invented system, the invention contemplates a
thin adapter module residing in the host codebase. The adapter
module attempts to import the invented system's public API under
a Python `try/except ImportError` guard; on successful import,
the adapter instantiates a switch and delegates to it; on failure
to import (i.e., when the invented system is not installed), the
adapter exposes no-op functions that preserve the host
application's classification behavior unchanged. This pattern
is referred to herein as **"learning-ready" integration** and
is described in detail in §5.12.

## 4. SUMMARY OF THE INVENTION — ANALYZER SYSTEM

### 4.1 Core components

[0029] In one embodiment, the analyzer system comprises at least:

- **A static-analysis module**, which parses source files of a
  target codebase, identifies functions whose abstract syntax
  trees match patterns from a stored pattern library characterizing
  classification decision points, and emits structured findings
  per identified site.
- **A dynamic-instrumentation module**, which, upon user request,
  attaches a measurement-only wrapper to each identified site; the
  wrapper records call volume, input-shape statistics, output
  distribution, and optional outcome signal, without mutating the
  decision path of the site.
- **A reference cost model**, comprising parameterized ranges for
  baseline engineering effort per rule-to-ML migration, per-site
  regression cost, per-call token cost, and associated multipliers,
  all exposed as adjustable assumptions.
- **A savings projector**, which combines static findings, dynamic
  measurements, and the reference cost model to produce per-site
  projected annual savings with explicit ratio-based decomposition
  back to individual assumptions.
- **A report generator**, which emits both a machine-readable
  JSON artifact (suitable for continuous-integration diff
  tracking) and a human-readable report ranking identified sites
  by projected savings.

### 4.2 Pattern library

[0030] The pattern library comprises at least patterns for: if-elif-else chains with string-literal return values; match-case
dispatchers; keyword-matching classifiers (for example, patterns
of the form `if keyword in text: return label`); regular-expression dispatchers; LLM-prompted classifiers (patterns of
function bodies that construct a prompt and parse a label
response); and rule-tree dispatchers (recursive conditional
structures reducing to a finite label set). The pattern library
is extensible; new patterns can be added without modifying
downstream modules.

### 4.3 Non-invasive dynamic measurement

[0031] The dynamic-instrumentation module's measurement wrapper
is non-invasive: it executes the site's existing logic before
recording any measurement, and measurement failures do not
propagate to the caller. This architectural property guarantees
that the measurement layer does not change the runtime behavior
of the target site, enabling adoption in production environments
without behavioral risk.

### 4.4 Savings projector with transparent assumptions

[0032] The savings projector combines at least four categories
of savings:

- **Direct engineering savings** — the difference between baseline
  rule-to-ML migration engineering effort and the effort required
  under the graduated-autonomy system, multiplied by fully-loaded
  engineering cost per unit time.
- **Time-to-ML acceleration** — the value of earlier ML
  availability, computed as (months-accelerated x monthly-value-per-site).
- **Regression avoidance** — the expected annual value of
  avoided silent-regression events, computed as (regressions-per-site-per-year x regression-cost x volume-adjustment).
- **Token-cost savings** — the annualized LLM-API-call cost
  avoided by routing a fraction of decisions through rule or
  ML pathways rather than through the LLM.

[0033] Each category is computed as a product of discrete
assumptions, each of which is exposed through a user-adjustable
configuration interface. The report artifact echoes each
assumption value back to the reader, enabling verification and
adjustment.

## 5. DETAILED DESCRIPTION OF PREFERRED EMBODIMENTS

### 5.1 Overall system architecture

[0034] Referring to FIG. 1, the graduated-autonomy classification
system 100 comprises a switch instance 110 which mediates between
a caller 102 (typically production application code) and a
decision-making chain comprising a rule function 120, an
optional LLM classifier 130, and an optional ML head 140. The
switch 110 is configured by a configuration record 112 which
specifies the operational phase, confidence threshold, safety-critical flag, and other parameters detailed herein. Classification
outcomes are recorded to a storage backend 150 which maintains
an append-only, self-rotating outcome log 152. A telemetry
emitter 160 receives optional observation events for external
monitoring.

[0035] The caller 102 invokes the switch 110's `classify` method
with an input value, receiving a classification result comprising
at least an output label, a source identifier, a confidence score,
and a current-phase identifier. The caller 102 later — upon
obtaining ground-truth outcome information from external signals —
invokes `record_outcome` to associate an outcome label with a
previously-classified input.

### 5.2 Phase state machine

[0036] Referring to FIG. 2, the phase selector is a state machine
over the six-element set {RULE, LLM_SHADOW, LLM_PRIMARY,
ML_SHADOW, ML_WITH_FALLBACK, ML_PRIMARY}. Permitted transitions
are forward-only in typical operation (each phase advances to
the next when the statistical gate is satisfied) but the system
also permits operator-initiated regression to any earlier phase
(e.g., reverting from ML_WITH_FALLBACK to LLM_PRIMARY upon
observing unexpected ML behavior).

[0037] In one embodiment, the phase is stored as a field on the
configuration record. Advancing the phase amounts to mutating
this field after the statistical gate test passes. Alternative
embodiments maintain phase as an attribute of the switch itself,
with phase transitions mediated by a separate `transition`
method.

### 5.3 Classification decision flow per phase

[0038] Referring to FIG. 3, the classification decision flow
follows different paths depending on the current phase. In all
phases, the rule function 120 is invoked first and its output
retained as `rule_output`. Subsequent actions depend on phase:

**RULE** (phase 0): Return the rule output directly. No further
classifiers are invoked. Outcome log records the rule output
with source "rule" and confidence 1.0.

**LLM_SHADOW** (phase 1): Invoke the LLM classifier 130 for
observation. On LLM success, record the LLM output and
confidence on the switch's internal "last shadow" state for
pickup at the next `record_outcome` call. On LLM exception,
swallow the exception and continue. Return the rule output with
source "rule" and confidence 1.0.

**LLM_PRIMARY** (phase 2): Invoke the LLM classifier 130. On
LLM exception, return the rule output with source "rule_fallback"
and confidence 1.0. On LLM success, compare the LLM confidence
against the threshold; if below threshold, return the rule output
with source "rule_fallback" and confidence 1.0; if at or above
threshold, return the LLM output with source "llm" and the LLM's
confidence.

**ML_SHADOW** (phase 3): The primary decision follows LLM_PRIMARY
semantics if an LLM is configured, otherwise RULE semantics. In
parallel, invoke the ML head 140 for observation. On ML exception,
swallow. Record the ML output and confidence on the switch's
internal "last ML" state.

**ML_WITH_FALLBACK** (phase 4): Invoke the ML head 140. On
exception, return rule output with source "rule_fallback". On
success, compare confidence to threshold; if below, return rule
with source "rule_fallback"; if above, return ML output with
source "ml" and ML confidence.

**ML_PRIMARY** (phase 5): If the circuit breaker is tripped,
return rule output with source "rule_fallback". Otherwise invoke
the ML head 140. On exception, trip the circuit breaker and
return rule output with source "rule_fallback". On success,
return the ML output with source "ml" and ML confidence,
regardless of confidence threshold (the breaker, not the
threshold, provides the safety floor).

### 5.4 Outcome record schema and storage

[0039] Each outcome record comprises at least the following
fields: a timestamp (floating-point seconds since Unix epoch);
the input; the output; the outcome label (one of: "correct",
"incorrect", "unknown"); the source label (one of: "rule", "llm",
"ml", "rule_fallback"); the confidence score; and, optionally
(depending on the phase at classification time), the captured
rule output, LLM output, LLM confidence, ML output, and ML
confidence from shadow evaluations.

[0040] **Serialization (illustrative embodiment).** In one
embodiment, each record is serialized to a single line of JSON
text; Unicode is permitted; non-ASCII characters are encoded
using UTF-8 and JSON-escape sequences; default handlers for
non-JSON-serializable types convert to string form; lines are
separated by the operating system's native line separator
(`os.linesep`). The JSON-lines serialization is illustrative
only. Alternative serialization formats — including but not
limited to YAML, MessagePack, CBOR, Apache Parquet, Protocol
Buffers, Avro, and custom binary encodings — are expressly
contemplated as non-limiting substitutions; see §13.6 for
extended storage-backend alternatives.

[0041] **Segment layout.** The storage backend organizes outcome
records into segments. In the illustrative embodiment, the
active segment is the file `outcomes.jsonl` at path
`<base>/<switch_name>/outcomes.jsonl`; rotated segments are named
`outcomes.jsonl.1`, `outcomes.jsonl.2`, and so forth up to a
configurable retention count (default 8 segments). Segment 1 is
the most-recently-rotated; higher indices correspond to older
rotations. The specific file extensions and naming convention
(`outcomes.jsonl`, `.jsonl.N`) are illustrative; any naming
convention that uniquely identifies the active segment and
rank-orders rotated segments is within the scope of this
embodiment.

[0042] **Rotation trigger and procedure.** Each call to
`append_outcome` first checks the size of the active segment;
if appending the new record would cause the segment to exceed
the configured `max_bytes_per_segment` (default 64 MB), rotation
is triggered before the write. The rotation procedure is:

1. Delete any rotated segments at indices beyond the retention
   cap `max_rotated_segments`.
2. Shift rotated segments up by one index (segment N -> segment
   N+1), starting from the highest occupied index so no active
   path is clobbered.
3. Rename the active segment `outcomes.jsonl` to
   `outcomes.jsonl.1`.
4. Append the new record to a fresh `outcomes.jsonl`.

[0043] **Bounded-growth property.** The total storage consumed
per switch is bounded above by (`max_bytes_per_segment` x
(`max_rotated_segments` + 1)). With default values this is
approximately 576 megabytes per switch.

[0044] **Read path.** The `load_outcomes` operation returns a
chronologically-ordered list of records by reading segments in
order: first `outcomes.jsonl.<retention_cap>` (oldest), then
each lower-indexed rotated segment, then the active segment
`outcomes.jsonl`. Malformed lines (e.g., partial writes from
an interrupted process) are silently skipped.

[0045] **Tamper evidence.** In one embodiment, outcome records
are extended with a cryptographic hash linking each record to
its predecessor (Merkle-style chain), producing tamper-evident
semantics without requiring a separate audit infrastructure.

### 5.5 Statistical transition gate implementation

[0046] Referring to FIG. 4, the statistical transition gate
operates as follows. At each "checkpoint" — a regular interval
during outcome accumulation, typically every N outcomes — the
gate collects per-example predictions from the decision-maker
and the candidate higher-tier classifier over a fixed held-out
evaluation set. The gate then computes two boolean vectors:
`decision_correct[i]` indicating whether the current decision-maker's i-th prediction matches ground truth, and
`candidate_correct[i]` similarly for the higher-tier classifier.

[0047] McNemar's exact test is then applied. The count `b` is the
number of indices where `decision_correct` is false and
`candidate_correct` is true (cases where the candidate won). The
count `c` is the symmetric case where the decision-maker won.
The total `n = b + c` is the number of disagreements between the
two. Under the null hypothesis that the two classifiers are
equally good, b is distributed as Binomial(n, 0.5). The one-sided
p-value is the right-tail probability P(X >= b | X ~ Binomial(n,
0.5)).

[0048] When n <= 50, the exact binomial sum is computed directly.
When n > 50, a continuity-corrected normal approximation is
used: z = (b - c - sign(b - c)) / sqrt(b + c); one-sided p-value =
0.5 · erfc(z / sqrt2).

[0049] When paired per-example data is not available, an
unpaired two-proportion z-test is used as a conservative
approximation: p_pooled = (p_candidate + p_decision_maker) / 2;
variance = p_pooled · (1 - p_pooled) · (2 / n); z = (p_candidate
- p_decision_maker) / sqrtvariance; one-sided p-value = 0.5 ·
erfc(z / sqrt2). This is conservative because it does not exploit
the correlation between paired observations; therefore if it
says "significant", the paired test would also.

[0050] The gate returns "permit advance" when the p-value is
below the configured alpha (typical alpha = 0.01); otherwise the gate
returns "hold".

### 5.6 Circuit breaker implementation

[0051] Referring to FIG. 6, the circuit breaker is implemented
as a boolean attribute `_circuit_tripped` on the switch object.
In phase ML_PRIMARY, each call to `classify` first checks this
attribute. If true, the call routes directly to the rule
function with source "rule_fallback", bypassing the ML head. If
false, the ML head is invoked inside a try/except block; on
exception, the attribute is set to true and the call routes to
rule-fallback.

[0052] A separate method `reset_circuit_breaker` clears the
attribute. In one embodiment, this method accepts a "reason"
string that is logged for operator auditability.

[0053] In an alternative embodiment, the breaker includes a
"half-open" state in which, after a configurable quiet period,
the ML head is re-probed with a single call to test recovery.
Success transitions to the normal state; failure re-trips the
breaker. This variation enables automatic recovery for
transient ML failures.

### 5.7 Safety-critical construction-time check implementation

[0054] At switch construction time, before the switch object's
internal state is initialized, the constructor checks whether
the configuration specifies `safety_critical = True` and
`phase = ML_PRIMARY`. If both are true, the constructor raises
an exception and the switch object is not created. The exception
message cites paper §7.1 and the containing safety rationale.

[0055] This check is architectural: the only way to create a
safety-critical switch in ML_PRIMARY phase would be to bypass
the constructor entirely, which violates the Python object model.
Third-party code attempting to graduate a safety-critical switch
to ML_PRIMARY at runtime must modify the configuration record
directly, at which point the switch's own `classify` method
could re-validate, but in practice the construction-time check
is sufficient for the load-bearing property.

### 5.8 Shadow-phase isolation implementation

[0056] The LLM_SHADOW and ML_SHADOW paths are implemented with
the following invariant: the decision-maker's output is
determined before the shadow classifier is invoked. When the
shadow classifier is invoked, its call is wrapped in a
try/except block that catches all exceptions and discards them.
No exception raised by a shadow classifier can propagate to the
caller, and no shadow-classifier output is used in computing
the switch's return value.

### 5.9 LLM classifier protocol

[0057] The LLM classifier is specified by a protocol: any object
with a method `classify(input, labels) -> LLMPrediction`, where
LLMPrediction is a value object carrying a `label` (string) and
a `confidence` (float in [0, 1]).

[0058] In the preferred embodiment, the invention ships thin
adapters for several LLM providers: an OpenAI-compatible chat-completions adapter (usable against OpenAI, Together, Groq,
vLLM, LiteLLM, etc.); an Anthropic Messages-API adapter; an
Ollama local-model adapter; and a llamafile adapter. Each
adapter parses the model's natural-language response and
normalizes it to one of the configured labels via a
best-effort matching routine (exact match, contained-in-label
match, and substring match, in that order).

[0059] The adapter abstraction permits the invention to remain
provider-agnostic: an integrator may substitute any classifier
implementing the protocol, including proprietary in-house
classifiers, open-weight models served locally, remote inference
services, or caching layers atop any of the above.

[0059a] **Model family is not limited to large language models.**
The terms "LLM classifier," "LLM_SHADOW," and "LLM_PRIMARY" are
used throughout this specification as illustrative shorthand for
an intermediate probabilistic tier that provides richer
generalization than the rule tier without yet occupying the
highest-autonomy seat. The tier is defined by the protocol
(`classify(input, labels) -> (label, confidence)`), not by a
specific model architecture. Alternative embodiments of the
tier include, without limitation: small language models
(sub-billion-parameter transformer variants, distilled or
quantized); masked-language models and encoder-only architectures
(e.g., BERT-family, RoBERTa-family, DeBERTa-family); encoder-decoder models (e.g., T5-family, FLAN-family); state-space
models (e.g., Mamba, S4, Hyena); mixture-of-experts models;
diffusion models producing categorical outputs; vision-language
and multimodal models combining text, image, audio, and/or
structured inputs; retrieval-augmented generation pipelines;
embedding-plus-nearest-neighbor classifiers; rule-plus-fuzzy-match systems; ensemble systems combining any of the foregoing;
and any future model class — generative or discriminative,
attention-based or otherwise — capable of producing a
classification with an associated confidence. Similarly, the
"ML head" protocol described in §5.10 is not limited to any
specific learning algorithm; its protocol admits any supervised,
semi-supervised, self-supervised, or few-shot learning method.

### 5.10 ML head protocol

[0060] The ML head is specified by a protocol: any object with
methods `fit(records) -> None`, `predict(input, labels) ->
MLPrediction`, and `model_version() -> str`. The preferred
embodiment ships a zero-config default: a TF-IDF vectorizer
feeding a logistic-regression classifier (via scikit-learn).
Alternative embodiments include sentence-transformer-encoded
inputs feeding a logistic head, gradient-boosted trees, or
remote inference services.

[0061] Auto feature detection. In one preferred embodiment, the
default ML head includes a `serialize_input_for_features`
function that inspects the input type and produces an appropriate
text representation: strings pass through unchanged; dictionaries
are serialized as key-value pairs separated by a visible delimiter
(e.g., "key1: value1 | key2: value2"), recursing into nested
structures; lists and tuples are space-joined element
serializations; None becomes the empty string; scalar types use
their repr; unknown types fall through to repr. This enables the
default ML head to handle typical production input shapes (ticket
dicts, request objects) without requiring explicit feature-extraction code.

### 5.11 Storage Protocol and backend implementations

[0062] The storage backend is specified by a protocol: any
object with methods `append_outcome(switch_name, record) -> None`
and `load_outcomes(switch_name) -> list`. The preferred embodiment
ships two implementations: an in-memory backend suitable for
tests and embedded deployments; and the self-rotating file-based
backend described in §5.4.

[0063] Alternative backends, each within scope of the invention,
include: SQLite (shared across multiple switches in a single
database); PostgreSQL (with a schema including the outcome
record's fields); remote object stores (S3, Azure Blob Storage,
Google Cloud Storage) with retention policies implemented via
object-lifecycle rules.

### 5.12 Optional-import adapter pattern for host integration

[0064] When the invented classification primitive is to be
integrated into a host application that may or may not have the
primitive installed — for example, an open-source project that
wishes to be "primitive-ready" without taking a hard dependency —
the invention contemplates a thin adapter module residing in the
host codebase. The adapter attempts to import the invented
primitive's public API under a try/except ImportError guard.
On successful import, the adapter's factory function instantiates
a switch; on failure, it returns None.

[0065] All host-application code that would otherwise invoke the
switch calls through thin helper functions that tolerate a None
switch (`safe_classify`, `safe_record_outcome`, etc.). These
helpers no-op when the switch is None. This pattern allows the
host application to operate identically regardless of whether
the primitive is installed — a property referred to herein as
"primitive-ready" integration.

[0066] This adapter pattern is applicable across languages
(Python as illustrated, but equally Node.js try/require, Go
build tags, Rust feature flags, etc.) and across any optional
dependency that provides classification services.

### 5.13 Telemetry hooks

[0067] The switch accepts an optional telemetry emitter object
with a single method `emit(event_name, payload) -> None`.
Classification and outcome events are emitted via this interface
to enable integration with external observability infrastructure.
Emitter exceptions are caught and ignored — telemetry failure
cannot affect the classification decision path.

[0068] The preferred embodiment ships three emitters: a null
emitter (default, zero overhead); a JSON-lines emitter that
writes to a configurable file handle; and an in-memory list
emitter (for tests). The emitter interface is extensible;
telemetry sinks implementing alternative protocols — including
but not limited to OpenTelemetry, Prometheus, StatsD, Kafka,
WebSocket streams, syslog, or application-specific backends —
may be registered without modifying the switch instance.

### 5.14 Research instrumentation

[0069] The invention includes a research-instrumentation module
that, when applied to a target classification problem, performs
the following procedure to produce a "transition curve":

1. Instantiate a switch in the RULE phase with a provided rule
   and ML head.
2. For each training example in an input stream, invoke the
   switch's `classify` method, record the outcome against ground
   truth, and call `record_outcome` on the switch.
3. At configurable checkpoint intervals, evaluate both the rule
   and the ML head (retrained on the accumulated outcome log)
   against a held-out test set. Record per-example predictions
   for both.
4. Emit one checkpoint record per interval, comprising the
   training-outcome count, rule test accuracy, ML test
   accuracy, ML-trained flag, and optionally per-example
   prediction arrays.
5. At the end of the training stream (or when a caller stops
   the runner), emit a final checkpoint.

[0070] The resulting checkpoint series characterizes the
rule-to-ML crossover — the training-outcome count at which the
ML head first exceeds the rule with statistical significance.

### 5.15 Cost-model reporter

[0071] The cost-model reporter module reads the outcome record
store of one or more switch instances and computes, per switch
and in aggregate, a decomposition of measurable technical
variables into user-configurable cost categories. Each category
is the product of a measured count drawn from the outcome record
store and a user-supplied per-unit assumption. Example
categories include:

- Migration-effort deltas: (baseline unit effort - alternative
  unit effort) x per-unit cost coefficient.
- Time-to-deployment acceleration: months-accelerated count x
  per-site per-month coefficient, conditional on whether the
  switch has reached a phase other than the initial phase
  (evidenced by at least one outcome with a non-rule source).
- Expected-failure-cost avoidance: expected-failure count x
  per-event cost coefficient x volume factor.
- External-service call-cost avoidance: (count of classifications
  not routed to an external service) x (tokens-per-call x
  price-per-token), annualized by a measured-interval scaling
  factor.

[0072] Each numeric coefficient is exposed as a user-configurable
assumption. The reporter emits the computed decomposition
together with the assumption values used, enabling the reader to
reproduce or adjust any quoted value.

### 5.16 Public API ergonomics — the `ml_switch` decorator

[0073] The invention's most common integration pattern is the
`ml_switch` decorator, which wraps an existing classifier
function:

```python
@ml_switch(
    labels=["bug", "feature_request", "question"],
    author="@triage:support",
    config=SwitchConfig(phase=Phase.RULE),
)
def triage(ticket: dict) -> str:
    if "crash" in ticket.get("title", "").lower():
        return "bug"
    if ticket.get("title", "").strip().endswith("?"):
        return "question"
    return "feature_request"
```

[0074] The decorated function remains callable with its original
signature; the Learned-Switch machinery is attached as attributes
(`triage.switch`, `triage.phase()`, `triage.record_outcome(...)`,
`triage.status()`), permitting introspection and outcome
recording without changing the calling convention.

## 6. STATIC + DYNAMIC ANALYZER DETAILED DESCRIPTION

### 6.1 Pipeline overview

[0075] Referring to FIG. 7, the analyzer operates in three
pipeline stages: static analysis, optional dynamic instrumentation,
and savings projection.

### 6.2 Static analysis stage

[0076] The static analysis stage operates on a target codebase
directory. For each source file in the codebase, the analyzer
parses the file into an abstract syntax tree (AST), walks the
tree, and applies the pattern library to identify classification
decision points. A pattern match produces a candidate-site record
comprising: file path, line range, inferred label set (harvested
from string literals in return statements), inferred label
cardinality, a regime classification (low/medium/high-cardinality),
and a preliminary fit-score.

### 6.3 Pattern library

[0077] The pattern library is a set of AST-matchers. Each matcher
detects a specific syntactic shape commonly indicative of a
classification decision point. Patterns include:

- **Pattern P1 — if-elif-else with string returns.** A function
  body consisting primarily of an `if` statement (with or without
  `elif` branches and a terminal `else`) whose branches each end
  in `return <string-literal>`.
- **Pattern P2 — match-case string dispatcher.** A function body
  consisting of a `match` statement whose cases return string
  literals.
- **Pattern P3 — dict-lookup dispatcher.** A function body that
  performs `dict[key]` on a function-local dict comprising
  string-literal keys and string-literal values.
- **Pattern P4 — keyword scanner.** A function body that iterates
  over a tuple of string literals, checks `if <str> in input`,
  and returns a label.
- **Pattern P5 — regex dispatcher.** A function body invoking
  `re.match` / `re.search` on one or more pattern literals and
  returning labels based on which pattern matched.
- **Pattern P6 — LLM-prompted classifier.** A function body that
  constructs a prompt string, invokes an LLM completion or
  message API, and parses the response to a label.
- **Pattern P7 — rule-tree classifier.** A recursive conditional
  structure whose leaves are string-literal labels.

[0078] Each pattern is extensible; new patterns may be added to
the library without modifying the analyzer's pipeline stages.

### 6.4 Dynamic instrumentation stage

[0079] When invoked in dynamic mode, the analyzer applies a
measurement-only wrapper to each identified candidate site. The
wrapper intercepts each call to the wrapped function, records
the call volume, input shape summary (e.g., input string length,
dict key set hash), output value, output distribution (running
histogram), and, if provided by the caller, an outcome signal.

[0080] The wrapper is architecturally non-invasive: it executes
the original function body to completion and captures the
return value, then records the measurement after the return.
Measurement failures do not propagate. The wrapper can be applied
in production environments without behavioral risk.

[0081] After a configurable measurement window (typically 24-72
hours of production traffic), the dynamic-stage output is a set
of per-site measurement records.

### 6.5 Savings projector

[0082] The savings projector combines static findings, dynamic
measurements, and the reference cost model. For each site:

- Engineering savings are computed using site-independent assumptions.
- Time-to-ML acceleration is adjusted per site based on the
  measured call volume (higher volume -> earlier crossover).
- Regression avoidance is adjusted per site by volume.
- Token-cost savings are computed per site as (measured call
  volume) x (expected fraction routed through rule/ML) x
  (per-call token cost).

### 6.6 Report generation

[0083] The analyzer emits two output artifacts:

- **Machine-readable structured output** (illustrated as JSON in
  the preferred embodiment): a structured document comprising
  the per-site findings, projected savings with decomposition,
  and the reference cost model used. Suitable for continuous-integration pipelines to diff across pull requests. Alternative
  machine-readable formats — including but not limited to YAML,
  Protocol Buffers, Apache Parquet, XML, CBOR, or custom binary
  encodings — are expressly contemplated and interchangeable
  without affecting the scope of the analyzer invention.
- **Human-readable report** (illustrated as Markdown in the
  preferred embodiment): a ranked report sorted by projected
  annual savings, including per-site summaries and a portfolio-level total. Alternative human-readable formats — including
  but not limited to HTML, PDF, reStructuredText, AsciiDoc, plain
  text, or terminal-rendered output with ANSI styling — are
  expressly contemplated and interchangeable without affecting
  the scope of the analyzer invention.

### 6.7 Integration with CI/CD

[0084] The analyzer is designed to be invocable from a CI/CD
pipeline. A single command of the form `analyze <repo-path>
[--format <fmt>] [--output OUTPUT]` runs the static stage and
emits the structured artifact in a configurable format. In the
illustrative embodiment, a `--json` convenience flag is provided
equivalent to `--format json`. The dynamic
stage is run as a separate step in the CI environment or in
production, with measurements attached to a later run of the
savings projector.

### 6.8 Privacy and confidentiality

[0085] The static-analysis stage does not emit source code
content to any external service; it emits only aggregated
findings (file paths, line ranges, label sets). The dynamic
measurement-only wrapper records statistical summaries only (call
volume, input shape hashes) unless the operator explicitly opts
into richer capture. This design preserves source-code
confidentiality for adopters.

## 7. APPLICATIONS AND USE CASES

### 7.1 General production classification

[0086] The invention applies to any production classification
decision point as characterized in §2.1. Specific applications
include:

- Customer-support ticket triage.
- Conversational-intent routing.
- Content moderation.
- Clinical diagnostic coding.
- Fraud and anomaly detection.
- Security-information and event-management (SIEM) alert triage.
- E-commerce taxonomy assignment.
- Legal-document classification.
- Application-log analysis and incident triage.
- Retrieval-strategy selection for search and retrieval-augmented
  generation (RAG) systems.
- Tool / agent routing within LLM-agent frameworks.
- Tax and regulatory transaction coding.

### 7.2 LLM output safety / moderation

[0087] A particularly important application is the classification
of LLM-generated output before delivery to users. In this
application, the invention's rule layer implements regular-expression-based PII detection, a blocklist-based toxicity rule,
and marker-based confidential-content detection. Graduation to
phases 1-4 brings in commodity moderation APIs (Perspective,
OpenAI Moderation) and eventually in-house ML heads trained on
organization-specific incident-labeled outputs.

[0088] In the preferred configuration for this application,
LLM-output safety classifiers are designated safety-critical
per §3.6 — whether through the boolean `safety_critical`
attribute or through any of the pluggable safety-critical
policies described in §13.33 — so that the invention's
construction-time check ensures the classifier never reaches
ML_PRIMARY and the rule-based floor remains the contract.
Whether a given deployment treats its LLM-output safety
classifier as safety-critical is an operator-configurable
decision; the invention contemplates and supports both postures.

### 7.3 Security-incident mitigation

[0089] The invention's architectural properties map to specific
security-incident prevention:

- **Prompt-injection resilience.** The rule's decision cannot
  be altered by prompt injection against the LLM shadow, because
  the rule is code (not a prompt) and its output is determined
  before the LLM is invoked.
- **Safety-critical authorization invariants.** Authorization
  classifiers (export-control, role-based, data-sensitivity)
  cannot graduate to pure-ML decision-making due to the
  construction-time cap.
- **Silent ML regression detection.** Outcome log comparison
  between ML output and rule output reveals silent regression;
  the statistical transition gate prevents re-graduation until
  the regression is resolved.
- **Audit-trail completeness.** Every classification decision
  is captured with its full provenance (rule output, LLM output,
  ML output, confidence, source, timestamp).
- **Adversarial shadow degradation resilience.** A shadow
  classifier that fails (by exception, timeout, or adversarial
  input) cannot block, delay, or contaminate the decision-maker's output, by virtue of the shadow-isolation invariant.

## 8. EXPERIMENTAL SUPPORT FOR THE TECHNICAL-IMPROVEMENT CLAIMS

[0090] Measurements on a reference implementation of the
preferred embodiment, on commodity hardware, support the
technical-improvement claims of §2.2 [0004]. Measurements
herein are empirical support for the invention's claimed
properties, not limitations on the claimed subject matter.

### 8.1 Transition-curve measurements

[0091] The reference implementation was evaluated against four
public intent-classification benchmarks: Banking77 (77 intents),
CLINC150 (151 intents with out-of-scope), HWU64 (64 intents,
multi-scenario), and ATIS (26 intents, flight-booking narrow
domain). Rules were constructed automatically from the first 100
training examples via a top-5-distinctive-keywords-per-label
extraction; the ML head was TF-IDF + logistic regression;
training was streamed one example at a time with checkpoint
evaluation against held-out test sets.

[0092] **Transition depths measured (p < 0.01, paired McNemar):**

| Benchmark | Labels | Rule acc | ML @ transition | ML final | Transition depth |
|---|---:|---:|---:|---:|---:|
| ATIS      | 26  | 70.0% | 75.6% | 88.7% | <= 250 outcomes |
| HWU64     | 64  |  1.8% | 10.5% | 83.6% | <= 1,000 outcomes |
| Banking77 | 77  |  1.3% |  8.8% | 87.8% | <= 1,000 outcomes |
| CLINC150  | 151 |  0.5% |  7.9% | 81.9% | <= 1,500 outcomes |

[0093] Two regimes emerged: "narrow-domain rule-viable"
(ATIS, ~70% rule floor, ML catches up with ~19pp final gap) and
"high-cardinality rule-doomed" (other three, <7% rule,
gap >80pp). Seed-size sensitivity at 10x (500 training examples
in the rule-construction window instead of 100) moved the rule
ceiling by <= 6 percentage points — the two-regime finding is
robust to rule-construction thoroughness.

### 8.2 Latency measurements

[0094] **Measured per-call latency (p50, over 5000+ samples):**

| Path | p50 latency | Relative to rule |
|---|---:|---:|
| Bare rule function | 0.12 us | 1x |
| Real ML head (TF-IDF + LR on ATIS) | 105 us | 868x slower |
| Dendra switch at RULE | 0.62 us | 5x overhead |
| Dendra switch at ML_WITH_FALLBACK | ~110 us | ML-dominated |
| Local LLM (llama3.2:1b, Ollama) | ~250 ms | ~2,000,000x slower |

[0095] Dendra's phase-routing overhead (0.5 us over bare rule)
is negligible on any production hot path. The invention thus
preserves rule-function latency characteristics while adding
outcome logging, phase-state machinery, safety cap enforcement,
and circuit-breaker logic.

### 8.3 Security-benchmark measurements

[0096] **Jailbreak-corpus rule-floor preservation:** 20 injection
patterns drawn from publicly-known categories (direct override,
nested smuggling, role reversal, encoding tricks, authority
spoof, Unicode homoglyph attacks, DAN-style, tool-poisoning,
etc.); 100% rule-floor holds under LLM_SHADOW phase even when
the shadow LLM was configured to return the attacker-desired
label with 99% confidence.

[0097] **PII-detection rule-floor recall:** 25-item corpus (SSN,
phone, email, credit card, passport, AWS key, JWT, Bearer token,
MRN, ICD-10, IBAN, DOB, and safe negatives); 100% recall, 100%
precision in the reference implementation.

[0098] **Toxicity-detection rule-floor precision:** 10-item
corpus (5 toxic, 5 safe); 100% precision.

[0099] **Adversarial-shadow latency:** shadow LLM configured to
hang for 5 ms then raise TimeoutError; end-to-end classify latency
remained under 50 ms at p95 across 50 calls, demonstrating that
the decision path is not blocked by shadow-classifier failures.

[0100] **Circuit-breaker stress:** 100 consecutive ML exceptions
trigger exactly one ML invocation (the first), subsequent 99
calls bypass the ML head entirely and route to rule-fallback;
breaker remains tripped until explicit reset.

## 9. ALTERNATIVE EMBODIMENTS

### 9.1 Multi-label extension

[0101] A straightforward extension permits the rule, LLM, and ML
head to return a set of labels rather than a single label. The
outcome record stores the full label set (serialized as a sorted,
plus-joined string in one embodiment). Statistical transition
gates operate on Hamming distance or Jaccard similarity between
predicted and ground-truth label sets.

### 9.2 Non-Python implementations

[0102] The invention is language-agnostic. Alternative embodiments
in Rust, Go, TypeScript, Java, and C# follow the same architecture
with language-idiomatic expressions of the protocol interfaces.
Each such implementation falls within the scope of the invention.

### 9.3 Alternative statistical tests

[0103] While McNemar's exact test is the preferred embodiment,
alternative statistical tests may substitute, including Wilson
score interval comparison, bootstrap resampling over paired
predictions, Bayesian posterior comparison with a beta prior,
and sequential-analysis stopping rules. Each enables the same
architectural guarantee (bounded regression probability).

### 9.4 Alternative ML backbones

[0104] The preferred embodiment uses TF-IDF + logistic regression
as the default ML head. Alternatives include: sentence-transformer embeddings + linear classifier; gradient-boosted
trees; shallow transformer fine-tunes; ensemble voting; ONNX-exported production models from any of these.

### 9.5 Distributed / federated deployment

[0105] In a federated deployment, multiple switch instances
running at different institutions contribute anonymized outcome-pattern signatures to a shared aggregation layer. The aggregation
layer computes cross-institutional priors on transition depth
as a function of dataset attributes (label cardinality,
distribution stability, outcome-quality). Each institution's
new site benefits from the federated prior. The outcome-pattern
signatures are designed to leak no raw data; only aggregate
statistics cross institutional boundaries.

### 9.6 Hardware acceleration

[0106] In embedded or edge deployments, the rule path can be
compiled to machine code (via ahead-of-time compilation or just-in-time specialization). The outcome log can be shipped via
delta-sync to a cloud aggregator. The ML head can be exported
to ONNX and run on edge TPUs or NPUs.

## 10. INDUSTRIAL APPLICABILITY

[0107] The invention is applicable to any production software
system containing classification decision points (§2.1).
Classification-site density varies widely by software domain
and organization, and the invention scales from single-instance
deployments to deployments across many instances without
alteration of the architectural properties of §3.

## 11. CLAIM CONCEPTS (non-limiting, for utility-conversion drafting)

[0108] The following claim concepts are provided to guide
utility-application claim drafting and are intended to establish
priority for subject matter within scope, without limiting claim
breadth at the utility stage.

### 11.1 Method-claim concepts (functional, for utility conversion)

The following claim concepts are deliberately narrow at the
independent level (to facilitate fast examination) while using
functional terminology defined in §15 so that dependent claims
and continuations can reach broader scope without enablement
objections.

**CC-1. A computer-implemented method comprising:**

   (a) providing a switch instance (§15 [0198]) configured with
       a phase from a plurality of ordered phases of cardinality
       at least two;
   (b) for each classification request, routing the request
       among a plurality of classifier tiers (§15 [0196])
       including at least a deterministic rule tier and at least
       one learned tier, according to the switch's current phase,
       such that in one phase the rule tier is the decision-making tier and in at least one other phase a learned
       tier is the decision-making tier;
   (c) recording each classification event to an outcome record
       store (§15 [0199]) having bounded retention;
   (d) gating phase advancement on an evidence-based criterion
       (§15 [0200]) drawn from the outcome record store;
   (e) architecturally enforcing a safety-floor invariant (§15
       [0201]) preventing the highest-autonomy phase when a
       safety-critical attribute is set;
   (f) upon detecting failure of the highest-autonomy classifier
       tier, routing classifications to the rule tier and
       persisting that routing pursuant to a configured recovery
       mechanism (§15 [0202]); and
   (g) maintaining shadow-path isolation (§15 [0203]) such that
       observational classifier invocations cannot affect the
       user-visible decision.

**CC-2.** The method of CC-1 wherein the evidence-based
criterion of (d) is a paired-proportion hypothesis test at a
configurable one-sided significance level.

**CC-3.** The method of CC-1 wherein the plurality of ordered
phases comprises six ordered phases (RULE, LLM_SHADOW,
LLM_PRIMARY, ML_SHADOW, ML_WITH_FALLBACK, ML_PRIMARY) with the
routing semantics described in §3.2.

**CC-4.** The method of CC-1 wherein the outcome record captures
shadow-observed outputs of classifier tiers not serving as the
decision-making tier.

**CC-5.** The method of CC-1 wherein the bounded retention of
(c) is achieved by size-triggered segment rotation with segment-count-based retention, wherein total storage is bounded by the
configured segment size times the retention count.

**CC-6.** The method of CC-1 wherein the architectural
enforcement of (e) occurs at construction time of the switch
instance.

**CC-7.** The method of CC-1 wherein the recovery mechanism of
(f) requires an operator-supplied reset signal.

**CC-8.** The method of CC-1 wherein the input is an output
produced by a large language model, the label set comprises
categories characterizing the output safety including at least
"safe" and one of "PII", "toxic", "confidential", "fabricated",
and the safety-critical attribute is set.

**CC-9.** The method of CC-1 wherein the switch instance, the
rule tier, the learned tiers, and the outcome record store are
distributed across a plurality of computational nodes
coordinated by a message bus, a workflow orchestrator, or an
equivalent.

**CC-10.** The method of CC-1 wherein the probability that any
permitted phase transition produces a classifier whose mean
accuracy is worse than the rule tier's mean accuracy on the
post-transition distribution is bounded above by the one-sided
significance level of the evidence-based criterion.

### 11.2 System-claim concepts

CC-S1. A computer system comprising a processor, memory, and
instructions implementing the method of CC-1.

CC-S2. The system of CC-S1 further comprising a telemetry
interface emitting per-classification and per-outcome events to
an external observability service.

### 11.3 CRM-claim concepts

CC-CRM1. A non-transitory computer-readable medium storing
instructions which, when executed by a processor, cause the
processor to perform the method of CC-1.

### 11.4 Analyzer-claim concepts

CC-A1. A method of identifying and quantifying classification
decision points in a production codebase, comprising: parsing
source files to produce abstract syntax trees; applying a stored
pattern library to identify sites matching any of a set of
syntactic shapes characterizing classification decision points;
for each identified site, inferring a label set from string
literals, a label cardinality, and a regime classification;
optionally instrumenting each site with a non-invasive
measurement wrapper; and projecting per-site annual savings by
combining static findings, dynamic measurements, and a reference
cost model comprising at least engineering-cost, regression-cost,
and token-cost ranges.

CC-A2. The method of CC-A1 wherein the pattern library comprises
at least patterns for if-elif-else string dispatchers, match-case
dispatchers, keyword scanners, regular-expression dispatchers,
LLM-prompted classifiers, and rule-tree classifiers.

CC-A3. The method of CC-A1 wherein the reference cost model
comprises at least: a parameterized migration-effort coefficient
tied to an engineering-time measurement, an expected-failure-cost coefficient tied to an event count, and a per-call
external-service cost coefficient computed from a token count
and a per-token price; and wherein the per-site projection
emits each coefficient value alongside the computed figure.

## 13. ADDITIONAL EMBODIMENTS AND SCOPE EXTENSIONS

[0109] The foregoing description is deliberately non-limiting.
This section enumerates additional embodiments and variations,
each described so as to establish priority under 35 USC 119(e)
while preserving the option to claim any subset narrowly at the
utility-application stage. Hedging phrases ("in one embodiment,"
"alternatively," "including without limitation," "in a further
embodiment") are used throughout.

### 13.1 Extended classifier-tier set

[0110] In one embodiment, the decision-making chain additionally
includes a **deterministic-lookup tier** situated between the
rule function 120 and the LLM classifier 130; the deterministic-lookup tier consults a content-addressed cache of previously-classified inputs and returns a cached label with high confidence
when an exact or near-exact match is found. In an alternative
embodiment, the chain additionally includes a **retrieval-augmented tier** that searches a vector index of previously-classified inputs and returns the label of the nearest neighbor
when its similarity score exceeds a configured threshold.

[0111] In a further embodiment, the LLM classifier 130 is itself
composed of a plurality of underlying models operating as an
ensemble, with the plurality's output determined by majority vote,
by weighted average of confidence scores, or by a learned gating
function. In yet another embodiment, the ML head 140 is an
ensemble of a plurality of base learners.

[0111a] The phase-name shorthand "LLM_*" and "ML_*" is not
limited to the specific model families those names connote in
the preferred embodiment. Alternative embodiments substitute,
for the intermediate probabilistic tier (phases LLM_SHADOW and
LLM_PRIMARY), any of the model classes enumerated in §5.9 [0059a]
— including but not limited to small language models,
encoder-only masked-language models, encoder-decoder models,
state-space models, mixture-of-experts models, diffusion models
producing categorical outputs, vision-language or multimodal
models, retrieval-augmented pipelines, and hybrid ensembles.
Alternative embodiments similarly substitute, for the trained-classifier tier (phases ML_SHADOW, ML_WITH_FALLBACK, ML_PRIMARY),
any supervised, semi-supervised, self-supervised, few-shot,
active-learning, online-learning, or reinforcement-learning
trained classifier regardless of underlying architecture. The
phase-routing semantics, the statistical transition gate, the
safety-critical cap, and the shadow-phase isolation properties
apply without modification when any such substitution is made.

### 13.2 Extended phase set

[0112] Alternative embodiments include additional operational
phases beyond the six-phase enumeration, including without
limitation: a RULE_CACHE phase (rule plus deterministic-lookup
cache in front); an LLM_ENSEMBLE_SHADOW phase (multiple LLMs
observing in parallel with disagreement metrics as part of the
outcome record); an ML_PRIMARY_WITH_LLM_FALLBACK phase (ML
decides when confident; LLM rather than rule serves as the
fallback); and a HYBRID_PRIMARY phase (a learned gating function
selects among rule, LLM, and ML at decision time).

[0113] In a further embodiment, the phase set is itself
user-configurable: the invention contemplates a plugin interface
by which an application author defines a custom phase, including
the classifier-invocation order, the fallback policy, and the
confidence-threshold behavior. The statistical transition gate
applies uniformly across custom phases.

### 13.3 Extended input modalities

[0114] In one embodiment, the input to the switch is a text
string; in alternative embodiments, the input is of any of the
following forms: a structured record (dictionary or similar
key-value container); a tuple or list of heterogeneous
components; an audio-transcript representation; an image
representation reduced to a feature vector via an image
encoder; a video-frame-sequence representation similarly reduced;
a multi-modal record combining any of the foregoing; a time-series of observations; a graph-structured input (e.g., a code
AST, a knowledge-graph subgraph); or a protocol-buffer, JSON,
XML, or binary serialized record.

[0115] The feature-extraction layer (§5.10 [0061]) dispatches on
input type and applies an appropriate encoding; this dispatch is
itself extensible and new encoders can be registered at runtime.

### 13.4 Extended label outputs

[0116] In one embodiment, the output label is a string drawn from
a fixed finite set; in alternative embodiments, the output is any
of the following: a multi-label set (subset of the fixed label
set); a hierarchical label (path through a taxonomy tree); a
structured label (string plus metadata); a ranked list of top-k
labels with confidences; a span (identifying a sub-region of the
input), optionally accompanied by a classification of that span;
a rewriter output (the input transformed according to the
classification); a refusal output (a structured "decline"
response with a reason code).

### 13.5 Extended statistical tests

[0117] In one embodiment, the statistical transition gate uses
McNemar's exact one-sided test; in alternative embodiments the
gate uses any of the following, without limitation: Wilson score
interval comparison; bootstrap resampling over paired per-example
predictions; Bayesian posterior comparison with beta or
Dirichlet priors; sequential-probability-ratio tests (Wald's
SPRT); group-sequential designs with alpha-spending functions;
permutation tests; cross-validated paired-difference tests
(e.g., 5x2 cv paired t); and ensemble-of-tests where multiple
statistical procedures must agree before advancement is permitted.

### 13.6 Extended storage backends

[0118] In one embodiment, outcome records are stored in a
self-rotating file-based JSONL log; in alternative embodiments,
outcomes are persisted in any of the following, without
limitation: SQLite databases indexed by switch name and
timestamp; PostgreSQL with time-partitioned tables; remote object
stores (Amazon S3, Google Cloud Storage, Azure Blob Storage)
with object-lifecycle rules enforcing retention; append-only
columnar stores (Apache Parquet with date-partitioning); Kafka
topics with time-based retention; blockchain or distributed-ledger persistence (providing a cryptographically tamper-evident
audit log); or content-addressable distributed storage (IPFS-style).

### 13.7 Cryptographic provenance

[0119] In one embodiment, each outcome record includes a Merkle-style hash linking it to its predecessor, producing a tamper-evident audit chain. In a further embodiment, each record
additionally includes a cryptographic signature produced by a
principal-identity key (e.g., Ed25519), binding the record to
an authenticated author identity. In yet another embodiment, the
chain is periodically anchored to a public ledger or notary
service, producing external tamper-evident timestamps.

### 13.8 Automatic threshold calibration

[0120] In one embodiment, the confidence threshold of §5.3 is a
fixed value configured at construction; in an alternative
embodiment, the threshold is automatically calibrated over time
based on outcome observations, using any of: Platt scaling,
isotonic regression, temperature scaling, or conformal
prediction. The adaptive threshold may be distinct per phase,
per label, or per input-shape cluster.

### 13.9 Drift detection and auto-revert

[0121] In one embodiment, the system includes a drift detector
that monitors the rolling accuracy of the current decision-maker
against the outcome log and, upon detecting a decrease that
exceeds a configurable threshold (e.g., 5 percentage points over
a sliding window), automatically reverts the switch to the
previous phase. The reverted state persists until either a
statistical gate passes re-advancement or an operator issues an
explicit override. In a further embodiment, the drift detector
uses a CUSUM (cumulative sum) test, a Page-Hinkley test, an
ADWIN sliding-window adaptive detector, or a Kolmogorov-Smirnov
test on feature-distribution shift.

### 13.10 Federated deployment and cross-institutional learning

[0122] In one embodiment, a plurality of switch instances
operating at different institutional deployments contribute
anonymized outcome-pattern summaries (§15 [0205]) to a shared
aggregation layer, which computes cross-institutional priors on
transition depth as a function of dataset attributes (label
cardinality, distribution stability, outcome-quality, outcome-latency). Each institution's new-site deployment benefits from
the federated prior. In an alternative embodiment, federated
learning of the ML head itself is performed, with outcome
records remaining local to each institution and only parameter
updates being aggregated.

### 13.11 Hardware acceleration and edge deployment

[0123] In one embodiment, the rule function 120 is compiled ahead-of-time to machine code using a static compiler, resulting in
sub-microsecond evaluation; in an alternative embodiment, the rule
is JIT-compiled to native code at first invocation. In a further
embodiment, the ML head 140 is exported to an inference-optimized format (including without limitation ONNX, TensorFlow-Lite, Core ML, OpenVINO) and deployed on an edge device (mobile
phone, embedded MCU, FPGA, TPU, NPU), while the outcome log is
synchronized to a central aggregator over a delta-sync protocol.

### 13.12 Cross-language reference implementations

[0124] The invention is language-agnostic. Equivalent
implementations in any of the following programming languages,
without limitation, fall within scope: Python, Rust, Go,
TypeScript, JavaScript, Java, Kotlin, Swift, C#, C++, Ruby, PHP,
Elixir, Scala, Clojure. Each language implementation is
permitted to use language-idiomatic constructs (e.g., Rust
traits, Go interfaces, Java abstract classes, TypeScript
structural types) to express the protocol interfaces described
herein.

### 13.13 Multi-tenant hosted deployment

[0125] In one embodiment, a plurality of switch instances is
hosted by a multi-tenant service provider; each tenant's
switches and outcome logs are isolated from one another by
cryptographic access controls applied at the storage layer; the
service exposes a network API (REST, gRPC, or equivalent) for
classification and outcome-recording operations; and, subject to
tenant opt-in, anonymized outcome-pattern summaries (§15 [0205])
are aggregated across tenants to compute cross-tenant priors for
transition-depth prediction. In an alternative embodiment, the
service is deployed on a tenant's own infrastructure with
optional outbound telemetry.

### 13.14 Deep integration with observability platforms

[0126] In one embodiment, the telemetry emitter (§5.13)
produces events in OpenTelemetry format suitable for ingestion by
any OpenTelemetry-compatible backend (including without limitation
Datadog, New Relic, Honeycomb, Splunk, Elastic Observability,
Grafana Tempo). In a further embodiment, the emitter additionally
produces Prometheus metrics, StatsD counters, or Sentry
performance events. A telemetry-forwarder component, running as a
sidecar process or in-process subscriber, translates classify-and outcome-events into any of the foregoing formats at the user's
choice.

### 13.15 Technical compliance specializations

[0127] In one embodiment, the invention is configured for
technical requirements that arise in regulated industries,
including without limitation: encryption-at-rest of outcome
records via a symmetric or authenticated-encryption cipher
applied at the storage layer; targeted redaction of individual
outcome records (supporting data-subject-erasure requests)
implemented by overwriting the record in place with a redacted
sentinel while preserving the segment structure; and
classification-aware handling of controlled-content outcomes in
which the outcome log of a switch whose outputs are themselves
controlled content is itself subject to the same access controls
as its outputs.

### 13.16 Explainability and post-hoc analysis

[0128] In one embodiment, the switch emits per-classification
explanations, including without limitation: a provenance chain
showing which tier decided; the LLM's self-generated reasoning
when the LLM was used; feature-importance scores for the ML head
when the ML head was used; counterfactual examples showing inputs
near the decision boundary; SHAP, LIME, or Integrated-Gradients
attributions; attention-weight visualizations for transformer-based classifiers.

### 13.17 Adversarial-robustness specializations

[0129] In one embodiment, the invention includes specific
adversarial-robustness mechanisms, including without limitation:
prompt-injection detection before LLM invocation (a classifier
that labels an input as "injection-suspicious" before dispatch);
model-poisoning detection during ML head training (an anomaly
detector over loss trajectories); backdoor-trigger scanning
(probing with synthetic inputs designed to reveal trained
backdoors); input-laundering defenses (disallowing inputs whose
encoding changes their classification).

### 13.18 Prompt-safety preconditions for LLM invocation

[0130] In one embodiment, before the LLM classifier is invoked, a
separate prompt-safety classifier (implemented itself as a
switch) classifies the prompt for risk; high-risk prompts bypass
the LLM and are routed to a more conservative tier. This
recursive use of the invention — a classification gate on the
input to another classification gate — is contemplated within
scope.

### 13.19 Analyzer extensions for additional pattern types

[0131] The static-analysis module's pattern library (§6.3) is
extensible. Additional patterns include without limitation: class-based dispatcher patterns (visitor classes with per-subclass
methods returning labels); decorator-stack patterns (functions
wrapped in one or more decorators that modify classification
behavior); macro-expanded dispatchers (in languages supporting
compile-time metaprogramming); template-specialization patterns
(C++ template specializations returning distinct labels); and
configuration-driven dispatchers (data files mapping input
features to labels, loaded at startup).

### 13.20 Analyzer integration with development tooling

[0132] In one embodiment, the analyzer is integrated with any of:
continuous-integration systems (GitHub Actions, GitLab CI,
CircleCI, Jenkins) producing diffable reports on each pull
request; code-review tools (GitHub, GitLab, Gerrit) producing
comments on lines containing identified candidate sites;
IDE plugins (VS Code, JetBrains, Emacs, Vim) producing inline
decorations over source files; and language-server-protocol
(LSP) providers offering rich hover information about each
candidate site.

### 13.21 Extensions to the reference cost model

[0133] In one embodiment, the reference cost model used by the
savings projector (§6.5) combines any of the following cost
categories, each parameterized as a ratio times a per-unit
assumption: engineering effort per migration step; expected
regression-event cost per candidate site; token cost per
classifier call (computed as token-count times external LLM-service price); and time-to-deployment value (computed as
months-accelerated times a per-site per-month coefficient).
Each category is independently includable, excludable, or
reweightable; the cost-model plugin interface accepts additional
categories registered at runtime.

### 13.22 Machine-learning training variants

[0134] In one embodiment, the ML head is trained using any of:
fully-supervised learning with gradient descent; semi-supervised
learning leveraging unlabeled examples; self-training (pseudo-labeling with confidence-based filtering); active learning
(querying a human labeler for the most-informative examples);
curriculum learning (progressive-difficulty training order);
meta-learning (learning to adapt to new label sets quickly);
reinforcement learning (outcome-as-reward); online learning
(per-example gradient updates); federated learning across
institutions (§13.10).

### 13.23 LLM-classifier variants including small models

[0135] In one embodiment, the LLM classifier is a frontier-scale
model accessed via a remote API; in alternative embodiments, the
LLM classifier is any of: a compact open-weight model served
locally; a specialized classification model fine-tuned from a
general-purpose base; a quantized model running on consumer
hardware; a distilled student model derived from a larger teacher;
a routing meta-model that selects among a plurality of underlying
models per call; or a hybrid (small-model fast path plus frontier-model slow path, with the small model's confidence gating the
choice).

### 13.24 Use for output classification and generation gating

[0136] In one embodiment, the invention is applied to classify
the output of a text-generating large language model before that
output is delivered to a user or downstream system; the
classification labels comprise at least categories such as "safe",
"pii", "toxic", "confidential", "hallucinated", "refusal",
"ambiguous", or equivalent enumerations. In a further embodiment,
the classification result determines one of: delivery unchanged;
rewrite-then-deliver (where a rewriter component transforms the
output to remove the problematic content); blocked-with-refusal;
escalation-to-human-review. In yet another embodiment, the
invention is applied recursively — the rewriter's output is itself
classified by a second switch before delivery.

### 13.25 Agent-tool routing and agent-action gating

[0137] In one embodiment, the invention is applied within an
LLM agent framework to classify, before invocation, which tool
among a plurality of registered tools an agent should call given
a task description and conversation context; the switch's labels
are tool identifiers; the rule layer implements deterministic
tool-routing heuristics (keyword-to-tool mappings); the LLM
layer parses intent; the ML layer learns from observed tool-invocation outcomes (success, failure, time-to-completion).

[0138] In a further embodiment, the invention gates agent
actions more broadly: before an agent executes any action with
side effects (filesystem write, network call, shell command),
the action description is classified by a safety-critical switch
into categories such as "safe-automatic", "safe-with-review",
"dangerous-require-human", or "blocked". The safety-critical
construction-time cap (§3.6) ensures such agent-safety gates
never graduate to ML_PRIMARY.

### 13.26 Integration with retrieval-augmented generation

[0139] In one embodiment, the invention classifies queries in a
retrieval-augmented-generation (RAG) system to select, per query,
one of a plurality of retrieval strategies (e.g., "keyword
search", "dense vector search", "hybrid", "multi-hop", "query
expansion"). The rule layer performs syntactic analysis of the
query; the ML layer learns from observed retrieval success
(click-through, downstream answer quality).

### 13.27 Non-monotonic phase transitions

[0140] In one embodiment, phase advancement is monotonic (forward-only after statistical gate passes); in an alternative embodiment,
phase regression is automatic — the drift detector (§13.9)
triggers an automatic move to an earlier phase when evidence
supports it. In a further embodiment, the system maintains a
history of phase transitions and can replay the outcome log
against any historical phase configuration to quantify
retrospective alternatives.

### 13.28 Multi-tenant switch isolation

[0141] In one embodiment, a single process hosts a plurality of
switch instances for distinct tenants (users, customers,
organizational units); outcome logs are isolated per tenant via
naming conventions and/or cryptographic access controls; phase
configuration is per-tenant; and aggregate statistics may be
computed across tenants only when tenants have opted in.

### 13.29 Data-plane / control-plane separation

[0142] In one embodiment, the switch's classify operation (the
data plane) is separated from the switch's phase-management
operations (the control plane). The data plane is optimized for
low latency; the control plane runs asynchronously and can be
served by a different process or machine from the data plane.
Phase transitions propagate from control plane to data plane via
configuration-change notifications.

### 13.30 Training-order independence

[0143] In one embodiment, the transition-depth statistic is
robust to the order in which training examples are streamed; the
research-instrumentation module (§5.14) supports training-order
permutation testing by re-running the streaming experiment with
a plurality of shuffles and reporting transition-depth
distribution statistics (mean, standard deviation, interquartile
range).

### 13.31 Benchmark-corpus generation

[0144] In one embodiment, the research-instrumentation module
additionally generates synthetic benchmark corpora for evaluating
classifier-primitive properties, including without limitation:
jailbreak-resistance corpora (prompt-injection patterns drawn
from published catalogues); PII-detection corpora (templated
synthetic PII instances across regions and formats); toxicity
corpora (curated safe/unsafe examples); compound-attack corpora
(inputs exhibiting multiple adversarial properties simultaneously).

### 13.32 Proof-of-deployment attestations

[0145] In one embodiment, a switch periodically emits a signed
attestation of its current phase, outcome-log hash, and
configuration, to an external registry; third parties may query
this registry to verify, without trusting the switch's operator,
that the switch is operating in a claimed configuration at a
claimed point in time. This mechanism supports audit and
certification workflows.

### 13.33 Extended safety-critical policies

[0145a] In one embodiment the `safety_critical` attribute
described in §3.6 is a per-switch boolean. In alternative
embodiments, the safety-critical determination is pluggable
and user-defined, including without limitation:

- A user-supplied predicate function that is evaluated at
  classification time and returns a boolean or a policy decision
  (e.g., allow / deny / escalate) for the invocation at hand.
- A label-set criterion that marks specific output labels as
  safety-critical — any classification whose candidate or final
  output falls within a designated label set is treated as
  safety-critical for the purpose of the ML_PRIMARY cap
  (§3.6).
- A confidence-based criterion under which decisions with
  estimated confidence below a configured threshold are treated
  as safety-critical, routing them through the rule floor
  regardless of phase.
- An input-classification criterion under which decisions on
  inputs matching specified properties (regular-expression,
  schema, provenance tag, tenant identifier, jurisdiction) are
  treated as safety-critical.
- A policy-engine decision under which an external policy
  engine (e.g., Open Policy Agent, Cedar, XACML, AWS IAM
  condition set, Kubernetes admission controller) returns a
  per-invocation safety-critical status consumed by the switch.
- A risk-score criterion under which a separate risk-scoring
  function (itself potentially a classifier of any tier)
  determines whether the invocation should be treated as
  safety-critical.
- A composite policy combining any of the foregoing via
  logical OR / AND / precedence composition.
- A temporal or rate-based criterion (e.g., during an active
  security incident, a regulatory freeze window, or when outcome-log anomalies exceed a rate threshold, the switch is treated
  as safety-critical for the duration of the condition).
- A multi-signer cryptographic criterion under which the
  safety-critical status can only be deasserted upon a
  threshold of distinct signers approving the change.

The construction-time cap described in §3.6 applies whenever
the safety-critical determination — by whatever means, whether
an attribute, a predicate, a policy, a score, or a composite —
evaluates to true for the switch or the invocation at hand.
The architectural invariant is that no classification treated
as safety-critical may be decided purely by an ML head; the
rule floor is always reached on any such classification.

### 13.34 Compositional multi-switch patterns

[0145b] The invention contemplates compositions of a plurality
of switches into larger classification systems. The phased-autonomy, transition-gate, and safety-cap properties are
preserved per-switch; the composition topology is additional
and does not alter the per-switch invariants. Compositional
patterns include, without limitation:

- **Hierarchical (taxonomic) composition.** A first switch
  classifies an input into a coarse category; based on the
  coarse label, one of a plurality of downstream switches is
  selected to produce a finer-grained classification. Each
  level of the taxonomy is implemented as an independent
  switch with its own phase, rule, optional LLM tier, and
  optional ML head. Taxonomy trees of arbitrary depth are
  contemplated.
- **Parallel ensemble composition.** A plurality of switches
  each classify the same input independently; their outputs
  are aggregated by majority vote, weighted confidence
  averaging, a learned gating function, a meta-classifier, or
  any equivalent aggregation rule. Individual ensemble members
  may be in different phases (e.g., one switch in RULE, another
  in ML_PRIMARY); the aggregator observes and may act on the
  phase distribution.
- **Gated-routing composition.** A router switch selects, based
  on its classification, which of a plurality of downstream
  switches to invoke for a particular input. The router may
  itself be a LearnedSwitch (graduating from a rule-based
  router to an ML router over time).
- **Cross-validation composition.** Two or more switches of
  heterogeneous architecture classify the same input; a
  disagreement-detection component compares their outputs and,
  upon disagreement, routes the input to human review, to a
  higher-authority switch, or to a quarantine outcome stream.
  Useful for authorization and safety-critical classifications
  where independent attestation is desired.
- **Cascade-fallback composition.** A primary switch classifies;
  when its confidence is below a threshold or its classification
  raises its own exception, a fallback switch (potentially of
  different model family or training corpus) is consulted.
  Multiple cascade stages are contemplated.
- **Sequential-pipeline composition.** Input passes through
  switches in sequence, each stage filtering, enriching, or
  refining the classification. For example, a PII-redaction
  switch precedes a topical-classification switch; the topical
  classifier receives the redacted input.
- **Meta-switch composition (switch-of-switches).** A higher-level switch's rule tier, intermediate tier, and trained-classifier tier are themselves entire LearnedSwitch instances,
  and the phase graduation applies not to individual models
  but to whole sub-systems. Useful for managed phased rollout
  of classifier-platform upgrades.
- **Federated-ensemble composition.** A plurality of switches
  deployed across organizational boundaries contribute
  classifications to a shared aggregator while each organization
  retains independent phase, rule, and outcome-log ownership.
  Extends §13.10 with aggregation semantics beyond pure
  training-data federation.
- **Temporal-ensemble composition.** A historical ensemble
  where past-version switches (e.g., frozen prior-generation ML
  heads) continue to shadow the current decision-maker,
  providing regression-detection signal without affecting the
  decision path.
- **Adversarial-cross-check composition.** An adversarially-trained switch classifies the same input as the primary
  switch; divergence between the two triggers anomaly flags,
  supporting adversarial-robustness monitoring.
- **Multi-modal composition.** Different switches handle
  different input modalities (text, image, audio, time-series);
  a meta-aggregator combines per-modality classifications.

In each compositional pattern, the per-switch architectural
properties (phase semantics, transition gate, safety-critical
cap, shadow isolation, outcome logging) apply unchanged. The
composition layer adds topology-specific properties (taxonomic
path consistency, ensemble calibration, router accuracy,
disagreement thresholding, cascade confidence propagation, etc.)
that are themselves contemplated as independently-patentable
novel features when combined with the per-switch invariants of
the present invention. Compositions of any of the foregoing
patterns, including nested compositions (e.g., a hierarchical
tree whose leaves are ensembles), are expressly contemplated.

---

## 14. ANTI-CIRCUMVENTION EMBODIMENTS

[0146] This section describes a plurality of implementation
variations that, while differing from the preferred embodiment
in surface structure, each practice the core invention described
above. The purpose is to establish priority for each such
variation so that a competitor cannot practice the invention
while escaping claims merely by surface rearrangement. Each
variation below is independently enabled and is contemplated
within scope.

### 14.1 Structural variations of the switch

[0147] **Single-process monolith** (preferred embodiment). The
switch, its rule function, its LLM classifier, its ML head, its
storage backend, and its telemetry emitter reside within a single
operating-system process.

[0148] **Distributed multi-service implementation.** In an
alternative embodiment, each of the rule function, LLM classifier,
ML head, storage backend, and statistical transition gate is
implemented as an independent network service (e.g., a separate
HTTP/gRPC/Thrift microservice), with a thin coordinator service
that invokes the component services in the order prescribed by
the current phase and records the outcome. The coordinator may
itself be stateless, consulting a configuration store for
current phase. All architectural properties described in §3-§5
(phase-specific routing, shadow isolation, safety-critical cap,
circuit breaker, bounded storage) apply uniformly to this
distributed form. No aspect of the invention requires that the
components co-reside.

[0149] **Workflow-orchestrator implementation.** In another
alternative embodiment, the classification pipeline is modeled as
a workflow (e.g., using Temporal, Apache Airflow, Argo Workflows,
AWS Step Functions, Dagster, Prefect, or equivalent systems); each
classifier tier is a workflow activity; the phase selector is a
control-flow decision within the workflow; and the outcome log is
written to a durable task-history store. Workflow-based
implementations practice the invention when they satisfy §3.3
(statistical transition gate), §3.5 (circuit-breaker persistence),
§3.6 (safety-critical cap), and §3.7 (shadow isolation) —
irrespective of the workflow-orchestrator product used.

[0150] **Event-driven / pub-sub implementation.** In a further
embodiment, classification requests are published to a message
bus (e.g., Kafka, RabbitMQ, NATS, AWS SNS/SQS, Google Pub/Sub,
Apache Pulsar); a plurality of subscribers processes each
request per the phase-specific routing; and outcomes are
published back as result events. Shadow-classifier outputs are
published to a separate topic for observation without feeding
into the decision topic. This implementation practices the
invention's shadow-isolation guarantee (§3.7) architecturally
via topic separation.

[0151] **Serverless / FaaS implementation.** In yet another
embodiment, each classifier tier is a serverless function (AWS
Lambda, Google Cloud Functions, Azure Functions, Cloudflare
Workers, Vercel Edge Functions); the phase selector is a thin
router function that invokes downstream functions based on
current phase; the outcome log is persisted to a managed
serverless store (DynamoDB, Firestore, Durable Objects); and
the statistical transition gate runs as a scheduled serverless
task. The aggregate is contemplated within scope.

[0152] **Embedded / single-function implementation.** In a
contrasting embodiment, the switch is implemented as a single
higher-order function (or equivalent construct in non-functional
languages) that composes the rule, LLM, and ML head via function
composition; the phase selector determines the composition at
invocation time. Example (non-limiting, Python-like pseudocode):

    def make_switch(rule, llm, ml, phase, config):
        def classify(x):
            # phase-specific composition selected here
            ...
        return classify

This is structurally distinct from the class-based preferred
embodiment but behaviorally equivalent.

### 14.2 Phase-selector variations

[0153] **Explicit enumeration** (preferred embodiment). The phase
is stored as a member of an explicit enumeration type and
transitions are method calls on the switch object.

[0154] **Configuration-file-driven phase.** In an alternative
embodiment, the phase is read from an external configuration file
(e.g., YAML, TOML, JSON, environment variable) at each
classification call or at application startup. Phase changes are
made by editing the configuration and triggering a reload. This
implementation practices the invention when the statistical gate
and the safety-critical cap are enforced at configuration-load
time.

[0155] **LLM-managed phase selection.** In a further embodiment,
the phase itself is selected by an LLM operating from a system
prompt containing the current outcome-log summary and phase
semantics; at each classification, the LLM emits both a phase
selection and a label. Such an implementation practices the
invention when the phase semantics described in §3-§5 are
respected by the LLM's prompt and when the safety-critical cap
is enforced either in the prompt or in a subsequent validation
step.

[0156] **Policy-module-driven phase.** In another embodiment,
an external policy module (e.g., Open Policy Agent, a feature-flag service like LaunchDarkly or Split.io, a policy engine
implementing the Common Expression Language) determines the
current phase based on input attributes, rollout percentages,
or business rules. The switch consults the policy module before
each classification.

[0157] **Temporally-varying phase.** In a still further embodiment,
the phase varies with input attributes, time of day, user cohort,
or request-source — for example, classifying requests from a
"pilot" customer cohort in a higher phase than the general
customer population. The transition gate evaluates per-cohort
outcome data independently. This contemplates per-slice phase
management without departing from the invention's core logic.

### 14.3 Transition-gate variations that avoid word "statistical"

[0158] The preferred embodiment uses a statistical hypothesis
test (McNemar's exact test, §5.5). Alternative embodiments use
other criteria, each of which practices the invention's core
property of a "gated transition based on observed evidence":

[0159] **Accuracy-margin criterion.** In one alternative, the
transition gate requires the candidate classifier's observed
accuracy to exceed the decision-maker's accuracy by at least a
configured margin (e.g., 2 percentage points). This lacks a
p-value but achieves the same goal.

[0160] **Win-rate criterion.** In another, the gate requires the
candidate classifier to win more head-to-head per-example
comparisons than the decision-maker over a minimum evidence
window.

[0161] **Manual-operator-approved criterion.** In a further
embodiment, the gate requires explicit human approval after
reviewing an outcome-log summary. No automated test is applied;
the human's judgment is the gate.

[0162] **Bayesian-posterior criterion.** Per §13.5, the gate can
require that the posterior probability of candidate > decision-maker exceed a configured threshold (e.g., 0.99) under a stated
prior.

[0163] **Cost-weighted expected-value criterion.** The gate
computes E[candidate] - E[decision-maker] under a user-provided
cost function, and advances when the expected-value delta is
positive by more than a configured threshold.

[0164] Each of the foregoing is contemplated within scope. A
competitor cannot escape the invention by substituting any
evidence-based graduation criterion for a specifically-named
statistical test.

### 14.4 Storage and rotation variations

[0165] Per §13.6 and §13.7, outcome persistence can take any of
a wide variety of forms. Two specific rotation variations
additionally covered:

[0166] **Time-based rotation.** In one alternative, segments
are rotated at time boundaries (hourly, daily, weekly) rather
than size boundaries. Retention is measured in segments-of-time.

[0167] **Log-compaction rotation.** In another, the log is
compacted (duplicate-input entries collapsed to their most
recent record) rather than rotated by size. Compaction produces
the same bounded-storage property as size-based rotation.

### 14.5 Safety-critical enforcement variations

[0168] The preferred embodiment refuses construction when
`safety_critical = True` and `phase = ML_PRIMARY` (§5.7). Alternative
embodiments enforce the same invariant at other points:

[0169] **Runtime validation on phase transition.** In one
alternative, the construction permits any initial phase, but the
phase-transition method rejects any transition into ML_PRIMARY
when `safety_critical = True`. Semantically equivalent to
construction-time refusal for any switch that starts below the
cap.

[0170] **Static-analysis enforcement.** In another, a pre-deployment static-analysis check (lint rule or CI check) fails
the build when a switch is configured as `safety_critical = True`
and its phase is `ML_PRIMARY`. The check runs before any runtime
use of the switch.

[0171] **Policy-engine enforcement.** In a further embodiment, a
policy engine rejects phase configurations at the configuration-store layer, before any application reads the configuration.

[0172] **Cryptographic enforcement.** In yet another, the
safety-critical attribute is cryptographically signed by a
supervising authority and the signature becomes invalid under
phase-ML_PRIMARY configurations, making such configurations
unusable.

### 14.6 Circuit-breaker variations

[0173] The preferred embodiment persists the tripped state until
explicit operator reset (§5.6). Alternative embodiments include:

[0174] **Time-based automatic reset.** After a configurable quiet
period, the breaker attempts automatic recovery. This is a
different policy choice but employs the same core mechanism
(detect ML failure -> route to safety floor).

[0175] **Half-open probe recovery.** Per §5.6 [0053], the breaker
enters a "half-open" state, attempts a single ML call, and
resumes normal operation on success or re-trips on failure. This
is a widely-known circuit-breaker variant (commonly attributed
to Michael Nygard's *Release It!* and popularized by Netflix
Hystrix), and its application in this context — specifically as
the safety-floor mechanism of the graduated-autonomy primitive's
highest phase — is contemplated within scope.

[0176] **Gradual traffic bleeding.** After the breaker trips,
traffic is gradually returned to the ML path as recovery
succeeds (e.g., 1% of traffic, then 10%, etc.). This is a
canary-style recovery policy built atop the breaker mechanism.

### 14.7 Shadow-path variations

[0177] The preferred embodiment runs shadow classifiers inside
the same classify() call with error-swallowing (§5.8).
Alternative embodiments include:

[0178] **Asynchronous shadow evaluation.** Shadow classifiers
are invoked on a separate thread, process, or background queue;
the primary decision is returned immediately; shadow results
correlate back to the outcome record via an identifier. This is
contemplated within scope when the correlation eventually
produces the same outcome-record fields as the preferred
embodiment.

[0179] **Sampled shadow evaluation.** Shadow classifiers are
invoked on a random sample (e.g., 10%) of requests rather than
all requests, reducing observational cost. The statistical gate
uses sampling-aware corrections.

### 14.8 Ensemble and hybrid decision-makers

[0180] The preferred embodiment has exactly one decision-maker at
a time per phase. Alternative embodiments include:

[0181] **Ensemble at a phase.** In one alternative, the ML_PRIMARY
phase uses an ensemble of ML heads rather than a single head;
the ensemble vote determines the label and an aggregated
confidence determines breaker behavior. The ensemble is treated
as a single logical ML head for §3 and §5 purposes.

[0182] **Interpolated decision at a phase.** In another, the
classification at LLM_PRIMARY or ML_PRIMARY phases is a weighted
combination of the tier's output and the rule's output, with the
weight determined by confidence or by a calibrated interpolation
function. Such interpolations are within scope.

[0183] **Hybrid routing per input.** In a further embodiment, the
phase effectively varies per input — easy inputs (by any
measured criterion) route to rule, harder inputs to LLM, hardest
to ML. This is a hybrid routing strategy built atop the
invention's primitive structure.

### 14.9 API-surface and naming variations

[0184] No aspect of the invention depends on any specific API
name, decorator syntax, class name, method name, or attribute
name. Without limitation, a competitor's implementation using any
of the following surface choices still practices the invention:

- `@classifier_switch`, `@learn`, `@graduate`, `@tier_switch`,
  `@evolving_classifier`, or any other decorator name, or no
  decorator at all (direct class instantiation or function
  composition).
- `ClassifierLifecycle`, `TieredClassifier`, `Evolvable`,
  `MaturingClassifier`, or any other class name for the switch.
- `classify()`, `predict()`, `decide()`, `label()`, `route()`, or
  any other verb for the classify operation.
- Phase constants named `EARLY`, `OBSERVING`, `LEARNING`,
  `CONFIDENT`, `AUTONOMOUS`, etc., or numeric constants `0..5`,
  or opaque tokens.
- `outcome`, `result`, `observation`, `record`, `label_event`,
  `feedback` — any name for the outcome record.

The invention resides in the architectural properties described
in §3-§5, not in any naming convention.

### 14.10 Label-type and signature variations

[0185] Per §13.4, labels may be strings, enumerations, spans,
multi-label sets, hierarchical paths, or structured objects. A
competitor cannot escape the invention by emitting labels of a
different type. Similarly, the classify operation may accept any
number of inputs, may accept variadic or keyword arguments, and
may return a tuple containing the label plus additional metadata;
each such signature variation is within scope.

### 14.11 Code-language and platform variations

[0186] Per §13.12, implementations in any programming language
are within scope. Additionally, implementations running on
non-standard platforms (browsers via WebAssembly; embedded
microcontrollers via C; native mobile apps; GPUs via CUDA
kernels; FPGAs via HDL; custom ASICs) are within scope when they
practice the architectural properties.

### 14.12 Training-pipeline variations

[0187] Per §13.22, training may use any supervised / semi-supervised / self-supervised / active / meta / federated regime.
Additional variations within scope:

[0188] **Training-as-a-service.** The ML head is retrained by an
external service invoked by the switch at checkpoint intervals;
the switch itself does not embed the training code. Within scope.

[0189] **Offline-batch retraining.** Training occurs in a nightly
batch job with no online retraining; the trained model artifact
is deployed at a checkpoint. Within scope.

[0190] **Continuous training with live-swap.** The ML head
retrains continuously on a side replica; atomic live-swap
promotes the replica to primary. Within scope.

[0191] **No training (pretrained-only).** The ML head is a
pretrained model that is never updated from the outcome log;
the outcome log serves only audit and transition-gate purposes.
Within scope.

### 14.13 Dependency-graph and meta-pattern variations

[0192] In one alternative embodiment, the invention's components
are realized as aspects or interceptors (AOP style) wrapping an
existing function; as middleware layers in a web framework; as
compiler plugins transforming annotated classifier functions; or
as runtime hooks installed by an IDE or language runtime. Each
is within scope.

[0193] In a further embodiment, the invention is recursive: the
classify operation is itself gated by another switch (one switch
gates the output of another). Recursive use is within scope.

### 14.14 Anti-design-around property summary

[0194] In summary, the preferred embodiment is one specific
implementation of an architectural pattern whose essential
elements are:

- A **plurality of classifier tiers** (at least rule + one
  learned component).
- A **selector** among the tiers (any form — enumeration, config,
  policy, LLM prompt, function composition).
- **Outcome logging** (any durable record of classifications and
  observed results).
- A **gated transition mechanism** between selector states (any
  evidence-based criterion — statistical, accuracy-threshold,
  human-approval).
- **A safety-floor invariant** preventing the highest-autonomy
  state under configured conditions (any enforcement point —
  construction, configuration, runtime, policy).
- **A persistent-reverted-state recovery mechanism** from the
  highest-autonomy state (any form — circuit breaker, kill
  switch, rollback, canary).
- **Shadow-path isolation** ensuring observational classifiers
  cannot affect user-visible decisions (any architectural
  separation — try/except, thread isolation, process isolation,
  topic separation).

An implementation practicing all seven elements practices the
invention, regardless of surface choices.

---

## 15. FUNCTIONAL DEFINITIONS OF KEY TERMS

[0195] This section defines key terms used in this specification
and in any later utility-application claims in functional form,
so that utility claims using these terms establish priority for
all implementations satisfying the functional description.

[0196] **"Classifier tier"** means any component that produces a
label for a given input, regardless of whether the component is
a hand-coded rule, an LLM, an ML head, a retrieval system, an
ensemble, a cache, or any other form capable of producing a
label. Whether the component is deterministic, probabilistic,
trained, or configured is immaterial.

[0197] **"Phase"** means a specific assignment, from a finite
ordered set, of routing behavior among classifier tiers for
classification requests. A phase assigns, for each request:
which tier produces the user-visible output; which tiers run in
observational mode without affecting the output; and what
fallback behavior applies on tier failure. The finite ordered
set may have any cardinality of at least two and any naming
convention.

[0198] **"Switch instance"** means any discrete unit of state
carrying at minimum: a phase, a rule tier, and an outcome log.
The unit may be an object, a closure, a service, a row in a
database, a workflow instance, a document in a configuration
store, or any equivalent state-carrying construct.

[0199] **"Outcome log"** means any durable record of tuples
comprising at minimum (input-identifier, decision-tier-output,
ground-truth-outcome-label) for a plurality of classification
events. Durability may be local disk, networked storage, a
distributed database, a blockchain, or any other persistence
mechanism. Bounded storage may be achieved by size-based
rotation, time-based rotation, compaction, or equivalent.

[0200] **"Transition gate"** means any mechanism that permits or
denies advancement between phases based on evidence from the
outcome log. The evidence-evaluation mechanism may be a
statistical test, an accuracy margin, a Bayesian posterior, a
cost-weighted expectation, an operator judgment, or any
equivalent criterion.

[0201] **"Safety-floor invariant"** means any architectural
property that prevents a switch instance from entering the
highest-autonomy phase under configured safety-critical
conditions. Architectural enforcement may occur at construction
time, at configuration-load time, at phase-transition time, via
static analysis, via policy engines, or via cryptographic
attestation.

[0202] **"Circuit-breaker-recovery mechanism"** means any
mechanism that, upon detecting a failure of the highest-autonomy
classifier, routes classification requests to a lower-autonomy
tier and persists that routing until a specified recovery
condition is met. The recovery condition may be an explicit
operator reset, a time-based automatic retry, a half-open probe,
or any equivalent.

[0203] **"Shadow isolation"** means any architectural property
ensuring that observational classifier invocations cannot
affect the user-visible decision. Isolation may be synchronous
try/except, asynchronous dispatch with out-of-band recording,
separate topic in a message bus, separate process, or any
equivalent separation.

[0204] **"Classifier-primitive-ready integration"** means any
host-application integration pattern in which the host operates
identically whether or not the classification primitive is
installed. Integration may be via optional import guards,
conditional module loading, feature flags, build-time
conditionals, runtime probing, or any equivalent.

[0205] **"Anonymized outcome-pattern signature"** (for §13.10
federated deployment) means any representation of aggregate
classification-outcome statistics that does not permit
reconstruction of individual outcome records. Acceptable forms
include count summaries, distribution histograms, differential-privacy-noised aggregates, or secure-multi-party-computation
shares.

[0206] These functional definitions are intended to bind any
later claim using these terms to the full scope of the
underlying functional property, while the preferred-embodiment
descriptions (§3-§8) provide the specific implementations
needed for enablement under 35 USC 112.

---

## 12. ABSTRACT

A graduated-autonomy classification system comprises a switch
instance operating in one of six ordered phases (RULE, LLM_SHADOW,
LLM_PRIMARY, ML_SHADOW, ML_WITH_FALLBACK, ML_PRIMARY), routing
each classification request to a rule function, an LLM, or an
ML head per phase-specific semantics, recording each outcome
to an append-only log with automatic size-bounded rotation, and
permitting phase advancement only when a paired-proportion
statistical test rejects a null hypothesis of equal-or-worse
performance at a configured significance level. A safety-critical attribute refuses switch construction in the highest
phase, protecting authorization-class decisions. A circuit
breaker in the highest phase reverts routing to the rule upon
ML-head failure and persists until explicit operator reset.
Shadow-phase classifiers are architecturally isolated from the
decision path. A companion static-and-dynamic analyzer identifies
classification decision points in a target codebase, applies
non-invasive measurement, and projects per-site annual savings
using a transparent, ratio-decomposable reference cost model.
The invention is applicable to customer-support triage,
conversational-intent routing, content moderation, clinical
coding, fraud detection, security alert triage, RAG retrieval-strategy selection, agent tool routing, tax/compliance coding,
and LLM-output safety classification — the last being
particularly important because LLM-output classification is
itself a classification problem and the same primitive applies.

---

## APPENDICES

### Appendix A — Representative Python reference implementation

[The reference implementation is publicly available at
`github.com/axiom-labs-os/dendra`, licensed under Apache 2.0. All code
paths described in §5 correspond to modules at
`src/dendra/core.py`, `src/dendra/storage.py`, `src/dendra/ml.py`,
`src/dendra/llm.py`, `src/dendra/research.py`, `src/dendra/roi.py`,
`src/dendra/viz.py`, and `src/dendra/telemetry.py` of that
repository as of priority date. Unit tests are at the sibling
`tests/` directory.]

### Appendix B — Key numerical configuration defaults

- `max_bytes_per_segment`: 64 megabytes (default).
- `max_rotated_segments`: 8 (default).
- Default confidence threshold: 0.85.
- Default transition significance level alpha: 0.01.
- Default seed-window size for rule construction: 100 training examples.
- Default keywords-per-label for rule generation: 5.
- Default checkpoint interval: 250 outcomes.
- Default minimum outcomes before ML fit: 100.

### Appendix C — Correspondence between specification and reference-implementation modules

| Specification Section | Reference-Implementation Module |
|---|---|
| §3.1–§3.2, §5.2, §5.3 | `src/dendra/core.py` |
| §3.4, §5.4 | `src/dendra/storage.py` |
| §3.3, §5.5 | `src/dendra/viz.py` (statistical tests) + `src/dendra/research.py` |
| §5.9 | `src/dendra/llm.py` |
| §5.10 | `src/dendra/ml.py` |
| §5.13 | `src/dendra/telemetry.py` |
| §5.14 | `src/dendra/research.py` |
| §5.15 | `src/dendra/roi.py` |
| §5.16 | `src/dendra/decorator.py` |
| §6 (Analyzer) | `docs/marketing/business-model-and-moat.md` §2 (design);
 reference implementation deferred to follow-on release |

---

**End of provisional specification.**

*No formal claims are included — see §11 for non-limiting claim
concepts to guide utility-application drafting within 12 months
of the priority date.*

**Attachments:** USPTO Form SB/16 (cover sheet), USPTO Form
SB/15A (micro-entity declaration), drawings (FIG. 1 through
FIG. 8).

_Copyright (c) 2026 B-Tree Ventures, LLC. All rights reserved
for reduction to practice purposes. Apache 2.0 license on
reference-implementation code does not limit patent rights per
37 CFR 1.77 disclosure._
