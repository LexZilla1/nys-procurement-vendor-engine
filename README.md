# NYS Procurement Vendor Engine

A validation engine that checks vendor documents and NYS tenders against a
verbatim "golden copy" of New York State procurement rules. Every finding is
grounded in a verbatim citation (`GoldenCopy.cite()` — no paraphrase can enter a
result), and rule freshness is tracked separately from rule text.

## Golden copy

`golden-copy/sources/` holds 45 verbatim source records (22 statute-class
sections captured from NY Open Legislation, plus OSC/OGS guidance, forms, and a
regulation). Integrity is enforced by `parse_golden_copy.py`, which reconciles
the source-file count against `golden-copy-INDEX.md` and `VERIFICATION-REPORT.md`
(the 45/45/45 check) and requires every file to declare a `Covers:` field.

## Automated monthly freshness check

`scripts/freshness_check.py` re-fetches the 22 statute-class sources from the NY
Senate Open Legislation API v3, diffs each against the current golden-copy
`STATE TEXT`, and classifies **FULL-MATCH / FRAGMENT / DIVERGENT**. It also
re-checks the four sunset statutes' repeal metadata (API `repealed`/
`repealedDate` and the in-text `* NB Repealed` date) against our recorded sunset
dates (§314 → 2028-07-01, §139-j/-k → 2028-07-31, §163 → 2031-06-30). It is
**read-only** against the golden copy — it only writes a report to
`docs/freshness/YYYY-MM-DD.md` and never rewrites a source file.

Run it offline (no key, no network) to exercise the diff/classify/report logic:

```bash
python3 scripts/freshness_check.py --selftest
```

### What triggers a PR vs a silent pass

The workflow `.github/workflows/freshness-check.yml` runs on the **1st of each
month** (and on demand via *Run workflow*):

- **All FULL-MATCH, no sunset mismatch → silent pass.** The dated report is
  committed straight to `main`; no PR is opened.
- **Any DIVERGENT verdict OR any sunset mismatch → drift.** A **draft** pull
  request is opened, labeled **`freshness-drift`**, containing the report and the
  new report file. It is **never auto-merged**, and the golden-copy source files
  are **never rewritten automatically** — a human reviews and decides whether to
  re-capture (a Phase-3-style rebuild) or update the sunset records.

### Adding the `NYSLEG_API_KEY` secret

The workflow reads the API key from a repository secret. To add it:

1. Get a free Open Legislation API key by signing up at
   <https://legislation.nysenate.gov/> (email registration; no fee).
2. In GitHub, go to **Settings → Secrets and variables → Actions → New
   repository secret**.
3. Name it exactly **`NYSLEG_API_KEY`** and paste the key as the value.

The key is read only from the environment at run time; it is never logged,
printed, or written to any committed file. If the secret is missing, the script
exits with a clear error and no report is produced.

> Note: the label `freshness-drift` should exist in the repo (**Issues → Labels
> → New label**) so the PR is tagged; if it does not exist, GitHub creates the
> PR without the label rather than failing.
