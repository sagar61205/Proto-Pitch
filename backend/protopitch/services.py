"""Lifecycle, approval and audit services. All side effects on projects go through here."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from protopitch.db.models import (
    Approval,
    Artifact,
    AuditEvent,
    JDDocument,
    Job,
    Project,
    ProjectVersion,
    utcnow,
)
from protopitch.domain.lifecycle import (
    ProjectStatus,
    TransitionKind,
    TransitionRefused,
    plan_transition,
)
from protopitch.errors import ApprovalRequiredError, IllegalTransitionError, NotFoundError

SYSTEM_ACTOR = "system"


def audit(
    session: Session,
    *,
    actor: str,
    action: str,
    subject_type: str,
    subject_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            details=details or {},
        )
    )


def get_project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} does not exist.")
    return project


class ApprovalGate:
    """Refuses a side-effecting operation unless a matching approval has been recorded."""

    @staticmethod
    def record(
        session: Session,
        *,
        kind: str,
        payload_hash: str,
        decision: str,
        actor: str,
        project_id: str | None = None,
        comment: str | None = None,
    ) -> Approval:
        approval = Approval(
            kind=kind,
            payload_hash=payload_hash,
            decision=decision,
            actor=actor,
            project_id=project_id,
            comment=comment,
        )
        session.add(approval)
        session.flush()
        audit(
            session,
            actor=actor,
            action=f"approval.{decision}",
            subject_type="approval",
            subject_id=approval.id,
            details={"kind": kind, "payload_hash": payload_hash, "project_id": project_id},
        )
        return approval

    @staticmethod
    def consume(
        session: Session, *, kind: str, payload_hash: str | None, project_id: str | None
    ) -> Approval:
        """Use up one approval for exactly this kind, project and payload, or refuse."""
        refusal = ApprovalRequiredError(
            f"This action needs a recorded approval of kind '{kind}' for exactly this request.",
            next_actions=["Review the plan for this action and approve it, then retry."],
        )
        if not payload_hash:
            raise refusal
        approval = session.scalars(
            select(Approval)
            .where(
                Approval.kind == kind,
                Approval.payload_hash == payload_hash,
                Approval.decision == "approved",
                Approval.consumed_at.is_(None),
                Approval.project_id == project_id
                if project_id is not None
                else Approval.project_id.is_(None),
            )
            .order_by(Approval.created_at.desc())
            .limit(1)
        ).first()
        if approval is None:
            raise refusal
        approval.consumed_at = utcnow()
        return approval


def project_blob_hashes(session: Session, project_id: str) -> set[str]:
    """Every artifact-store blob this project refers to."""
    hashes: set[str] = set()
    hashes.update(
        session.scalars(select(JDDocument.content_hash).where(JDDocument.project_id == project_id))
    )
    hashes.update(session.scalars(select(Artifact.sha256).where(Artifact.project_id == project_id)))
    for column, owner in (
        (ProjectVersion.workspace_snapshot, ProjectVersion.project_id),
        (Job.workspace_snapshot, Job.project_id),
    ):
        hashes.update(h for h in session.scalars(select(column).where(owner == project_id)) if h)
    return hashes


def blobs_still_referenced(session: Session, hashes: set[str]) -> set[str]:
    """Of ``hashes``, those some remaining record still needs (the store is shared)."""
    if not hashes:
        return set()
    kept: set[str] = set()
    for column in (
        JDDocument.content_hash,
        Artifact.sha256,
        ProjectVersion.workspace_snapshot,
        Job.workspace_snapshot,
    ):
        kept.update(h for h in session.scalars(select(column).where(column.in_(hashes))) if h)
    return kept


def transition_project(
    session: Session,
    project: Project,
    target: ProjectStatus,
    *,
    actor: str,
    approval_payload_hash: str | None = None,
    failure: dict[str, Any] | None = None,
    reason: str | None = None,
) -> Project:
    """Apply one lifecycle transition, enforcing the transition table and approval gates."""
    current = ProjectStatus(project.status)
    try:
        plan = plan_transition(
            current,
            target,
            failed_from=ProjectStatus(project.failed_from) if project.failed_from else None,
            previous_status=(
                ProjectStatus(project.previous_status) if project.previous_status else None
            ),
        )
    except TransitionRefused as exc:
        raise IllegalTransitionError(
            f"Cannot move this project from {current} to {target}: {exc.reason}.",
            next_actions=["Check the project's current status and the allowed next steps."],
        ) from exc

    approval_id: str | None = None
    if plan.approval_kind is not None:
        approval_id = ApprovalGate.consume(
            session,
            kind=plan.approval_kind,
            payload_hash=approval_payload_hash,
            project_id=project.id,
        ).id

    if plan.kind is TransitionKind.FAIL:
        project.failed_from = current.value
        project.failure = failure or {}
    elif plan.kind is TransitionKind.RESUME:
        project.failed_from = None
        project.failure = None
    elif plan.kind is TransitionKind.ARCHIVE:
        project.previous_status = current.value
    elif plan.kind is TransitionKind.UNARCHIVE:
        project.previous_status = None

    project.status = target.value
    project.updated_at = utcnow()
    audit(
        session,
        actor=actor,
        action=f"project.{plan.kind.value}",
        subject_type="project",
        subject_id=project.id,
        details={
            "from": current.value,
            "to": target.value,
            "approval_id": approval_id,
            "reason": reason,
        },
    )
    return project
