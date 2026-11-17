"""Job types are registered, never hard-wired into the worker (extension by registration)."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from protopitch.jobs.backend import JobView

if TYPE_CHECKING:
    from protopitch.sandbox.driver import SandboxDriver
    from protopitch.settings import Settings
    from protopitch.storage.artifacts import ArtifactStore


class PermanentStepError(Exception):
    """Raised by a step when retrying cannot help; the job fails immediately."""

    def __init__(self, message: str, *, code: str = "step_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class StepContext:
    """Everything a step may use. Steps reach the platform only through this object."""

    job: JobView
    step_name: str
    attempt: int
    workspace: Path | None
    settings: Settings
    artifacts: ArtifactStore
    sandbox: SandboxDriver
    log: Callable[[str], None]
    previous: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def payload(self) -> dict[str, Any]:
        return self.job.payload


StepHandler = Callable[[StepContext], dict[str, Any] | None]
JobHook = Callable[[Session, JobView], None]


@dataclass(frozen=True)
class StepDefinition:
    name: str
    handler: StepHandler


@dataclass(frozen=True)
class JobDefinition:
    type: str
    steps: tuple[StepDefinition, ...]
    uses_workspace: bool = False
    # When a job of this type fails, its project moves to FAILED (resumable).
    fails_project: bool = False
    on_success: JobHook | None = None


class JobRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, JobDefinition] = {}

    def register(self, definition: JobDefinition) -> JobDefinition:
        if definition.type in self._definitions:
            raise ValueError(f"job type already registered: {definition.type}")
        names = [s.name for s in definition.steps]
        if not names or len(set(names)) != len(names):
            raise ValueError(f"job {definition.type} needs uniquely named steps")
        self._definitions[definition.type] = definition
        return definition

    def get(self, job_type: str) -> JobDefinition:
        try:
            return self._definitions[job_type]
        except KeyError:
            raise KeyError(f"unknown job type: {job_type}") from None

    def types(self) -> list[str]:
        return sorted(self._definitions)


def build_registry(extra_modules: Iterable[str] = ()) -> JobRegistry:
    """Built-in job types plus any module that exposes ``register(registry)``."""
    registry = JobRegistry()
    for module_name in ("protopitch.jobs.builtin", *extra_modules):
        module = importlib.import_module(module_name)
        module.register(registry)
    return registry
