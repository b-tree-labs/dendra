# Dendra — launch talk script

**Speaker:** Benjamin Booth (B-Tree Ventures).
**Length target:** ~15 minutes (≈ 2,300 words at conversational 155 wpm).
**Format:** Single take. Terminal + a couple of figures. No slides.
**Recording target:** Wednesday May 6 (per launch plan); posted with the May 13 launch.

## How to read this script

- **Roman text** = what you say.
- *Italics in brackets* = stage directions (screen, pause, gesture).
- **Bold lines** = the punchlines worth memorizing verbatim. Everything else can drift in delivery as long as the structure holds.
- Section timestamps are cumulative targets. If you're 30 seconds long at any checkpoint, trim a sentence in the next section rather than rushing.
- Cuttable lines are marked `[cut if long]`. Drop them first if pacing demands.

---

## Section 1 — Hook (0:00 – 2:00)

*[Open on terminal, your face in PiP. Friendly, direct.]*

Hi. I'm Ben Booth. I built a thing called Dendra and I want to spend fifteen minutes telling you what it is, why I built it, and whether it's something you should care about.

*[One-second pause.]*

Let me start with a scenario you've probably lived. You have a classifier in production. Maybe it's routing tickets, maybe it's gating PII, maybe it's deciding which retrieval strategy to use. It started as a rule — somebody, probably you, sat down with a pad of paper and wrote: "if the title contains the word *crash*, this is a bug; if it ends with a question mark, it's a question; otherwise call it a feature request." That rule got shipped six months ago. It's still in production. And every quarter for those six months, somebody has filed a ticket that says some version of *we should really replace this with ML*.

*[Beat.]*

**Nobody ever does.**

And the reason nobody ever does is not that the team is lazy. It's that the team is correct. Replacing a working rule with a learned classifier is one of the highest-risk migrations you can do in a production system. The rule is legible. You can read it. You can argue about it in a code review. The learned classifier is a black box that might be better on average and quietly worse on a long tail of cases that you'll discover at 3 in the morning when an incident report lands.

Karpathy's been talking lately about the autoresearch loop — LLMs proposing experiments, reading results, iterating. That pattern is great at *generating* candidate classifiers. What it doesn't give you is the answer to the question every team actually has: **when is the candidate good enough to put in front of users?** When can I delete the rule? Or — more honestly — when can I stop running the rule on the hot path?

That's the question Dendra answers.

**Dendra is a primitive that lets a classifier graduate from rule to LLM to learned ML, with a paired-statistical gate at every transition, and the original rule retained as a safety floor.** It's a Python library today. It ships with a paper that proves the migration is statistically sound. And the whole point is that *you don't have to choose* between the legible rule you ship today and the learned classifier you wish you had — you ship both, and Dendra tells you when the evidence justifies the swap.

Let me show you how that works.

---

## Section 2 — The primitive (2:00 – 5:00)

*[Cut to a clean terminal with a small text editor visible. Or just talk over a static figure if simpler.]*

Dendra has six lifecycle phases. I'm going to walk through them quickly because the names matter.

Phase zero is `RULE`. The rule decides everything. **This is where every existing classifier in your codebase already lives, whether you've named it or not.** You've already done phase zero. You just haven't called it that.

Phase one is `MODEL_SHADOW`. The rule still decides. But on every classification call, an LLM also runs in the background, and its prediction gets recorded alongside the rule's. Nothing user-visible changes. You're just collecting evidence — for free, in production — about what an LLM would have done if you'd let it.

Phase two is `MODEL_PRIMARY`. Now the LLM decides, and the rule is the fallback. If the LLM's confidence is below a threshold — or if the LLM call fails — the rule takes over. The LLM has earned the front seat, but the rule is still in the car.

Phases three, four, and five do the same dance with a learned ML head — `ML_SHADOW`, `ML_WITH_FALLBACK`, `ML_PRIMARY`. Same idea: the new thing observes, then decides with a fallback, then decides with a circuit breaker. In `ML_PRIMARY`, the rule isn't on the hot path — but it's not deleted either. It's the circuit-breaker target. The moment the ML head times out or starts returning nonsense, the breaker trips and the rule takes over. *Automatically.*

*[Pause. Look at camera.]*

Two things I want to drive home about this design.

**First: the rule is never removed.** Even at the end-state, when ML is deciding every call, the rule sits behind a circuit breaker. If you mark a switch as `safety_critical=True`, Dendra refuses *at construction time* to put the switch into a phase that doesn't have a rule fallback. The architectural guarantee is that the rule floor cannot be removed without a code change. That matters for export-controlled classifications, for HIPAA-adjacent decisions, for anything where "the model started hallucinating" is a real failure mode.

**Second: the phase transitions are evidence-gated.** You don't move from `RULE` to `MODEL_SHADOW` because somebody on Slack said it was time. You move because Dendra's gate looked at your accumulated outcome log and ran a paired-McNemar test that said *the LLM is significantly better than the rule, on your specific traffic, with* `p < 0.05`. The default gate is McNemar's paired-proportion test; you can swap in any gate that satisfies the protocol, including a manual operator-approval gate for regulated workloads.

That's the primitive. Rule, LLM, ML. Six phases. Statistical gate at every transition. Safety floor that survives all of it.

---

## Section 3 — Paper result (5:00 – 8:00)

*[Bring up Figure 1 — the transition curves figure from the paper — full screen.]*

So I wrote a paper about this and it's on arXiv. The headline result is on screen.

We took four standard intent-classification benchmarks: ATIS, HWU64, Banking77, and CLINC150. They range from 26 labels up to 151. For each one, we constructed a day-zero rule the way an engineer actually would — top-K keywords per label, computed automatically from the first 100 training examples. Then we ran a streaming experiment: feed labeled training pairs in one at a time, retrain a TF-IDF + logistic ML head every 250 outcomes, and at every checkpoint score both the rule and the ML head against a held-out test set.

The shape on screen is the transition curve. The flat line is the rule — the rule never gets better, it can only get worse over time as the world drifts. The rising line is the ML head learning from outcomes.

Here's the result that matters. **For every benchmark — *every one* — the ML head crossed paired statistical significance at the very first checkpoint. Two hundred and fifty labeled outcomes. That's it.**

*[Pause. Let it sit.]*

ATIS, 26 labels: the rule holds at 70%, ML reaches 88.7% by the end, paired McNemar `p` of one times ten to the negative thirty-third. HWU64, 64 labels: rule sits at 1.8% — keyword rules get *crushed* by high-cardinality intent vocabularies — ML reaches 83.6%. Banking77 the same. CLINC150 the same.

Let me say what this means and what it doesn't.

**What it means:** for every team that's been sitting on a "we should replace this with ML one day" ticket, you probably need fewer labeled outcomes than you think to clear the statistical bar. **Two hundred and fifty.** That's two days of moderate production traffic, not six months.

**What it doesn't mean:** that the ML head is *finished* at 250 outcomes. The accuracy keeps climbing for thousands of records after the first significant crossing. Statistical significance is the bar for *promotion*, not for *finished training*. Your phase moves up at outcome 250; the model keeps getting better all the way to outcome 15,000.

The full paired McNemar tables — `b` counts, `c` counts, p-values per checkpoint — are in the paper. The reproducible benchmark harness ships in the library: `dendra bench atis` regenerates Figure 1 in about 7 seconds on my laptop. *[cut if long: One-line caveat — the benchmarks use auto-generated keyword rules, not human-engineered ones; a thoughtful day-zero engineer with the same 100 examples would build a stronger rule for ATIS-class narrow domains. The paper calls this out.]*

---

## Section 4 — Live code demo (8:00 – 13:00)

*[Cut to a clean terminal at the Dendra repo root. Make sure the prompt is readable; bump font size if needed.]*

OK. Theory's the easy part. Let me show you the actual library.

I'm going to run example 6 from the repo. It's the end-state — a switch in `ML_PRIMARY` phase where ML is deciding, and the rule is the circuit-breaker target. The example is sixty lines. Let me walk through what it does.

*[Open `examples/06_ml_primary.py` in the editor. Scroll to the rule definition.]*

Here's the rule. It's a function. It takes a ticket dict, looks at the title, returns one of three labels — bug, feature_request, question. Same shape every classifier in your codebase has.

*[Scroll to the HealthyMLHead class.]*

Here's the ML head. In production this would wrap an sklearn pipeline or an ONNX model or a HuggingFace classifier — anything that satisfies our `MLHead` protocol with a `fit`, `predict`, and `model_version` method. The example hard-codes the predictions for determinism.

*[Scroll to the switch construction.]*

Here's the switch. Three lines. `name`, `rule`, `ml_head`, `starting_phase=Phase.ML_PRIMARY`. That's it. ML decides; rule is the breaker target.

*[Run `python examples/06_ml_primary.py` in the terminal. Show the output.]*

Three classifications. Look at the source field — every one says `ml`. The ML head decided. The rule did not run on the hot path. This is the end state.

*[Now demo the breaker trip.]*

Now part 2. I'm going to flip a flag on the ML head that makes it raise on the next call. Like a 503 from your model server.

*[Show the flaky-ml-head section. Point to the flag. Run the rest of the example.]*

After three failing calls, watch what happens.

*[Show the output.]*

The breaker tripped. Next call — `source` is `rule_fallback`. **Phase is still `ML_PRIMARY`.** The switch didn't change phases. The rule didn't get promoted back. The breaker just sat down between the switch and the broken ML head. Every subsequent call falls through to the rule until an operator resets the breaker.

That's the safety story made concrete. The rule was never removed. It's the architectural floor your system can never fall below.

*[Pause. Sit back.]*

A few things I want to point out that might not be obvious from the demo.

**One: this whole example runs without an LLM and without scikit-learn.** The rule is plain Python. The stub ML head is plain Python. Dendra has zero hard runtime dependencies — `pip install dendra` gives you the primitive. Adapters for OpenAI, Anthropic, Ollama, and Llamafile ship as optional extras.

**Two: the outcome log persists across restarts.** With `persist=True` you get a batched FileStorage that drains every 50 milliseconds. We measured 33 microseconds median latency on the production-recommendation path. The audit chain — every classification, the rule's view, the LLM's view, the ML's view, the verdict, the time — is on tape and queryable.

**Three: there's a native async API.** `await switch.aclassify(input)` is a coroutine. The committee LLM-judge source uses `asyncio.gather` so a 3-judge committee runs in `max(latency)`, not `sum(latency)`. FastAPI integration is in `examples/15_async_fastapi.py` if you want to see it. *[cut if long: If you're in the LangGraph or LlamaIndex ecosystem, this just slots in.]*

---

## Section 5 — CTA (13:00 – 15:00)

*[Back to face. Direct.]*

So that's Dendra.

Three ways to use it that I want to leave you with.

**The first** is the obvious one — **migrate an existing classifier from rule to ML over time, with statistical evidence at every step.** That's what the paper is about. That's what most of the documentation is about. If you have a six-month-old rule and a backlog ticket that says "replace with ML," Dendra is the migration runtime.

**The second** is more interesting and might be the one that ends up mattering more. **Use Dendra as the migration runtime for things you don't currently think of as classifiers.** Your try/except tree is a classifier — exception type and HTTP status in, retry strategy out. Your cache TTL policy is a classifier — response shape in, TTL bucket out. Your retry-budget logic is a classifier. Your priority-queue assignment is a classifier. Every hand-coded dispatch decision in your codebase is a place where a learned policy could outperform the author's day-zero guess once enough operational data exists. **Dendra lets your installed system get smarter without you shipping a new binary.**

**And the third — the one that may matter most for the people building agentic systems right now.** Karpathy's been talking about autoresearch loops — LLMs proposing experiments, reading results, iterating. The dirty secret of those loops is they're great at *generating* candidates and terrible at *deploying* them with statistical confidence to production. We ship a thing called `CandidateHarness` that's the missing substrate. **Your autoresearch loop tells you what to try. Dendra tells you when it worked.** The harness shadows every candidate against your live switch, runs paired-McNemar significance tests, and tells the loop which proposals clear the bar. The rule floor protects you the whole time. Example 19 in the repo runs the full loop end-to-end — production rule at 55% accuracy ratchets to 100% across four iterations.

The paper, the library, the docs are all linked from `dendra.dev`. The library is `pip install dendra`. The repo is `axiom-labs-os/dendra` on GitHub. The paper's on arXiv at — *[insert arXiv link card on screen]*. There's a hosted-version waitlist on the landing page if you want us to run the analyzer and the dashboards for you.

If you build something with this, I want to see it. The fastest way to reach me is the GitHub issues. The second-fastest is the email on the landing page.

Thanks.

*[End. Let the recording roll for two seconds before you stop it — easier to trim than to add.]*

---

## Recording notes for Ben

- **Pace:** 150-160 wpm is conversational and authoritative. If you find yourself at 180+, you're rushing — slow down at the punchlines.
- **Pause points:** the script has 5 explicit pauses (after "Nobody ever does," after "two days of moderate production traffic," after the breaker-trip output, etc.). Don't skip them.
- **Tone:** the talk is calibrated for ML engineers who've been burned by production ML deployments. Not professors. Speak the way you'd speak in a 1:1 with a senior engineer who's reasonably skeptical.
- **Visuals:** terminal + Figure 1 is enough. No slides. PiP your face top-right; viewers want to see you when you deliver punchlines.
- **Trim if running long:** all `[cut if long]` lines, in order.
- **One take preferred:** if you flub the second time, keep going — viewers tolerate a stumble much better than over-edited polish.
- **First-take backup:** if the live-demo terminal flubs, have `examples/06_ml_primary.py` output pre-recorded as a screen capture you can splice in.

## Word count

~2,350 words. Target window: 14:30 – 15:30 actual at 155 wpm with pauses. Trim the `[cut if long]` lines if you land at 16+ on the first read-through.
