"""Database schema (ARCHITECTURE §6). M1 covers the foundation entities only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timestamps are stored and returned as timezone-aware UTC on every database."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; timestamps must be timezone-aware UTC")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, datetime: UTCDateTime}


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    jd_url: Mapped[str | None] = mapped_column(String(2000))
    context: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), index=True)
    failed_from: Mapped[str | None] = mapped_column(String(40))
    failure: Mapped[dict[str, Any] | None]
    previous_status: Mapped[str | None] = mapped_column(String(40))
    active_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    versions: Mapped[list[ProjectVersion]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectVersion.number"
    )
    jd_documents: Mapped[list[JDDocument]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectVersion(Base):
    __tablename__ = "project_versions"
    __table_args__ = (UniqueConstraint("project_id", "number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    parent_number: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    status_snapshot: Mapped[str | None] = mapped_column(String(40))
    # Content hash of the workspace tree in the artifact store; the source of truth.
    workspace_snapshot: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    project: Mapped[Project] = relationship(back_populates="versions")


class JDDocument(Base):
    """The original job description. Immutable once stored."""

    __tablename__ = "jd_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(2000))
    language: Mapped[str | None] = mapped_column(String(16))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    project: Mapped[Project] = relationship(back_populates="jd_documents")


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (Index("ix_artifacts_project", "project_id", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    version: Mapped[int | None] = mapped_column(Integer)
    job_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_queue", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int | None] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None]
    leases: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[dict[str, Any] | None]
    workspace_snapshot: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    steps: Mapped[list[Step]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Step.index"
    )


class Step(Base):
    __tablename__ = "steps"
    __table_args__ = (UniqueConstraint("job_id", "index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict[str, Any] | None]
    error: Mapped[dict[str, Any] | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    job: Mapped[Job] = relationship(back_populates="steps")


class JobEvent(Base):
    """Progress and log lines for a job; streamed to the UI over server-sent events."""

    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    step: Mapped[str | None] = mapped_column(String(80))
    level: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class WorkerStatus(Base):
    """What each worker last reported about itself. Lets the API describe sandbox
    capability where the worker runs, which may not be where the API runs."""

    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    sandbox: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Approval(Base):
    """A recorded owner decision bound to the hash of the exact payload it authorises."""

    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_lookup", "kind", "payload_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(60))
    payload_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(12))
    comment: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    consumed_at: Mapped[datetime | None]


class AuditEvent(Base):
    """Append-only history. Rows are never updated or deleted, including on project deletion."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    subject_type: Mapped[str] = mapped_column(String(40))
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
