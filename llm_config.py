#!/usr/bin/env python3
"""
Central config for the (future) LLM-based RFP reader — BUILD SPEC v2 §14.

Loads ANTHROPIC_API_KEY from the environment. Precedence:
  1. A real environment variable (e.g. injected by the Claude Code on the web
     environment's secret settings) — the recommended, most-secure source.
  2. A local .env file (gitignored, NEVER committed), loaded as a fallback if
     python-dotenv is installed.

The key is NEVER hardcoded in this file or anywhere in the repo. This module is
deliberately SEPARATE from tender_extractor.py, whose stdlib-only privacy
guarantee (§11) forbids importing an LLM SDK.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
_PLACEHOLDER = "sk-ant-REPLACE_ME"  # the value in .env.example — treated as unset


def _load_env_file():
    """Load .env if present. python-dotenv is optional; a real environment
    variable works without it. override=False so an env-var secret always wins."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(os.path.join(HERE, ".env"), override=False)


_load_env_file()


def get_anthropic_api_key(required=True):
    """Return the Anthropic API key, or raise a clear error if it's missing.
    The .env.example placeholder is treated as 'not set' so a forgotten copy
    fails loudly instead of sending a bogus key."""
    key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if key and key != _PLACEHOLDER:
        return key
    if required:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Set it as an environment secret in "
            "your Claude Code on the web environment settings (recommended), or "
            "in a local .env file (gitignored — see .env.example). It is never "
            "stored in the repository.")
    return None


def has_anthropic_api_key():
    """True if a usable key is present (no exception). Handy for skipping LLM
    paths / tests when no key is configured."""
    return get_anthropic_api_key(required=False) is not None


# The pipeline's default model. Externalised via ANTHROPIC_MODEL so a single
# env var moves every call site together (triage today, advisory later) and no
# call site mixes models mid-pipeline. The default preserves the existing model
# — any move to a newer model is a separate, deliberate change, never implicit.
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


def get_anthropic_model():
    """Return the configured Anthropic model id. Reads ANTHROPIC_MODEL from the
    environment; a blank/unset value falls back to DEFAULT_ANTHROPIC_MODEL
    (claude-sonnet-4-6). Never raises — model selection must not be a failure
    path."""
    model = (os.getenv("ANTHROPIC_MODEL") or "").strip()
    return model or DEFAULT_ANTHROPIC_MODEL


if __name__ == "__main__":
    # Safe status check — reports presence + length only, NEVER the value.
    k = get_anthropic_api_key(required=False)
    if k:
        print("ANTHROPIC_API_KEY: set ({} chars)".format(len(k)))
    else:
        print("ANTHROPIC_API_KEY: NOT set")
    print("ANTHROPIC_MODEL: {}".format(get_anthropic_model()))
