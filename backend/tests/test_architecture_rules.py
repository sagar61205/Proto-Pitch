"""Guards for rules in AGENTS.md and DEVELOPMENT_GUIDE.md that code review alone would miss."""

from __future__ import annotations

import ast
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "protopitch"
SOURCES = [p for p in PACKAGE.rglob("*.py") if "migrations/versions" not in p.as_posix()]

NETWORK_MODULES = {
    "socket",
    "urllib",
    "urllib.request",
    "http.client",
    "httpx",
    "requests",
    "aiohttp",
    "ftplib",
    "smtplib",
    "telnetlib",
    "ssl",
}  # fmt: skip  (urllib.parse only parses text and is fine)
# Only these may open connections. The sandbox driver talks to 127.0.0.1 for local preview.
# intelligence/research, providers, deploy and scm join this list in their milestones.
NETWORK_ALLOWED = {"sandbox/docker.py", "jobs/worker.py"}

PROVIDER_WORDS = re.compile(
    r"anthropic|openai|gemini|ollama|claude|gpt-|mistral|cohere|llama", re.IGNORECASE
)
# Provider-specific identifiers are allowed only in provider adapters (and configuration).
PROVIDER_ALLOWED_PREFIX = "providers/"


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_only_designated_modules_can_open_network_connections() -> None:
    offenders = {}
    for path in SOURCES:
        relative = path.relative_to(PACKAGE).as_posix()
        used = _imports(path) & NETWORK_MODULES
        if used and relative not in NETWORK_ALLOWED:
            offenders[relative] = sorted(used)
    assert offenders == {}, f"network-capable imports outside the allowed modules: {offenders}"


def test_worker_uses_socket_only_for_its_identity() -> None:
    source = (PACKAGE / "jobs/worker.py").read_text()
    assert re.findall(r"socket\.(\w+)", source) == ["gethostname"]


def test_core_code_names_no_model_provider() -> None:
    offenders = []
    for path in SOURCES:
        relative = path.relative_to(PACKAGE).as_posix()
        if relative.startswith(PROVIDER_ALLOWED_PREFIX):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PROVIDER_WORDS.search(line):
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert offenders == [], "provider-specific identifiers in core code:\n" + "\n".join(offenders)


def test_domain_imports_nothing_from_the_rest_of_the_platform() -> None:
    for path in (PACKAGE / "domain").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        outside = [
            line for line in source.splitlines()
            if re.match(r"\s*(from|import) protopitch", line) and "protopitch.domain" not in line
        ]  # fmt: skip
        assert outside == [], f"{path.name} depends on {outside}"


def test_no_print_statements_in_platform_code() -> None:
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
                raise AssertionError(f"print() in {path.relative_to(PACKAGE)}; use the logger")
