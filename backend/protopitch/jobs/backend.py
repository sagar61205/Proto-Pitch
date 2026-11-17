"""The job backend interface.

Workers talk to the platform only through this protocol, with plain data in and out, so a
later HTTP implementation lets workers run on other machines (ARCHITECTURE §13).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TERMINAL = frozenset({"succeeded", "failed"})


class StepStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class StepView:
    index: int
    name: str
    status: str
    attempt: int
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class JobView:
    id: str
    type: str
    status: str
    project_id: str | None
    version: int | None
    payload: dict[str, Any]
    workspace_snapshot: str | None
    error: dict[str, Any] | None
    leases: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    steps: list[StepView] = field(default_factory=list)


@dataclass(frozen=True)
class EventView:
    id: int
    job_id: str
    step: str | None
    level: str
    message: str
    created_at: datetime


class JobBackend(Protocol):
    def enqueue(
        self,
        job_type: str,
        *,
        project_id: str | None = None,
        version: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str: ...

    def lease_next(self, worker_id: str, lease_seconds: float) -> JobView | None: ...
    def heartbeat(self, job_id: str, worker_id: str, lease_seconds: float) -> bool: ...
    def release(self, job_id: str, worker_id: str) -> None: ...
    def start_step(self, job_id: str, worker_id: str, index: int) -> int: ...
    def complete_step(
        self,
        job_id: str,
        worker_id: str,
        index: int,
        output: dict[str, Any],
        workspace_snapshot: str | None,
    ) -> None: ...
    def fail_step(
        self, job_id: str, worker_id: str, index: int, error: dict[str, Any], *, retry: bool
    ) -> None: ...
    def complete_job(self, job_id: str, worker_id: str) -> None: ...
    def fail_job(self, job_id: str, worker_id: str, error: dict[str, Any]) -> None: ...
    def append_event(
        self, job_id: str, level: str, message: str, step: str | None = None
    ) -> None: ...
    def report_worker(self, worker_id: str, sandbox: dict[str, Any]) -> None: ...
    def get_job(self, job_id: str) -> JobView: ...
    def events_after(self, job_id: str, after_id: int, limit: int = 500) -> list[EventView]: ...
