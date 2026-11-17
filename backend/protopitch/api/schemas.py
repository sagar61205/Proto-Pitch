"""Request and response models. The frontend's types are generated from these."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from protopitch.domain.lifecycle import ProjectStatus


def _clean(value: str) -> str:
    return value.strip()


def _http_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("must be an http or https URL")
    return value


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    jd_text: str = Field(min_length=1, max_length=200_000)
    jd_url: str | None = Field(default=None, max_length=2000)
    context: str | None = Field(default=None, max_length=20_000)

    _strip = field_validator("company", "role", "jd_text")(_clean)
    _url = field_validator("jd_url")(_http_url)

    @field_validator("company", "role", "jd_text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be blank")
        return value


class ProjectUpdate(BaseModel):
    """The job description itself is immutable; these fields are editable."""

    model_config = ConfigDict(extra="forbid")

    company: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=200)
    jd_url: str | None = Field(default=None, max_length=2000)
    context: str | None = Field(default=None, max_length=20_000)

    _url = field_validator("jd_url")(_http_url)


OwnerAction = Literal["archive", "unarchive", "resume"]


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: OwnerAction


class ProjectOut(BaseModel):
    id: str
    company: str
    role: str
    jd_url: str | None
    context: str | None
    status: ProjectStatus
    failed_from: ProjectStatus | None
    failure: dict[str, Any] | None
    active_version: int
    owner_actions: list[OwnerAction]
    created_at: datetime
    updated_at: datetime


class JDOut(BaseModel):
    text: str
    url: str | None
    content_hash: str
    created_at: datetime


class VersionOut(BaseModel):
    number: int
    parent_number: int | None
    reason: str | None
    workspace_snapshot: str | None
    created_at: datetime


class StepOut(BaseModel):
    index: int
    name: str
    status: str
    attempt: int
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    started_at: datetime | None
    finished_at: datetime | None


class JobOut(BaseModel):
    id: str
    type: str
    status: str
    project_id: str | None
    version: int | None
    error: dict[str, Any] | None
    leases: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    steps: list[StepOut]


class ProjectDetail(ProjectOut):
    jd: JDOut
    versions: list[VersionOut]
    jobs: list[JobOut]


class ApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=60)
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["approved", "rejected"]
    project_id: str | None = None
    comment: str | None = Field(default=None, max_length=2000)


class ApprovalOut(BaseModel):
    id: str
    kind: str
    payload_hash: str
    decision: str
    project_id: str | None
    comment: str | None
    created_at: datetime
    consumed_at: datetime | None


class ActionPlan(BaseModel):
    """What an approval-gated action will do, and the hash an approval must be bound to."""

    kind: str
    payload_hash: str
    summary: str
    consequences: list[str]


class ProfileOut(BaseModel):
    profile: str
    image: str | None
    present: bool
    image_digest: str | None
    lock_hash: str | None


class SandboxStatus(BaseModel):
    available: bool
    driver: str
    reason: str | None
    profiles: list[ProfileOut]


class SystemStatus(BaseModel):
    version: str
    generation_available: bool
    sandbox: SandboxStatus
    # No model provider is needed or configured in M1; the deterministic platform is complete.
    model_providers_configured: list[str]
    job_types: list[str]


class ErrorBody(BaseModel):
    code: str
    message: str
    next_actions: list[str]


class ErrorResponse(BaseModel):
    error: ErrorBody
