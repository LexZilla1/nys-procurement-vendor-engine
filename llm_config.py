"""LLM configuration check.

Reports whether the ANTHROPIC_API_KEY environment variable is available to the
application. Prints only presence and length -- never the secret value itself.
"""

import os


def check_api_key(name: str = "ANTHROPIC_API_KEY") -> bool:
    value = os.environ.get(name)
    if value:
        print(f"{name}: set ({len(value)} chars)")
        return True
    print(f"{name}: NOT set")
    return False


if __name__ == "__main__":
    check_api_key()
