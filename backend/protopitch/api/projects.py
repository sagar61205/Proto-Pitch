from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from protopitch.api.deps import Actor, Ctx, Db
from protopitch.api.schemas import (
    ERROR_RESPONSES,
    ActionPlan,
    ApprovalCreate,
    ApprovalOut,
    JDOut,
    JobOut,
    OwnerAction,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    ProjectUpdate,
    TransitionRequest,
    VersionOut,
)
from protopitch.context import AppContext
from protopitch.db.models import Approval, JDDocument, Job, Project, ProjectVersion
from protopitch.db.session import scrub_deleted
from protopitch.domain.hashing import payload_hash, text_hash
from protopitch.domain.lifecycle import ProjectStatus
from protopitch.errors import ConflictError, IllegalTransitionError
from protopitch.jobs.backend import JobStatus
from protopitch.jobs.builtin import PROJECT_BOOTSTRAP
from protopitch.services import (
    ApprovalGate,
    audit,
    blobs_still_referenced,
    get_project,
    project_blob_hashes,
    transition_project,
)

router = APIRouter(tags=["projects"], responses=ERROR_RESPONSES)

DELETE_KIND = "project_delete"


def _owner_actions(project: Project) -> list[OwnerAction]:
    status = ProjectStatus(project.status)
    if status is ProjectStatus.ARCHIVED:
        return ["unarchive"]
    actions: list[OwnerAction] = ["archive"]
    if status is ProjectStatus.FAILED:
        actions.insert(0, "resume")
    return actions


def _project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        company=project.company,
        role=project.role,
        jd_url=project.jd_url,
        context=project.context,
        status=ProjectStatus(project.status),
        failed_from=ProjectStatus(project.failed_from) if project.failed_from else None,
        failure=project.failure,
        active_version=project.active_version,
        owner_actions=_owner_actions(project),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _detail(ctx: AppContext, project: Project) -> ProjectDetail:
    jd = project.jd_documents[0]
    return ProjectDetail(
        **_project_out(project).model_dump(),
        jd=JDOut(
            text=jd.raw_text, url=jd.url, content_hash=jd.content_hash, created_at=jd.created_at
        ),
        versions=[
            VersionOut(
                number=v.number,
                parent_number=v.parent_number,
                reason=v.reason,
                workspace_snapshot=v.workspace_snapshot,
                created_at=v.created_at,
            )
            for v in project.versions
        ],
        jobs=[JobOut.model_validate(asdict(j)) for j in ctx.jobs.list_jobs(project.id)],
    )


def _delete_payload(project_id: str) -> dict[str, str]:
    return {"action": DELETE_KIND, "project_id": project_id}


@router.post("/projects", response_model=ProjectDetail, status_code=201)
def create_project(body: ProjectCreate, ctx: Ctx, db: Db, actor: Actor) -> ProjectDetail:
    """Create an independent project from a job description and start its bootstrap job."""
    jd_hash = text_hash(body.jd_text)
    stored = ctx.artifacts.put_bytes(body.jd_text.encode("utf-8"))
    assert stored.sha256 == jd_hash
    project = Project(
        company=body.company,
        role=body.role,
        jd_url=body.jd_url,
        context=body.context,
        status=ProjectStatus.CREATED.value,
        active_version=1,
    )
    project.jd_documents = [
        JDDocument(raw_text=body.jd_text, url=body.jd_url, content_hash=jd_hash)
    ]
    project.versions = [ProjectVersion(number=1, reason="Initial version")]
    db.add(project)
    db.flush()
    audit(
        db,
        actor=actor.id,
        action="project.create",
        subject_type="project",
        subject_id=project.id,
        details={"company": project.company, "role": project.role, "jd_sha256": jd_hash},
    )
    ctx.jobs.enqueue_in(
        db, PROJECT_BOOTSTRAP, project_id=project.id, version=1, payload={"jd_sha256": jd_hash}
    )
    db.commit()
    return _detail(ctx, project)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Db, include_archived: bool = False) -> list[ProjectOut]:
    query = select(Project).order_by(Project.created_at.desc())
    if not include_archived:
        query = query.where(Project.status != ProjectStatus.ARCHIVED.value)
    return [_project_out(p) for p in db.scalars(query)]


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def read_project(project_id: str, ctx: Ctx, db: Db) -> ProjectDetail:
    return _detail(ctx, get_project(db, project_id))


@router.patch("/projects/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: str, body: ProjectUpdate, ctx: Ctx, db: Db, actor: Actor
) -> ProjectDetail:
    project = get_project(db, project_id)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if key in ("company", "role") and (value is None or not str(value).strip()):
            continue
        setattr(project, key, value.strip() if isinstance(value, str) else value)
    if changes:
        audit(
            db,
            actor=actor.id,
            action="project.update",
            subject_type="project",
            subject_id=project.id,
            details={"fields": sorted(changes)},
        )
    db.commit()
    return _detail(ctx, project)


def _resume(ctx: AppContext, db: Session, project: Project, actor_id: str) -> None:
    if project.status != ProjectStatus.FAILED.value or not project.failed_from:
        raise IllegalTransitionError(
            "Only a failed project can be resumed.",
            next_actions=["Open the project to see its current status."],
        )
    failed_job_id = (project.failure or {}).get("job_id")
    transition_project(db, project, ProjectStatus(project.failed_from), actor=actor_id)
    if failed_job_id:
        ctx.jobs.retry_failed(db, str(failed_job_id))


@router.post("/projects/{project_id}/transitions", response_model=ProjectDetail)
def owner_transition(
    project_id: str, body: TransitionRequest, ctx: Ctx, db: Db, actor: Actor
) -> ProjectDetail:
    """Owner-initiated lifecycle actions. Pipeline transitions are made by jobs, not here."""
    project = get_project(db, project_id)
    if body.action == "archive":
        transition_project(db, project, ProjectStatus.ARCHIVED, actor=actor.id)
    elif body.action == "unarchive":
        if not project.previous_status:
            raise IllegalTransitionError("This project is not archived.")
        transition_project(db, project, ProjectStatus(project.previous_status), actor=actor.id)
    else:
        _resume(ctx, db, project, actor.id)
    db.commit()
    return _detail(ctx, project)


@router.get("/projects/{project_id}/delete-plan", response_model=ActionPlan)
def delete_plan(project_id: str, db: Db) -> ActionPlan:
    project = get_project(db, project_id)
    return ActionPlan(
        kind=DELETE_KIND,
        payload_hash=payload_hash(_delete_payload(project.id)),
        summary=f"Permanently delete the project '{project.role}' at '{project.company}'.",
        consequences=[
            "The job description, versions, jobs and workspace of this project are removed.",
            "Other projects are not affected.",
            "The audit history keeps a record that the project existed and was deleted.",
            "This cannot be undone.",
        ],
    )


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, ctx: Ctx, db: Db, actor: Actor) -> Response:
    """Destructive: refused unless an approval bound to this exact deletion exists."""
    project = get_project(db, project_id)
    running = db.scalars(
        select(Job.id).where(Job.project_id == project.id, Job.status == JobStatus.RUNNING)
    ).first()
    if running:
        raise ConflictError(
            "A job is still running for this project.",
            next_actions=["Wait for the job to finish, then delete the project."],
        )
    approval = ApprovalGate.consume(
        db,
        kind=DELETE_KIND,
        payload_hash=payload_hash(_delete_payload(project.id)),
        project_id=project.id,
    )
    audit(
        db,
        actor=actor.id,
        action="project.delete",
        subject_type="project",
        subject_id=project.id,
        details={"company": project.company, "role": project.role, "approval_id": approval.id},
    )
    blobs = project_blob_hashes(db, project.id)
    db.delete(project)
    db.flush()
    # Jobs and artifacts are removed by the database's cascade; expire the session's view.
    db.expire_all()
    orphaned = blobs - blobs_still_referenced(db, blobs)
    db.commit()
    for sha256 in orphaned:
        ctx.artifacts.delete(sha256)
    scrub_deleted(ctx.engine)
    ctx.workspaces.remove_project(project_id)
    return Response(status_code=204)


@router.post("/approvals", response_model=ApprovalOut, status_code=201)
def record_approval(body: ApprovalCreate, db: Db, actor: Actor) -> ApprovalOut:
    if body.project_id is not None:
        get_project(db, body.project_id)
    approval = ApprovalGate.record(
        db,
        kind=body.kind,
        payload_hash=body.payload_hash,
        decision=body.decision,
        actor=actor.id,
        project_id=body.project_id,
        comment=body.comment,
    )
    db.commit()
    return ApprovalOut.model_validate(approval, from_attributes=True)


@router.get("/projects/{project_id}/approvals", response_model=list[ApprovalOut])
def list_approvals(project_id: str, db: Db) -> list[ApprovalOut]:
    get_project(db, project_id)
    rows = db.scalars(
        select(Approval)
        .where(Approval.project_id == project_id)
        .order_by(Approval.created_at.desc())
    )
    return [ApprovalOut.model_validate(r, from_attributes=True) for r in rows]
