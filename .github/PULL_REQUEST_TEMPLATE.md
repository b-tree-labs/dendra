<!--
Thanks for contributing to Postrule. A few things that make
review faster:

- Keep the PR focused on a single change. Two unrelated
  fixes are easier as two PRs.
- Run `pytest` locally before pushing. The pre-push hook
  catches most issues but not all of them.
- DCO sign-off is required (`git commit -s`). The CI
  workflow checks every commit.

Delete the sections that don't apply.
-->

## What this PR does

<!-- One-paragraph summary. What changed and why? -->

## How I tested it

<!-- Concrete steps. What command did you run? What output
     confirmed it worked? -->

## Type of change

- [ ] Bug fix (non-breaking; adds tests + a one-line behaviour
      change)
- [ ] New feature (non-breaking; surface change documented)
- [ ] Breaking change (call out the migration path; note version
      bump in CHANGELOG)
- [ ] Documentation only
- [ ] Tooling / repo hygiene

## Checklist

- [ ] Tests pass locally (`pytest`)
- [ ] Public API additions are exported from `postrule/__init__.py`
- [ ] User-visible changes are reflected in `CHANGELOG.md`
      under `[Unreleased]`
- [ ] Docs are updated for any new public surface
      (`docs/api-reference.md`, README.md, relevant feature doc)
- [ ] Examples added/updated for any new top-level pattern
- [ ] DCO sign-off on every commit (`git commit -s`)

## Related issues

<!-- Closes #123, refs #456 -->
