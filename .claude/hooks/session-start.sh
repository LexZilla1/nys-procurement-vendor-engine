#!/bin/bash
# SessionStart hook — install the optional LLM dependencies so the Step 4 live
# classifier (pipeline/llm_classifier.py), the llm_reader, and their tests can
# run in Claude Code on the web. The stdlib engine (validator, tender_extractor,
# triage rule layer, parser, freshness checker) needs NONE of this, so a failed
# install is non-fatal — it only disables the LLM-backed paths.
set -euo pipefail

# Web only: no-op on local/desktop sessions.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Idempotent: pip skips already-satisfied requirements (installs anthropic +
# python-dotenv from requirements.txt). Non-fatal so a transient PyPI hiccup
# never blocks the session — the stdlib paths still work.
if ! python3 -m pip install --quiet --disable-pip-version-check --root-user-action=ignore -r requirements.txt; then
  echo "session-start: 'pip install -r requirements.txt' failed; LLM-backed features (Step 4, llm_reader) will be unavailable this session, but the stdlib engine is unaffected." >&2
fi
