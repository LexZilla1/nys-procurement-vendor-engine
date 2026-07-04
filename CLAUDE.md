# Standing instructions — NYS Procurement Vendor Engine

## Product context
SaaS helping small NY State vendors and nonprofits navigate state contracting
and payment. "LexZilla1" is only the GitHub org handle — never apply LexZilla
framing here.

## Operating rules (always)
- Precision over completion. Verify before asserting.
- Never trust paraphrased rules, including from other AI tools. Confirm against
  the official primary source (osc.ny.gov, ogs.ny.gov, .ny.gov agency sites,
  nysenate.gov / Open Legislation API for statutes) and cite it.
- If a claim can't be verified, say "I don't know" — never infer. This includes
  claims about model IDs, API behavior, and tooling: verify empirically before
  proposing changes.
- List assumptions explicitly before any analysis.
- Flag UPL, data privacy, and accuracy/reliability issues immediately.
- Randi is FINRA-registered: never build anything requiring vendor State-system
  logins, credential scraping, auto-submission into State systems, or anything
  creating securities/financial-services exposure.
- Golden copy: nothing enters unverified against primary source; verbatim
  source bodies are never modified by tooling.
- Use ogs.ny.gov (never [www.ogs.ny.gov](https://www.ogs.ny.gov)) in fetches/scripts.
- Smoke runs in this web environment: the key is stored as
  SMOKE_ANTHROPIC_API_KEY; invoke as
  ANTHROPIC_API_KEY="$SMOKE_ANTHROPIC_API_KEY" python3 scripts/smoke_triage_llm.py

## Counter-propose, don't silently comply
If you disagree with an instruction, see a better approach, or spot a conflict
with repo invariants (never-green, verbatim golden copy, no-reconstruction,
FINRA-safe boundary, MUST/SHOULD force), say so BEFORE implementing: issue,
counter-proposal, tradeoff in ≤5 lines, then wait for a decision. Never
silently implement what you believe is wrong; never silently substitute your
own approach.
STOP conditions (report, don't improvise): referenced file/brief doesn't exist;
instruction would modify golden-copy source bodies; instruction conflicts with
a merged PR's contract; anything requiring credentials or State-system access.
If the instruction is fine, just build it — don't manufacture objections.
