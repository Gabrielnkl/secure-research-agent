# app/security/policy.py
import re
from app.models import SecurityVerdict


# Static patterns that are always blocked regardless of LLM verdict
INPUT_BLOCKLIST = [
    r"ignore\s+(previous|all|above)\s+instructions",
    r"system\s*prompt",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode",
    r"<\|.*?\|>",           # Common injection delimiters
    r"\[SYSTEM\]",
    r"\[INST\]",
]

MAX_INPUT_LENGTH = 2000


class PolicyViolationError(Exception):
    """Raised when input fails policy checks. Non-retryable."""
    pass


def check_input_policy(text: str, quarantine_verdict: SecurityVerdict) -> None:
    """
    Enforce input policy. Raises PolicyViolationError if the input is blocked.
    Called at the start of every workflow run.
    """
    # Rule 1: length
    if len(text) > MAX_INPUT_LENGTH:
        raise PolicyViolationError(
            f"Input exceeds maximum length ({len(text)} > {MAX_INPUT_LENGTH})"
        )

    # Rule 2: static blocklist (fast, no LLM needed)
    for pattern in INPUT_BLOCKLIST:
        if re.search(pattern, text, re.IGNORECASE):
            raise PolicyViolationError(
                f"Input matches blocked pattern: {pattern}"
            )

    # Rule 3: quarantine LLM verdict
    if not quarantine_verdict.safe:
        raise PolicyViolationError(
            f"Quarantine LLM blocked input: {quarantine_verdict.reason}"
        )


def check_output_policy(summary: str, key_points: list[str]) -> SecurityVerdict:
    """
    Check synthesized output before returning to the user.
    Returns a verdict — caller decides whether to block.
    """
    combined = summary + " ".join(key_points)

    OUTPUT_BLOCKLIST = [
        r"\bSSN\b",
        r"\b\d{3}-\d{2}-\d{4}\b",          # SSN pattern
        r"\b4[0-9]{12}(?:[0-9]{3})?\b",    # Credit card pattern
        r"(password|passwd|secret)\s*[:=]", # Credential leakage
    ]

    for pattern in OUTPUT_BLOCKLIST:
        if re.search(pattern, combined, re.IGNORECASE):
            return SecurityVerdict(
                safe=False,
                reason=f"Output contains potentially sensitive data pattern: {pattern}",
            )

    return SecurityVerdict(safe=True, reason="Output passed all policy checks.")