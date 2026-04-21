# Drawings for the Dendra Provisional Patent Application

**Eight figures.** Each is described in text below plus a Mermaid
diagram source you can render at [mermaid.live](https://mermaid.live),
export as SVG, and convert to PDF for the filing.

**USPTO drawing requirements (summary):**
- Black-and-white line drawings on white background.
- Each figure on a separate page.
- Figure numbers labeled "FIG. 1", "FIG. 2", etc.
- Reference numerals cited in the specification (optional but
  standard practice).

---

## FIG. 1 — Overall system architecture

**Description:** A block diagram showing the graduated-autonomy
classification system 100, comprising a switch instance 110
mediating between a caller 102 and a decision-making chain of
rule function 120, optional LLM classifier 130, and optional ML
head 140. Configuration record 112 controls the switch. Storage
backend 150 maintains outcome log 152. Telemetry emitter 160
receives observation events.

```mermaid
flowchart TD
    classDef box fill:#ffffff,stroke:#000000,color:#000000
    classDef dashed fill:#ffffff,stroke:#000000,stroke-dasharray:4 2,color:#000000

    C[caller 102<br/>production application]:::box
    CFG[config 112<br/>phase, threshold,<br/>safety_critical]:::box
    S[switch instance 110<br/>LearnedSwitch]:::box

    C -->|classify / record_outcome| S
    CFG -.configures.-> S

    subgraph chain [classifier chain]
      direction TB
      R[rule function 120<br/>user-supplied]:::box
      L[LLM classifier 130<br/>optional]:::dashed
      M[ML head 140<br/>optional]:::dashed
    end

    subgraph obs [observability]
      direction TB
      ST[storage backend 150<br/>outcome log 152]:::box
      T[telemetry emitter 160<br/>optional]:::dashed
    end

    S -->|routes by phase| chain
    S -->|appends / emits| obs

    %% Force the two subgraphs to stack vertically rather than sit side-by-side.
    chain ~~~ obs
```

---

## FIG. 2 — Six-phase state machine

**Description:** An ordered sequence of six states {RULE,
LLM_SHADOW, LLM_PRIMARY, ML_SHADOW, ML_WITH_FALLBACK, ML_PRIMARY}.
Each forward transition is gated by a statistical test (§5.5). A
regression (backward) transition is permitted at operator
discretion. Safety-critical switches cannot enter ML_PRIMARY.

```mermaid
stateDiagram-v2
    direction TB
    [*] --> RULE
    RULE --> LLM_SHADOW: gate passes
    LLM_SHADOW --> LLM_PRIMARY: gate passes
    LLM_PRIMARY --> ML_SHADOW: gate passes
    ML_SHADOW --> ML_WITH_FALLBACK: gate passes
    ML_WITH_FALLBACK --> ML_PRIMARY: gate passes AND NOT safety_critical
    ML_WITH_FALLBACK --> ML_WITH_FALLBACK: safety_critical cap

    note right of ML_PRIMARY
      refused at construction
      when safety_critical=true
    end note
```

---

## FIG. 3 — Classification decision flow per phase

**Description:** A decision tree showing, for a single input,
which components are invoked in each of the six phases, and
which component's output is returned to the caller.

```mermaid
flowchart TB
    classDef box fill:#ffffff,stroke:#000000,color:#000000

    IN([input]):::box
    PH{phase?}:::box
    IN --> PH

    subgraph rp [RULE phase]
      direction LR
      R1[rule] --> R2[→ return rule_out]:::box
    end

    subgraph ls [LLM_SHADOW phase]
      direction LR
      LS1[rule decides<br/>LLM shadows] --> LS2[→ return rule_out]:::box
    end

    subgraph lp [LLM_PRIMARY phase]
      direction LR
      LP1[LLM] --> LP2{conf<br/>≥ threshold?}:::box
      LP2 -->|yes| LP3[→ return LLM_out]:::box
      LP2 -->|no / err| LP4[→ return rule_out<br/>fallback]:::box
    end

    subgraph ms [ML_SHADOW phase]
      direction LR
      MS1[LLM / rule decides<br/>ML shadows] --> MS2[→ return decision]:::box
    end

    subgraph mf [ML_WITH_FALLBACK phase]
      direction LR
      MF1[ML] --> MF2{conf<br/>≥ threshold?}:::box
      MF2 -->|yes| MF3[→ return ML_out]:::box
      MF2 -->|no / err| MF4[→ return rule_out<br/>fallback]:::box
    end

    subgraph mp [ML_PRIMARY phase]
      direction LR
      MP1{breaker<br/>tripped?}:::box
      MP1 -->|yes| MP2[→ return rule_out<br/>fallback]:::box
      MP1 -->|no| MP3[invoke ML<br/>→ return ML_out]:::box
    end

    PH -->|RULE| rp
    PH -->|LLM_SHADOW| ls
    PH -->|LLM_PRIMARY| lp
    PH -->|ML_SHADOW| ms
    PH -->|ML_WITH_FALLBACK| mf
    PH -->|ML_PRIMARY| mp

    %% Invisible ordering edges force the subgraphs to stack vertically
    %% rather than fan out horizontally from PH.
    rp ~~~ ls
    ls ~~~ lp
    lp ~~~ ms
    ms ~~~ mf
    mf ~~~ mp
```

---

## FIG. 4 — Statistical transition gate

**Description:** The gate's input is two parallel lists of boolean
correctness indicators — one for the current decision-maker, one
for the candidate higher-tier. Output is a one-sided p-value; if
below α, phase may advance.

```mermaid
flowchart TB
    classDef box fill:#ffffff,stroke:#000000,color:#000000

    D[decision_correct<br/>bool list]:::box
    C[candidate_correct<br/>bool list]:::box
    CT[count b, c<br/>b = cand wins, c = dec wins]:::box
    SEL{n = b+c}:::box
    EX[exact binomial<br/>P X ge b Bin n,0.5]:::box
    NO[normal approx<br/>with continuity correction]:::box
    P[p-value]:::box
    GT{p less than alpha?}:::box
    ADV[permit phase advance]:::box
    HLD[hold]:::box

    D --> CT
    C --> CT
    CT --> SEL
    SEL -->|n <= 50| EX
    SEL -->|n > 50| NO
    EX --> P
    NO --> P
    P --> GT
    GT -->|yes| ADV
    GT -->|no| HLD
```

---

## FIG. 5 — Self-rotating storage layout

**Description:** On-disk layout of the outcome log for a single
switch. The active segment receives new writes; on threshold
cross, it becomes the most-recent rotated segment and older
segments shift up by one index. Segments beyond the retention cap
are deleted.

```mermaid
flowchart TD
    classDef box fill:#ffffff,stroke:#000000,color:#000000
    classDef dead fill:#ffffff,stroke:#000000,stroke-dasharray:2 2,color:#000000

    W[incoming outcome write]:::box
    A[active:<br/>outcomes.jsonl]:::box
    CHK{active + new record<br/>> max_bytes?}:::box
    APP[append to active]:::box
    ROT[rotate:<br/>active → .1<br/>.1 → .2<br/>.2 → .3<br/>...]:::box
    DROP[segments past retention<br/>deleted]:::dead

    W --> CHK
    CHK -->|no| APP
    CHK -->|yes| ROT
    ROT --> APP
    ROT --> DROP
```

---

## FIG. 6 — Circuit breaker state machine

**Description:** Two states (normal, tripped). ML exception in
normal state triggers transition to tripped. Explicit reset
returns to normal. No automatic recovery in the preferred
embodiment (optional half-open state in alternative embodiments).

```mermaid
stateDiagram-v2
    direction TB
    [*] --> normal
    normal --> tripped: ML raises exception
    tripped --> normal: reset_circuit_breaker() called

    note right of tripped
      all classifications
      route to rule-fallback
    end note
```

---

## FIG. 7 — Analyzer pipeline

**Description:** Three-stage pipeline: static analysis of the
target codebase, optional dynamic instrumentation with measurement,
and savings projection combining both with a reference cost model.
Outputs are machine-readable JSON + human-readable Markdown.

```mermaid
flowchart TB
    classDef box fill:#ffffff,stroke:#000000,color:#000000
    classDef opt fill:#ffffff,stroke:#000000,stroke-dasharray:4 2,color:#000000

    SRC[target codebase]:::box
    STATIC[static analysis<br/>AST + pattern lib]:::box
    SITES[candidate sites<br/>file, lines, labels, cardinality]:::box
    DYN[dynamic instrumentation<br/>measurement-only wrapper]:::opt
    MEAS[measurements<br/>volume, shape, distribution]:::opt
    CM[reference cost model<br/>eng + regression + token]:::box
    PROJ[savings projector<br/>per-site + portfolio]:::box
    J[dendra-analyzer.json]:::box
    MD[human-readable report]:::box

    SRC --> STATIC
    STATIC --> SITES
    SITES --> PROJ
    SITES -.-> DYN
    DYN --> MEAS
    MEAS -.-> PROJ
    CM --> PROJ
    PROJ --> J
    PROJ --> MD
```

---

## FIG. 8 — Output-safety integration (Property 7)

**Description:** The invention applied to classification of
LLM-generated output before delivery to users. User input →
generator → output → classification gate → delivery (or
refusal/rewrite). The gate is a safety-critical switch in
phase RULE (or later, up to ML_WITH_FALLBACK), with phase
ML_PRIMARY refused at construction.

```mermaid
flowchart TB
    classDef box fill:#ffffff,stroke:#000000,color:#000000
    classDef unsafe fill:#ffffff,stroke:#000000,stroke-dasharray:4 2,color:#000000

    U[user input]:::box
    GEN[LLM generator]:::box
    OUT[generated output]:::box
    GATE[safety-critical switch<br/>phase up to ML_WITH_FALLBACK<br/>labels: safe, pii, toxic, confidential]:::box
    SAFE[deliver to user]:::box
    BLOCK[block / rewrite / refuse]:::unsafe

    U --> GEN
    GEN --> OUT
    OUT --> GATE
    GATE -->|label=safe| SAFE
    GATE -->|otherwise| BLOCK
```

---

## Rendering workflow

1. For each figure above, copy the Mermaid source into
   [mermaid.live](https://mermaid.live).
2. Use the "Actions → Download SVG" button.
3. Open each SVG in a browser, Print → Save as PDF.
4. Label each output file "FIG-1.pdf", "FIG-2.pdf", etc.
5. Combine into a single "drawings.pdf" or attach separately
   per USPTO filing instructions.

## Alternative: hand-drawn

USPTO accepts hand-drawn line drawings. If time-constrained and
Mermaid rendering gives any trouble, a clean pen-on-paper sketch
of each figure also satisfies the drawing requirement. Scan at
300 DPI minimum, convert to PDF, include in the packet. Add the
figure number ("FIG. 1") in the margin.

---

_Drawings prepared 2026-04-20 for the Dendra provisional.
Reference numerals correspond to the specification's §5._
