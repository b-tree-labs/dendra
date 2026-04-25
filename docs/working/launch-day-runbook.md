# Launch-day runbook — Wednesday May 13, 2026

**Owner:** Ben (executive). All times America/Chicago (Austin).
**Pre-launch finalization deadline:** Tuesday May 12, 5pm CT.
**Launch window:** Wed May 13, 6:00 AM – 6:00 PM CT.

This is the linear go-no-go checklist. Execute top-to-bottom on
launch day; anything yellow or red on a gate halts the launch
until resolved or escalated.

---

## T-1 day — Tuesday May 12

### Quiet day. Press-check everything. No new commits to main.

| Check | Owner | Status |
|---|---|---|
| Full test suite green on `main` (`pytest -q`) | Ben | ☐ |
| Benchmark pins green (`pytest -m benchmark`) | Ben | ☐ |
| `dendra-0.2.0` builds + installs in fresh venv from `dist/` | Claude | ☐ |
| All 19 examples run end-to-end | Claude | ☐ |
| README.md last-pass: no stale numbers, no broken links | Ben | ☐ |
| FAQ.md last-pass: numbers match README + paper | Ben | ☐ |
| docs/papers/.../findings.md numbers match arXiv submission | Ben | ☐ |
| Landing page live on Firebase staging URL | Claude | ☐ |
| Brand assets (animated mark, social banners) final | Ben | ☐ |
| Recorded talk uploaded somewhere accessible (YouTube unlisted is fine) | Ben | ☐ |
| arXiv submission queued (live by morning May 13) | Ben | ☐ |
| HN post body finalized (D8 stamp by EOD May 12) | Ben | ☐ |
| X/LinkedIn post threads drafted | Claude | ☐ |
| Reviewer outreach drafts ready (Hamel + Lingjiao + any from Cowork list) | Claude | ☐ |
| `axiom-labs-os/dendra` repo: secrets-history rescan clean | Claude | ☐ |
| `axiom-labs-os/dendra` repo: branch-protection on main verified | Ben | ☐ |
| `dendra.dev` DNS: CNAME pointed at Firebase | Ben | ☐ |
| Pricing page final (post-Cowork analysis) | Ben | ☐ |
| Waitlist form posts successfully (test submission) | Claude | ☐ |
| GitHub repo description + topics set | Ben | ☐ |

**Gate to T-0:** every box above ticked. If anything red as of 5pm CT May 12, slip launch by one day; reschedule comms.

---

## T-0 — Wednesday May 13

### 6:00 AM CT — Pre-flight

| Step | Command / action |
|---|---|
| 1. Coffee | (this is mandatory) |
| 2. Last-look at HN post body | read it cold; one final pass |
| 3. Last-look at the talk video | confirm it plays, audio clean |
| 4. Confirm tests still green on main | `pytest -q` |
| 5. Build the launch wheels | `python -m build` |
| 6. Confirm `dist/dendra-1.0.0-py3-none-any.whl` exists | `ls dist/` |

### 6:30 AM CT — Bump to v1.0.0

```bash
# Tag the release commit
git checkout main
git pull
sed -i.bak 's/version = "0.2.0"/version = "1.0.0"/' pyproject.toml
sed -i.bak 's/__version__ = "0.2.0"/__version__ = "1.0.0"/' src/dendra/__init__.py
rm -f pyproject.toml.bak src/dendra/__init__.py.bak

# CHANGELOG entry already prepped per docs/working/changelog-v1.0.0-draft.md
git add pyproject.toml src/dendra/__init__.py CHANGELOG.md
git commit -s -m "release: v1.0.0"
git tag -a v1.0.0 -m "Dendra v1.0.0 — public launch"
```

**DO NOT push yet.** This commit + tag pushes everything visible
once the repo flips public.

### 7:00 AM CT — Build + verify the launch wheel

```bash
rm -rf dist/ build/
python -m build
ls dist/
# Should see:
#   dendra-1.0.0-py3-none-any.whl
#   dendra-1.0.0.tar.gz

# Smoke test in a clean venv
python3 -m venv /tmp/dendra-launch-check
/tmp/dendra-launch-check/bin/pip install dist/dendra-1.0.0-py3-none-any.whl
/tmp/dendra-launch-check/bin/python -c "from dendra import LearnedSwitch, CandidateHarness; print('OK')"
/tmp/dendra-launch-check/bin/python examples/01_hello_world.py
```

**Gate:** clean run. If anything fails, halt launch.

### 7:30 AM CT — Push to PyPI

```bash
.venv/bin/pip install --quiet --upgrade twine
twine check dist/*
twine upload dist/*
# Will prompt for PyPI API token. Have it ready.
```

Verify on PyPI: <https://pypi.org/project/dendra/1.0.0/>

In a third clean venv:

```bash
python3 -m venv /tmp/dendra-pypi-check
/tmp/dendra-pypi-check/bin/pip install dendra
/tmp/dendra-pypi-check/bin/python -c "import dendra; print(dendra.__version__)"
# Expected: 1.0.0
```

**Gate:** PyPI install works. If TestPyPI was used as a dry run earlier in the week, this should be uneventful.

### 8:00 AM CT — Push to GitHub + flip public

```bash
# Push the v1.0.0 commit + tag
git push origin main
git push origin v1.0.0
```

In the GitHub web UI:

1. Repo settings → Visibility → **Change to Public**
2. Confirm with the typed-name verification
3. Verify front-page README renders correctly
4. Add repo topics: `python`, `machine-learning`, `mlops`, `llm`, `classification`, `autoresearch`, `cascading`, `production-ml`
5. Settings → Social preview → upload `brand/dendra-github-social-preview.svg`
6. Releases → Create release from tag `v1.0.0` → paste CHANGELOG entry as release notes

### 8:30 AM CT — arXiv goes live

If submitted T-1 with a 2026-05-13 listing date, the abstract
should be live in cs.LG / cs.AI feeds by ~9 AM ET. Confirm the
URL works before posting to HN.

Verify: arXiv URL resolves; PDF downloads; figures render.

### 9:00 AM CT — Post to Hacker News

1. Open <https://news.ycombinator.com/submit>
2. Title: per D8 final pick (your choice between A and B)
3. URL: `https://dendra.dev/`
4. Body: paste from `docs/working/launch-hn-post.md`

**Critical for HN front-page algorithm:**
- Post NO EARLIER than 8:30 AM ET / 7:30 AM CT (catches the Eastern morning)
- Post NO LATER than 10:00 AM CT (after 11 AM CT loses the morning surge)
- Don't ask for upvotes
- Refresh once at +30 minutes to confirm it's on /new
- After ~1 hour, check if it's on the front page

### 9:30 AM CT — Social posts

| Channel | Action |
|---|---|
| **X / Twitter** | Post the launch thread (4-6 tweets, drafts in `docs/working/launch-x-thread.md`); tag @karpathy if the headline is the autoresearch one (no @-mention if A — risks looking sycophantic) |
| **LinkedIn** | Single long-form post (drafts in `docs/working/launch-linkedin-post.md`) |
| **Reviewer FYI emails** | Send Hamel + Lingjiao + any Cowork-list approvals (drafts in `docs/working/launch-reviewer-outreach.md`); explicit "no obligation" framing |

### 10:00 AM CT – 6:00 PM CT — Engagement

Stay at the keyboard. The HN post is live or has died; either
way, this is the day to be present.

**Things to do:**

- Answer every HN comment within 30 minutes of arrival (if HN
  is hot)
- File GitHub issues for every legitimate bug report; respond
  with a tag and one-line acknowledgment within an hour
- DM responses to thoughtful X replies
- Watch GitHub stars / PyPI download counter
- Watch Firebase analytics (if wired) for landing-page traffic
- Watch Anthropic / OpenAI cost dashboards if anyone is hammering
  the live-jailbreak test path (they shouldn't — it's gated by env
  var — but worth confirming)

**DO NOT do:**

- Push to main without a 4-eyes review (no one is fresh today)
- Promise features in HN comments ("v1.1 will have X" is fine;
  "we'll add X tomorrow" is not)
- Engage with bad-faith critics — let HN moderate
- Send any new outreach until tomorrow

### End of day

| Step | Owner |
|---|---|
| Snapshot HN comments + GitHub stars + PyPI downloads | Ben |
| Identify top 3 issues / questions to address in v1.0.1 | Ben |
| Send "thanks for landing" message to anyone who amplified | Ben |
| Send post-launch tasks to Q3 backlog (NeurIPS submission prep, hosted-beta dev) | Ben |

---

## Rollback / abort criteria

**Halt launch at any T-0 step if:**

- Test suite is red (any test, any platform)
- PyPI install fails in clean venv
- arXiv submission is held / rejected
- Landing page is down at the public DNS resolution time
- A genuine security incident is reported in the OSS code
- Ben is sick / unavailable for engagement

**If you halt:** flip GitHub repo back to private (if not yet
public), un-publish PyPI release (`pip install dendra==1.0.0`
will still resolve from cache, but `pypi.org` shows yanked),
post a one-sentence acknowledgment ("we hit a launch blocker;
holding for X"), schedule rerun.

**One-day slip plan:** repeat T-1 + T-0 from May 14. The HN
algorithm doesn't care which day; the only loss is the social-
calendar hold.

---

## Files this runbook references (and their status)

- `docs/working/launch-hn-post.md` — **TBD** (drafting next)
- `docs/working/launch-x-thread.md` — **TBD**
- `docs/working/launch-linkedin-post.md` — **TBD**
- `docs/working/launch-reviewer-outreach.md` — **TBD**
- `docs/working/changelog-v1.0.0-draft.md` — **TBD**
- `docs/working/launch-landing-page-wireframe.md` — ✓ shipped
- `docs/working/launch-talk-script.md` — ✓ shipped
- `docs/working/launch-repo-hygiene-triage.md` — ✓ shipped (awaiting sign-off)
- `docs/papers/2026-when-should-a-rule-learn/related-work-bibliography.md` — ✓ shipped
- arXiv-ready PDF — **BLOCKED on BasicTeX install + LaTeX template**

---

## What's still on Ben's plate (as of 2026-04-25)

**Decisions:**

- D8 final HN headline pick (defer to T-1)
- Pricing tiers (Cowork analysis dropped; awaiting output)
- Repo hygiene triage sign-off (`docs/working/launch-repo-hygiene-triage.md`)
- Landing-page wireframe sign-off (4 questions)

**Tasks:**

- Run the BasicTeX install
- Record the talk (target Wed May 6)
- Reviewer list from Cowork session
- Confirm domain ownership of dendra.dev on GoDaddy
- Confirm Firebase project ownership

I'll keep building toward this runbook. Tell me which decision
you want to stamp next.
