# Freshness reports

Automated monthly output of `scripts/freshness_check.py` (see the repo README →
"Automated monthly freshness check"). Each `YYYY-MM-DD.md` file is one run's
diff of the 22 statute-class golden-copy sources against the NY Open Legislation
API. Reports are written here; a run that detects drift opens a
`freshness-drift` PR instead of committing silently. Nothing in this folder
rewrites golden-copy source files.
