# Can I use Dendra? A developer's guide

Short answer: **yes, for nearly everything you'd want to do.**

Dendra is split-licensed:
- The **client SDK** (what you `import` into your code) is
  **Apache 2.0** — the same license as Kubernetes, Kafka, React
  Native, and thousands of other libraries. Permissive.
- The **Dendra-operated components** (the analyzer CLI, the
  ROI reporter, future hosted services) are
  **Business Source License 1.1** — permissive for nearly
  everything *except* offering a competing hosted
  Dendra-derivative service. Converts to Apache 2.0 on
  **2030-05-01**.

If the question below is on this list, the answer is **yes, go
for it:**

- Can I `pip install dendra` and use it in my closed-source
  commercial product? **Yes.**
- Can I wrap `@ml_switch` around my classifier and ship the
  result as part of my SaaS / mobile app / internal tool /
  enterprise platform? **Yes.**
- Can I fork the decorator and modify it for my own use?
  **Yes.**
- Can I redistribute Dendra as a dependency in another Apache /
  MIT / BSD / GPL / proprietary project? **Yes.**
- Can I run `dendra analyze` against my own codebase in CI,
  staging, or production — at my company? **Yes** — this is
  explicitly permitted by the Additional Use Grant in the BSL.
- Can I host a private Dendra Cloud for my own team's use?
  **Yes** — internal use within your organization is not a
  competing offering.
- Can I submit bug fixes / improvements to Dendra? **Yes** —
  we welcome contributions. See `CONTRIBUTING.md`.
- Can I cite Dendra in a paper, blog post, or talk? **Yes** —
  we encourage it. No license is needed for citation.

If the question is on *this* list, the BSL applies and you may
need a commercial license — contact
`licensing@b-treeventures.com`:

- Can I offer a hosted Dendra-as-a-Service product that
  competes with Dendra Cloud? **Not without a commercial
  license.**
- Can I rebrand Dendra's analyzer and sell it as part of my own
  product? **Not without a commercial license.**
- Can I embed Dendra's BSL-licensed modules in a product I'm
  offering to third parties as a paid service? **Not without a
  commercial license** (for the BSL-licensed modules; the
  Apache 2.0 client SDK is fine).

If you're not sure which license applies to a given file, look at
the per-file header — each source file declares its own license
in the top comment block. A file under Apache 2.0 is free for
commercial use; a file under BSL is governed by the terms in
`LICENSE-BSL`.

## Which files are which?

Per-file headers declare the applicable license. The rule of
thumb:

- **Apache 2.0** — anything you'd reasonably `import` from your
  own process: the decorator, phase enum, config, storage,
  adapters, telemetry, visualization, benchmarks.
- **BSL 1.1** — anything Dendra runs *for* you or as a product
  surface: the analyzer, the ROI reporter, the CLI that drives
  the paid product surfaces, any server or hosted component.

## Trademarks

DENDRA, TRANSITION CURVES, and AXIOM LABS are trademarks of
B-Tree Ventures, LLC. The licenses above do not grant rights to
use these marks. See [`TRADEMARKS.md`](./TRADEMARKS.md) for
fair-use and attribution guidance.

## Still unsure?

Email `licensing@b-treeventures.com` with your use case and we'll
tell you plainly whether the Apache 2.0 grant covers it or
whether the BSL applies. We default to "covered by Apache 2.0"
for any use case that isn't obviously a competing hosted
service.
