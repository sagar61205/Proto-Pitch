"""Database implementation of the job backend.

Leasing is one conditional UPDATE, so two workers can never take the same job. Every write
a worker makes is fenced by ``lease_owner``: a worker that lost its lease cannot record
results.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from protopitch.db.models import Artifact, Job, JobEvent, Project, ProjectVersion, Step, utcnow
from protopitch.db.session import SessionFactory, session_scope
from protopitch.domain.lifecycle import WORKING_STATES, ProjectStatus
from protopitch.errors import LeaseLostError, NotFoundError
from protopitch.jobs.backend import EventView, JobStatus, JobView, StepStatus, StepView
from protopitch.jobs.registry import JobRegistry
from protopitch.security.redaction import Redactor
from protopitch.services import SYSTEM_ACTOR, audit, transition_project

MAX_EVENT_CHARS = 8000


def _job_view(job: Job) -> JobView:
    return JobView(
        id=job.id,
        type=job.type,
        status=job.status,
        project_id=job.project_id,
        version=job.version,
        payload=dict(job.payload or {}),
        workspace_snapshot=job.workspace_snapshot,
        error=job.error,
        leases=job.leases,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        steps=[
            StepView(
                index=s.index,
                name=s.name,
                status=s.status,
                attempt=s.attempt,
                output=s.output,
                error=s.error,
                started_at=s.started_at,
                finished_at=s.finished_at,
            )
            for s in job.steps
        ],
    )


class DbJobBackend:
    def __init__(
        self, sessions: SessionFactory, registry: JobRegistry, redactor: Redactor | None = None
    ) -> None:
        self._sessions = sessions
        self._registry = registry
        self._redactor = redactor or Redactor.from_environment()

    # ----- enqueue -------------------------------------------------------------------------

    def enqueue(
        self,
        job_type: str,
        *,
        project_id: str | None = None,
        version: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        with session_scope(self._sessions) as session:
            return self.enqueue_in(
                session, job_type, project_id=project_id, version=version, payload=payload
            )

    def enqueue_in(
        self,
        session: Session,
        job_type: str,
        *,
        project_id: str | None = None,
        version: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Enqueue inside the caller's transaction (e.g. together with creating a project)."""
        definition = self._registry.get(job_type)
        snapshot: str | None = None
        if (project_id is None) != (version is None):
            raise ValueError("a job belongs to a project and a version, or to neither")
        if definition.uses_workspace and project_id is not None:
            row = session.scalars(
                select(ProjectVersion).where(
                    ProjectVersion.project_id == project_id, ProjectVersion.number == version
                )
            ).first()
            if row is None:
                raise NotFoundError(f"Project {project_id} has no version {version}.")
            snapshot = row.workspace_snapshot
        job = Job(
            type=job_type,
            status=JobStatus.QUEUED,
            project_id=project_id,
            version=version,
            payload=payload or {},
            workspace_snapshot=snapshot,
        )
        job.steps = [
            Step(index=i, name=step.name, status=StepStatus.PENDING)
            for i, step in enumerate(definition.steps)
        ]
        session.add(job)
        session.flush()
        session.add(JobEvent(job_id=job.id, level="info", message=f"Queued job {job_type}."))
        return job.id

    # ----- leasing -------------------------------------------------------------------------

    def lease_next(self, worker_id: str, lease_seconds: float) -> JobView | None:
        now = utcnow()
        available = or_(
            Job.status == JobStatus.QUEUED,
            and_(Job.status == JobStatus.RUNNING, Job.lease_expires_at < now),
        )
        with session_scope(self._sessions) as session:
            candidate = (
                select(Job.id).where(available).order_by(Job.created_at, Job.id).limit(1)
            ).scalar_subquery()
            # The availability test is repeated in the outer WHERE so that a concurrent
            # winner makes this statement match no row instead of taking the job twice.
            result = session.execute(
                update(Job)
                .where(Job.id == candidate, available)
                .values(
                    status=JobStatus.RUNNING,
                    lease_owner=worker_id,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    leases=Job.leases + 1,
                )
                .returning(Job.id)
            )
            job_id = result.scalar_one_or_none()
            if job_id is None:
                return None
            job = session.get(Job, job_id)
            assert job is not None
            session.refresh(job)
            if job.started_at is None:
                job.started_at = now
            recovered = job.leases > 1
            session.add(
                JobEvent(
                    job_id=job.id,
                    level="info",
                    message=(
                        "Recovered after an interruption; resuming from the last completed step."
                        if recovered
                        else "Worker picked up the job."
                    ),
                )
            )
            session.flush()
            return _job_view(job)

    def _fenced(self, session: Session, job_id: str, worker_id: str) -> Job:
        job = session.get(Job, job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} does not exist.")
        if job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
            raise LeaseLostError(f"Worker {worker_id} no longer holds job {job_id}.")
        return job

    def heartbeat(self, job_id: str, worker_id: str, lease_seconds: float) -> bool:
        with session_scope(self._sessions) as session:
            result = session.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == JobStatus.RUNNING,
                    Job.lease_owner == worker_id,
                )
                .values(lease_expires_at=utcnow() + timedelta(seconds=lease_seconds))
                .returning(Job.id)
            )
            return result.scalar_one_or_none() is not None

    def release(self, job_id: str, worker_id: str) -> None:
        """Give a job back to the queue (graceful shutdown); completed steps are kept."""
        with session_scope(self._sessions) as session:
            job = self._fenced(session, job_id, worker_id)
            for step in job.steps:
                if step.status == StepStatus.RUNNING:
                    step.status = StepStatus.PENDING
                    step.attempt = max(0, step.attempt - 1)
            job.status = JobStatus.QUEUED
            job.lease_owner = None
            job.lease_expires_at = None
            session.add(JobEvent(job_id=job_id, level="info", message="Worker released the job."))

    # ----- steps ---------------------------------------------------------------------------

    def start_step(self, job_id: str, worker_id: str, index: int) -> int:
        with session_scope(self._sessions) as session:
            job = self._fenced(session, job_id, worker_id)
            step = job.steps[index]
            step.status = StepStatus.RUNNING
            step.attempt += 1
            step.started_at = utcnow()
            step.error = None
            session.add(
                JobEvent(
                    job_id=job_id,
                    step=step.name,
                    level="info",
                    message=f"Step '{step.name}' started (attempt {step.attempt}).",
                )
            )
            return step.attempt

    def complete_step(
        self,
        job_id: str,
        worker_id: str,
        index: int,
        output: dict[str, Any],
        workspace_snapshot: str | None,
    ) -> None:
        with session_scope(self._sessions) as session:
            job = self._fenced(session, job_id, worker_id)
            step = job.steps[index]
            step.status = StepStatus.SUCCEEDED
            step.output = output
            step.finished_at = utcnow()
            job.workspace_snapshot = workspace_snapshot
            for item in output.get("artifacts", []) or []:
                session.add(
                    Artifact(
                        project_id=job.project_id,
                        version=job.version,
                        job_id=job.id,
                        kind=str(item["kind"]),
                        name=str(item["name"]),
                        sha256=str(item["sha256"]),
                        size=int(item["size"]),
                    )
                )
            session.add(
                JobEvent(
                    job_id=job_id,
                    step=step.name,
                    level="info",
                    message=f"Step '{step.name}' completed.",
                )
            )

    def fail_step(
        self, job_id: str, worker_id: str, index: int, error: dict[str, Any], *, retry: bool
    ) -> None:
        with session_scope(self._sessions) as session:
            job = self._fenced(session, job_id, worker_id)
            step = job.steps[index]
            step.status = StepStatus.PENDING if retry else StepStatus.FAILED
            step.error = self._clean(error)
            step.finished_at = utcnow()
            session.add(
                JobEvent(
                    job_id=job_id,
                    step=step.name,
                    level="error",
                    message=self._redactor.redact(
                        f"Step '{step.name}' failed on attempt {step.attempt}: "
                        f"{error.get('message', '')}" + (" Retrying." if retry else "")
                    )[:MAX_EVENT_CHARS],
                )
            )

    # ----- completion ----------------------------------------------------------------------

    def complete_job(self, job_id: str, worker_id: str) -> None:
        definition_hook = None
        with session_scope(self._sessions) as session:
            job = self._fenced(session, job_id, worker_id)
            if any(s.status != StepStatus.SUCCEEDED for s in job.steps):
                raise ValueError("a job can only complete when every step has succeeded")
            job.status = JobStatus.SUCCEEDED
            job.finished_at = utcnow()
            job.lease_owner = None
            job.lease_expires_at = None
            definition = self._registry.get(job.type)
            if definition.uses_workspace and job.project_id and job.version is not None:
                row = session.scalars(
                    select(ProjectVersion).where(
                        ProjectVersion.project_id == job.project_id,
                        ProjectVersion.number == job.version,
                    )
                ).first()
                if row is not None:
                    row.workspace_snapshot = job.workspace_snapshot
            definition_hook = definition.on_success
            if definition_hook is not None:
                session.flush()
                definition_hook(session, _job_view(job))
            session.add(JobEvent(job_id=job_id, level="info", message="Job completed."))

    def fail_job(self, job_id: str, worker_id: str, error: dict[str, Any]) -> None:
        with session_scope(self._sessions) as session:
            job = self._fenced(session, job_id, worker_id)
            self._fail(session, job, error)

    def _fail(self, session: Session, job: Job, error: dict[str, Any]) -> None:
        clean = self._clean(error)
        job.status = JobStatus.FAILED
        job.error = clean
        job.finished_at = utcnow()
        job.lease_owner = None
        job.lease_expires_at = None
        session.add(
            JobEvent(
                job_id=job.id,
                level="error",
                message=f"Job failed: {clean.get('message', '')}"[:MAX_EVENT_CHARS],
            )
        )
        definition = self._registry.get(job.type)
        if definition.fails_project and job.project_id:
            project = session.get(Project, job.project_id)
            if project is not None and ProjectStatus(project.status) in WORKING_STATES:
                failed_step = next(
                    (s.name for s in job.steps if s.status != StepStatus.SUCCEEDED), None
                )
                transition_project(
                    session,
                    project,
                    ProjectStatus.FAILED,
                    actor=SYSTEM_ACTOR,
                    failure={"job_id": job.id, "job_type": job.type, "step": failed_step, **clean},
                )
        audit(
            session,
            actor=SYSTEM_ACTOR,
            action="job.failed",
            subject_type="job",
            subject_id=job.id,
            details=clean,
        )

    def retry_failed(self, session: Session, job_id: str) -> None:
        """Put a failed job back on the queue, keeping every completed step (resume)."""
        job = session.get(Job, job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} does not exist.")
        if job.status != JobStatus.FAILED:
            return
        for step in job.steps:
            if step.status != StepStatus.SUCCEEDED:
                step.status = StepStatus.PENDING
                step.attempt = 0
                step.error = None
        job.status = JobStatus.QUEUED
        job.error = None
        job.finished_at = None
        job.created_at = utcnow()  # the deadline restarts with the owner's resume
        job.started_at = None
        session.add(JobEvent(job_id=job.id, level="info", message="Resumed by the owner."))

    # ----- events and reads ----------------------------------------------------------------

    def append_event(self, job_id: str, level: str, message: str, step: str | None = None) -> None:
        with session_scope(self._sessions) as session:
            session.add(
                JobEvent(
                    job_id=job_id,
                    step=step,
                    level=level,
                    message=self._redactor.redact(message)[:MAX_EVENT_CHARS],
                )
            )

    def get_job(self, job_id: str) -> JobView:
        with session_scope(self._sessions) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise NotFoundError(f"Job {job_id} does not exist.")
            return _job_view(job)

    def list_jobs(self, project_id: str | None = None, limit: int = 50) -> list[JobView]:
        with session_scope(self._sessions) as session:
            query = select(Job).order_by(Job.created_at.desc()).limit(limit)
            if project_id is not None:
                query = query.where(Job.project_id == project_id)
            return [_job_view(job) for job in session.scalars(query)]

    def events_after(self, job_id: str, after_id: int, limit: int = 500) -> list[EventView]:
        with session_scope(self._sessions) as session:
            rows = session.scalars(
                select(JobEvent)
                .where(JobEvent.job_id == job_id, JobEvent.id > after_id)
                .order_by(JobEvent.id)
                .limit(limit)
            )
            return [
                EventView(
                    id=r.id,
                    job_id=r.job_id,
                    step=r.step,
                    level=r.level,
                    message=r.message,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    def _clean(self, error: dict[str, Any]) -> dict[str, Any]:
        return {
            key: self._redactor.redact(value)[:MAX_EVENT_CHARS] if isinstance(value, str) else value
            for key, value in error.items()
        }


def deadline_passed(job: JobView, deadline_seconds: float, now: datetime | None = None) -> bool:
    return ((now or utcnow()) - job.created_at).total_seconds() > deadline_seconds
