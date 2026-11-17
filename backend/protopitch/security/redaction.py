"""Redaction of secrets from anything that is logged or streamed to the UI."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping

REDACTED = "[REDACTED]"

_SENSITIVE_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.IGNORECASE)

# Shapes of common credentials. Deliberately generic: no provider-specific logic lives here.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(authorization\s*[:=]\s*(?:bearer|basic)\s+)[^\s\"']+"),
    re.compile(
        r"(?i)\b((?:api[_-]?key|token|secret|password|passwd)\s*[:=]\s*[\"']?)[^\s\"',;]{6,}"
    ),
)


class Redactor:
    """Replaces known secret values and credential-shaped strings with a marker."""

    def __init__(self, secret_values: Iterable[str] = ()) -> None:
        self._values = sorted({v for v in secret_values if len(v) >= 8}, key=len, reverse=True)

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> Redactor:
        source = os.environ if env is None else env
        return cls(v for k, v in source.items() if _SENSITIVE_NAME.search(k))

    def redact(self, text: str) -> str:
        for value in self._values:
            if value in text:
                text = text.replace(value, REDACTED)
        for pattern in _PATTERNS:
            if pattern.groups:
                text = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", text)
            else:
                text = pattern.sub(REDACTED, text)
        return text
