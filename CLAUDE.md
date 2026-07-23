# Standing instructions — NYS Procurement Vendor Engine

## Product context
SaaS helping small NY State vendors and nonprofits navigate state contracting
and payment. "LexZilla1" is only the GitHub org handle — never apply LexZilla
framing here.

## Operating rules (always)
- Precision over completion. Verify before asserting.
- ALWAYS `git fetch origin` and confirm the real remote HEAD before analyzing the
  repo. A stale local checkout is as unreliable as a stale summary — a prior session
  lost hours to a branch 26 commits behind `origin/main` and reached a confident,
  completely wrong "none of this work exists" conclusion. "Verify against git" only
  counts if git has been fetched.
- CI: this repo has **NO CI on pull requests** — zero checks, always. "Green" is a
  claim derived from a local / branch run, never an automated verification at merge.
  Do NOT wait for checks to register on a PR (they never will), and do NOT schedule
  self-checks or polling to wait for CI. The freshness workflow is the CI-equivalent
  for the only thing that matters — golden-copy drift — and runs only monthly
  (cron `0 6 1 * *`) or on manual `workflow_dispatch`.
- Never trust paraphrased rules, including from other AI tools. Confirm against
  the official primary source (osc.ny.gov, ogs.ny.gov, .ny.gov agency sites,
  nysenate.gov / Open Legislation API for statutes) and cite it.
- If a claim can't be verified, say "I don't know" — never infer. This includes
  claims about model IDs, API behavior, and tooling: verify empirically before
  proposing changes.
- List assumptions explicitly before any analysis.
- Flag UPL, data privacy, and accuracy/reliability issues immediately.
- State-system boundary: never build anything requiring vendor State-system
  logins, credential scraping, or auto-submission into State systems, or any
  lending / financial-advisory feature.
- Golden copy: nothing enters unverified against primary source; verbatim
  source bodies are never modified by tooling.
- Use ogs.ny.gov (never [www.ogs.ny.gov](https://www.ogs.ny.gov)) in fetches/scripts.
- Smoke runs in this web environment: the key is stored as
  SMOKE_ANTHROPIC_API_KEY; invoke as
  ANTHROPIC_API_KEY="$SMOKE_ANTHROPIC_API_KEY" python3 scripts/smoke_triage_llm.py

## Counter-propose, don't silently comply
If you disagree with an instruction, see a better approach, or spot a conflict
with repo invariants (never-green, verbatim golden copy, no-reconstruction,
State-system boundary, MUST/SHOULD force), say so BEFORE implementing: issue,
counter-proposal, tradeoff in ≤5 lines, then wait for a decision. Never
silently implement what you believe is wrong; never silently substitute your
own approach.
STOP conditions (report, don't improvise): referenced file/brief doesn't exist;
instruction would modify golden-copy source bodies; instruction conflicts with
a merged PR's contract; anything requiring credentials or State-system access.
If the instruction is fine, just build it — don't manufacture objections.

### Prompt review (always)
Treat every pasted prompt/brief as a DRAFT TO ENGINEER, not an order to execute
— the goal is the best possible prompt, not literal compliance. Before acting:
1. Verify its premises against the ACTUAL code (file:line, real behavior), not
   assumptions — pasted briefs are often written without seeing current state.
2. Reject or correct anything wrong, over-scoped, unsafe, or invariant-violating
   (never-green, verbatim golden copy, no behavior change inside a seam/latent
   fix, State-system boundary — no vendor State-system logins, no credential
   scraping, no auto-submission into State systems). Watch for the common traps:
   a "canonical constant" that would merge two distinct vocabularies; a "fix"
   that changes a serialized or vendor-facing shape; a premise (e.g. "this
   KeyErrors") the code contradicts.
3. Counter-propose and STOP for the user's decision: state the correction and the
   improved version with rationale, then WAIT for the user to approve before
   implementing. NEVER silently execute a self-corrected version — correcting a
   prompt does not authorize acting on the correction.
4. If the prompt is already sound, say so briefly and proceed — no ceremony.
Precedence: this rule does NOT override task-specific instructions that take
priority — e.g. a read-only / investigation session (report findings only; no
commit/push/PR) or a pilot-run's constraints. Those win; apply prompt review
within them, not against them.

## Prompt claims are unverified by default
Prompts arrive from chat sessions (Claude Chat, ChatGPT) whose repo access may be absent,
partial, stale, or read-only. Any factual claim in a prompt about repo contents is
therefore a hypothesis, not a fact — whether a file exists, what a file contains, what a
test asserts, what is or isn't in golden copy, what a prior PR did, what the current state
of anything is — until it is reverified against freshly fetched state.

Read access is not verification. A session with repo access may still be looking at a
stale checkout, a partial view, or reasoning wrongly from what it correctly sees. Access
level does not change the obligation to reverify against freshly fetched state.

Before acting on such a claim, verify it against the repo.

If a claim is wrong:
- STOP. Report the discrepancy before proceeding.
- Do NOT write the claim into any file.
- Do NOT silently correct it and continue — the human needs to know the brief was wrong,
  because the same wrong claim is probably still live in the chat session that produced it.

This applies to documentation tasks as much as to code. A false claim recorded in
BACKLOG.md or docs/ is worse than a bug: nothing fails, it survives, and it misdirects
future sessions.

Precedent: PR #84 (2026-07-23) recorded "§179-p is NOT in golden copy / BLOCKING for
Payment Clock." The file golden-copy/sources/source-stf-179-p.md already existed. The
claim originated as a chat-session inference from XII.5.I paraphrasing §179-p, was never
checked against the filesystem, and was written to BACKLOG as fact.

## Disagreement is expected, not insubordination
Prompts are written by chat sessions that may not see the codebase, or may see only a
partial or stale slice of it. They may be architecturally wrong, more complex than
necessary, or in conflict with something already built.

If you believe the instruction is wrong — not just factually inaccurate, but a worse
approach than an available alternative — say so BEFORE implementing. State the
disagreement, the reason, and the alternative. Then wait.

Do not:
- comply silently while believing the approach is wrong
- implement it and note the concern afterwards
- widen scope to "fix" it on your own initiative

Counter-proposing is part of the job. The chat session has design context you lack;
you have codebase reality it lacks. Neither is automatically right. Surface the
conflict and let the human adjudicate.

Precedent (2026-07-23): the registry-mode fix was specified as a two-field change.
Code found the test suite pins that field and reported that a green fix requires three
files — correctly stopping rather than either pushing red or silently widening scope.
Separately, a hook suggested rewriting authorship of four already-merged main commits;
Code refused and explained why. Both were right to push back.

## Merge policy
Never merge a PR without explicit approval in this session, given AFTER the
PR is opened. For every PR, post: the PR link, a plain-English summary of
what changed and why (≤8 lines), what could break, and test results. Then
STOP and wait for Randi's "merge" (or requested changes).
Exception — auto-merge allowed ONLY for: freshness-clean automation PRs,
and typo/doc-comment-only changes touching no code, no golden copy, no
config. Everything else waits.
Note: PRs #29–#34 were merged under prompts that pre-authorized squash-merge;
this policy applies from this PR forward.

## Durability — never lose work (cloud/ephemeral sessions)
Cloud sessions run in ephemeral containers: **unpushed work may be lost** when
the container is reclaimed. Pushing a branch is always safe; only merging needs
approval (see Merge policy).
- Push the working branch to origin at every natural checkpoint: the first
  passing test run, before any long-running step, and before session end.
- Before ending any implementation session: commit the PR-scope changes, push
  the branch, and — if tests pass — open a draft PR.
- If tests do NOT pass, or a PR should not be opened, explicitly report:
  uncommitted changes, staged changes, local-only (unpushed) commits, the
  branch name, the upstream/push status, and the exact reason nothing was
  pushed / no PR was opened. Never end silently with work only on the local
  branch.
- Read-only / investigation sessions must NOT commit, push, or open PRs — they
  report findings only.

## Compliance wording check
Any PR that adds or changes vendor-facing output text (verdicts, notices,
interest/eligibility wording, form-fill notices) must include a self-review
section in the PR summary: quote each new or changed user-facing string and
state why it is information, not legal advice (UPL test), before requesting
merge approval.
