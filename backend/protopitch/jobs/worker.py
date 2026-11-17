"""The worker: leases jobs and runs their steps, one at a time.

Recovery model: a step is the unit of progress. Before a step the workspace is materialised
from the job's last snapshot; after it the workspace is saved and the step is marked done
in one fenced write. If the worker dies, its lease expires and any worker continues from
the first step that is not done.
"""

from __future__ import annotations

import os
import shutil
import socket
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from protopitch.errors import LeaseLostError, PlatformError
from protopitch.jobs.backend import JobBackend, JobView, StepStatus
from protopitch.jobs.db_backend import deadline_passed
from protopitch.jobs.registry import JobRegistry, PermanentStepError, StepContext
from protopitch.logging_setup import get_logger
from protopitch.sandbox.driver import SandboxDriver
from protopitch.settings import Settings
from protopitch.storage.artifacts import ArtifactStore
from protopitch.storage.workspace import WorkspaceManager

log = get_logger("worker")


class _Heartbeat(threading.Thread):
    def __init__(self, backend: JobBackend, job_id: str, worker_id: str, settings: Settings):
        super().__init__(daemon=True)
        self._backend = backend
        self._job_id = job_id
        self._worker_id = worker_id
        self._settings = settings
        self._stop = threading.Event()
        self.lost = False

    def run(self) -> None:
        jobs = self._settings.jobs
        while not self._stop.wait(jobs.heartbeat_seconds):
            try:
                if not self._backend.heartbeat(self._job_id, self._worker_id, jobs.lease_seconds):
                    self.lost = True
                    return
            except Exception:  # noqa: BLE001 - keep trying; expiry is the safety net
                log.warning("heartbeat failed", extra={"job_id": self._job_id})

    def stop(self) -> None:
        self._stop.set()


class Worker:
    def __init__(
        self,
        *,
        settings: Settings,
        backend: JobBackend,
        registry: JobRegistry,
        artifacts: ArtifactStore,
        workspaces: WorkspaceManager,
        sandbox: SandboxDriver,
        worker_id: str | None = None,
    ) -> None:
        self._settings = settings
        self._backend = backend
        self._registry = registry
        self._artifacts = artifacts
        self._workspaces = workspaces
        self._sandbox = sandbox
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._stopping = threading.Event()

    def request_stop(self) -> None:
        self._stopping.set()

    def report(self) -> None:
        """Tell the platform this worker is alive and what its sandbox can do."""
        try:
            self._backend.report_worker(self.worker_id, asdict(self._sandbox.probe()))
        except Exception:  # noqa: BLE001 - reporting must never stop the worker
            log.warning("could not report worker status", extra={"worker_id": self.worker_id})

    def run_forever(self) -> None:
        log.info("worker started", extra={"worker_id": self.worker_id})
        last_report = float("-inf")
        while not self._stopping.is_set():
            if time.monotonic() - last_report >= self._settings.jobs.worker_report_seconds:
                self.report()
                last_report = time.monotonic()
            if not self.run_once():
                self._stopping.wait(self._settings.jobs.poll_interval_seconds)
        log.info("worker stopped", extra={"worker_id": self.worker_id})

    def run_once(self) -> bool:
        """Lease and process one job. Returns False when the queue is empty."""
        job = self._backend.lease_next(self.worker_id, self._settings.jobs.lease_seconds)
        if job is None:
            return False
        heartbeat = _Heartbeat(self._backend, job.id, self.worker_id, self._settings)
        heartbeat.start()
        try:
            self._process(job, heartbeat)
        except LeaseLostError:
            log.warning("lease lost; abandoning job", extra={"job_id": job.id})
        finally:
            heartbeat.stop()
        return True

    # ----- one job -------------------------------------------------------------------------

    def _logger(self, job_id: str, step_name: str) -> Callable[[str], None]:
        def write(message: str) -> None:
            self._backend.append_event(job_id, "info", message, step_name)

        return write

    def _workspace_dir(self, job: JobView) -> Path:
        if job.project_id is not None and job.version is not None:
            return self._workspaces.path_for(job.project_id, job.version)
        return self._workspaces.scratch_path(job.id)

    def _process(self, job: JobView, heartbeat: _Heartbeat) -> None:
        definition = self._registry.get(job.type)
        jobs = self._settings.jobs
        snapshot = job.workspace_snapshot
        previous = {s.name: (s.output or {}) for s in job.steps if s.status == StepStatus.SUCCEEDED}
        workspace = self._workspace_dir(job) if definition.uses_workspace else None

        for index, step_def in enumerate(definition.steps):
            if job.steps[index].status == StepStatus.SUCCEEDED:
                continue
            while True:
                if self._stopping.is_set():
                    self._backend.release(job.id, self.worker_id)
                    return
                if heartbeat.lost:
                    raise LeaseLostError("lease lost")
                if deadline_passed(job, jobs.job_deadline_seconds):
                    self._backend.fail_job(
                        job.id,
                        self.worker_id,
                        {
                            "code": "deadline_exceeded",
                            "message": "The job exceeded its time limit.",
                        },
                    )
                    return
                attempt = self._backend.start_step(job.id, self.worker_id, index)
                try:
                    if workspace is not None:
                        self._workspaces.materialise(workspace, snapshot)
                        self._workspaces.begin_changes(workspace)
                    context = StepContext(
                        job=job,
                        step_name=step_def.name,
                        attempt=attempt,
                        workspace=workspace,
                        settings=self._settings,
                        artifacts=self._artifacts,
                        sandbox=self._sandbox,
                        log=self._logger(job.id, step_def.name),
                        previous=previous,
                    )
                    output = step_def.handler(context) or {}
                    if heartbeat.lost:
                        raise LeaseLostError("lease lost")
                    new_snapshot = self._workspaces.save(workspace) if workspace else snapshot
                    self._backend.complete_step(job.id, self.worker_id, index, output, new_snapshot)
                    snapshot = new_snapshot
                    previous[step_def.name] = output
                    break
                except LeaseLostError:
                    raise
                except Exception as exc:  # noqa: BLE001 - every step failure is recorded
                    permanent = isinstance(exc, PermanentStepError | PlatformError)
                    retry = not permanent and attempt < jobs.max_step_attempts
                    error = {
                        "code": getattr(exc, "code", "step_failed"),
                        "message": str(exc) or exc.__class__.__name__,
                        "step": step_def.name,
                        "attempt": attempt,
                        "trace": traceback.format_exc(limit=8),
                    }
                    self._backend.fail_step(job.id, self.worker_id, index, error, retry=retry)
                    if not retry:
                        self._backend.fail_job(job.id, self.worker_id, error)
                        return

        self._backend.complete_job(job.id, self.worker_id)
        if workspace is not None and job.project_id is None:
            shutil.rmtree(workspace, ignore_errors=True)
