"""HTTP API: projects, lifecycle actions, approval gates, job status and the event stream."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from protopitch.auth import Principal
from protopitch.context import AppContext
from protopitch.db.models import AuditEvent
from protopitch.db.session import session_scope
from protopitch.domain.hashing import payload_hash, text_hash
from protopitch.domain.lifecycle import ProjectStatus
from protopitch.errors import ForbiddenError
from protopitch.services import ApprovalGate, get_project, transition_project

from .conftest import JD_TEXT, drain, new_project
from .helpers import snapshot_files


def test_health_and_status(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    status = client.get("/api/system/status").json()
    assert status["model_providers_configured"] == []
    assert "project.bootstrap" in status["job_types"]
    assert set(status["sandbox"]) == {"available", "driver", "reason", "profiles"}


def test_create_project_stores_the_jd_and_bootstraps_a_workspace(
    client: TestClient, ctx: AppContext
) -> None:
    created = new_project(client)
    assert created["status"] == "CREATED"
    assert created["jd"]["text"] == JD_TEXT.strip()
    assert created["jd"]["content_hash"] == text_hash(JD_TEXT.strip())
    assert created["versions"][0]["number"] == 1
    assert created["jobs"][0]["type"] == "project.bootstrap"
    assert created["jobs"][0]["status"] == "queued"

    drain(ctx)
    detail = client.get(f"/api/projects/{created['id']}").json()
    job = detail["jobs"][0]
    assert job["status"] == "succeeded"
    assert [s["name"] for s in job["steps"]] == ["verify_jd", "init_workspace"]
    assert detail["status"] == "CREATED"  # later stages belong to later milestones
    snapshot = detail["versions"][0]["workspace_snapshot"]
    meta = json.loads(snapshot_files(ctx, snapshot)[".protopitch/project.json"])
    assert meta["project_id"] == created["id"]


def test_two_projects_for_the_same_company_are_independent(
    client: TestClient, ctx: AppContext
) -> None:
    first = new_project(client, company="Acme BV", role="Senior Data Scientist")
    second = new_project(client, company="Acme BV", role="Senior Data Scientist")
    drain(ctx)
    assert first["id"] != second["id"]
    listed = client.get("/api/projects").json()
    assert {p["id"] for p in listed} == {first["id"], second["id"]}

    one = ctx.workspaces.path_for(first["id"], 1)
    two = ctx.workspaces.path_for(second["id"], 1)
    assert one != two and one.is_dir() and two.is_dir()
    assert one.parent != two.parent  # separate project directories
    assert json.loads((one / ".protopitch/project.json").read_text())["project_id"] == first["id"]
    assert json.loads((two / ".protopitch/project.json").read_text())["project_id"] == second["id"]

    # Changing one project leaves the other untouched.
    client.patch(f"/api/projects/{first['id']}", json={"context": "only for the first"})
    client.post(f"/api/projects/{first['id']}/transitions", json={"action": "archive"})
    other = client.get(f"/api/projects/{second['id']}").json()
    assert other["context"] is None and other["status"] == "CREATED"
    assert other["jobs"][0]["project_id"] == second["id"]


@pytest.mark.parametrize(
    "body",
    [
        {"company": "", "role": "DS", "jd_text": "text"},
        {"company": "Acme", "role": "DS", "jd_text": "   "},
        {"company": "Acme", "role": "DS", "jd_text": "x", "jd_url": "javascript:alert(1)"},
        {"company": "Acme", "role": "DS", "jd_text": "x", "jd_url": "file:///etc/passwd"},
        {"company": "Acme", "role": "DS", "jd_text": "x", "unknown_field": 1},
        {"company": "Acme", "role": "DS"},
    ],
)
def test_invalid_projects_are_rejected_with_a_clear_error(client: TestClient, body: dict) -> None:
    response = client.post("/api/projects", json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["message"] and error["next_actions"]


def test_unknown_project_is_a_clear_404(client: TestClient) -> None:
    response = client.get("/api/projects/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_jd_text_is_immutable(client: TestClient) -> None:
    project = new_project(client)
    response = client.patch(f"/api/projects/{project['id']}", json={"jd_text": "rewritten"})
    assert response.status_code == 422
    assert client.get(f"/api/projects/{project['id']}").json()["jd"]["text"] == JD_TEXT.strip()


def test_archive_and_unarchive_restore_the_previous_state(client: TestClient) -> None:
    project = new_project(client)
    url = f"/api/projects/{project['id']}/transitions"
    archived = client.post(url, json={"action": "archive"}).json()
    assert archived["status"] == "ARCHIVED" and archived["owner_actions"] == ["unarchive"]
    assert client.get("/api/projects").json() == []
    assert len(client.get("/api/projects?include_archived=true").json()) == 1
    restored = client.post(url, json={"action": "unarchive"}).json()
    assert restored["status"] == "CREATED"


def test_illegal_transitions_are_rejected_with_a_clear_error(
    client: TestClient, ctx: AppContext
) -> None:
    project = new_project(client)
    url = f"/api/projects/{project['id']}/transitions"

    # Owner actions that do not apply in this state.
    for action in ("unarchive", "resume"):
        response = client.post(url, json={"action": action})
        assert response.status_code == 409, action
        assert response.json()["error"]["code"] == "illegal_transition"
    # The API offers no way to jump the pipeline.
    assert client.post(url, json={"action": "approve"}).status_code == 422
    assert client.post(url, json={"to": "READY_FOR_REVIEW"}).status_code == 422

    # Inside the platform, the transition table is enforced too.
    with session_scope(ctx.sessions) as session:
        record = get_project(session, project["id"])
        from protopitch.errors import IllegalTransitionError

        with pytest.raises(IllegalTransitionError) as info:
            transition_project(session, record, ProjectStatus.READY_FOR_REVIEW, actor="test")
        assert "CREATED" in info.value.message and "READY_FOR_REVIEW" in info.value.message
        assert "JD_ANALYZED" in info.value.message  # tells the reader what is allowed
    assert client.get(f"/api/projects/{project['id']}").json()["status"] == "CREATED"


def test_approval_gated_transition_needs_a_matching_unused_approval(
    client: TestClient, ctx: AppContext
) -> None:
    from protopitch.errors import ApprovalRequiredError

    project = new_project(client)
    proposal_hash = payload_hash({"proposal": "v1"})
    with session_scope(ctx.sessions) as session:
        record = get_project(session, project["id"])
        record.status = ProjectStatus.AWAITING_APPROVAL.value  # arrange: reach the checkpoint

    def approve(hash_to_use: str | None) -> None:
        with session_scope(ctx.sessions) as session:
            transition_project(
                session,
                get_project(session, project["id"]),
                ProjectStatus.APPROVED,
                actor="owner",
                approval_payload_hash=hash_to_use,
            )

    with pytest.raises(ApprovalRequiredError):
        approve(None)
    with pytest.raises(ApprovalRequiredError):
        approve(proposal_hash)  # nothing recorded yet

    # A rejection, an approval of something else, and an approval for another project do not count.
    other = new_project(client)
    with session_scope(ctx.sessions) as session:
        ApprovalGate.record(
            session,
            kind="architecture",
            payload_hash=proposal_hash,
            decision="rejected",
            actor="owner",
            project_id=project["id"],
        )
        ApprovalGate.record(
            session,
            kind="architecture",
            payload_hash=payload_hash({"proposal": "v2"}),
            decision="approved",
            actor="owner",
            project_id=project["id"],
        )
        ApprovalGate.record(
            session,
            kind="architecture",
            payload_hash=proposal_hash,
            decision="approved",
            actor="owner",
            project_id=other["id"],
        )
        ApprovalGate.record(
            session,
            kind="deployment",
            payload_hash=proposal_hash,
            decision="approved",
            actor="owner",
            project_id=project["id"],
        )
    with pytest.raises(ApprovalRequiredError):
        approve(proposal_hash)

    response = client.post("/api/approvals", json={
        "kind": "architecture", "payload_hash": proposal_hash, "decision": "approved",
        "project_id": project["id"],
    })  # fmt: skip
    assert response.status_code == 201
    approve(proposal_hash)
    assert client.get(f"/api/projects/{project['id']}").json()["status"] == "APPROVED"

    # An approval is used up: it cannot authorise the same step a second time.
    with session_scope(ctx.sessions) as session:
        get_project(session, project["id"]).status = ProjectStatus.AWAITING_APPROVAL.value
    with pytest.raises(ApprovalRequiredError):
        approve(proposal_hash)


def test_delete_is_refused_without_an_approval_bound_to_that_project(
    client: TestClient, ctx: AppContext
) -> None:
    keep = new_project(client)
    doomed = new_project(client)
    drain(ctx)

    refused = client.delete(f"/api/projects/{doomed['id']}")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "approval_required"

    # An approval for a different project does not authorise this deletion.
    other_plan = client.get(f"/api/projects/{keep['id']}/delete-plan").json()
    client.post("/api/approvals", json={
        "kind": other_plan["kind"], "payload_hash": other_plan["payload_hash"],
        "decision": "approved", "project_id": doomed["id"],
    })  # fmt: skip
    assert client.delete(f"/api/projects/{doomed['id']}").status_code == 403

    plan = client.get(f"/api/projects/{doomed['id']}/delete-plan").json()
    assert "cannot be undone" in " ".join(plan["consequences"]).lower()
    client.post("/api/approvals", json={
        "kind": plan["kind"], "payload_hash": plan["payload_hash"], "decision": "approved",
        "project_id": doomed["id"],
    })  # fmt: skip
    workspace = ctx.workspaces.path_for(doomed["id"], 1)
    assert workspace.is_dir()
    assert client.delete(f"/api/projects/{doomed['id']}").status_code == 204

    assert client.get(f"/api/projects/{doomed['id']}").status_code == 404
    assert not workspace.exists()
    # The other project is intact, and the audit trail still records what happened.
    assert client.get(f"/api/projects/{keep['id']}").json()["jobs"][0]["status"] == "succeeded"
    assert ctx.workspaces.path_for(keep["id"], 1).is_dir()
    with session_scope(ctx.sessions) as session:
        actions = session.scalars(
            select(AuditEvent.action).where(AuditEvent.subject_id == doomed["id"])
        ).all()
    assert "project.create" in actions and "project.delete" in actions


def test_failed_project_can_be_resumed_from_where_it_failed(
    client: TestClient, ctx: AppContext
) -> None:
    project = new_project(client)
    # Arrange a failure: the stored job description disappears before the worker runs.
    blob = next(ctx.settings.artifacts_dir.rglob(project["jd"]["content_hash"]))
    saved = blob.read_bytes()
    blob.unlink()
    drain(ctx)
    failed = client.get(f"/api/projects/{project['id']}").json()
    assert failed["status"] == "FAILED" and failed["failed_from"] == "CREATED"
    assert failed["failure"]["step"] == "verify_jd"
    assert failed["owner_actions"] == ["resume", "archive"]
    assert failed["jobs"][0]["steps"][0]["attempt"] == 3  # bounded retries, then failure

    blob.write_bytes(saved)  # the owner fixes the cause
    resumed = client.post(f"/api/projects/{project['id']}/transitions", json={"action": "resume"})
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "CREATED" and resumed.json()["failure"] is None
    drain(ctx)
    done = client.get(f"/api/projects/{project['id']}").json()
    assert len(done["jobs"]) == 1 and done["jobs"][0]["status"] == "succeeded"


def test_job_events_stream_as_server_sent_events(client: TestClient, ctx: AppContext) -> None:
    project = new_project(client)
    job_id = project["jobs"][0]["id"]
    drain(ctx)
    with client.stream("GET", f"/api/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    blocks = [b for b in body.split("\n\n") if b.strip()]
    logs = [json.loads(b.split("data: ", 1)[1]) for b in blocks if "event: log" in b]
    assert [e["id"] for e in logs] == sorted(e["id"] for e in logs)
    assert logs[0]["message"].startswith("Queued")
    assert any(e["step"] == "verify_jd" for e in logs)
    assert blocks[-1].startswith("event: end") and '"succeeded"' in blocks[-1]

    # A reconnecting client receives only what it missed.
    with client.stream(
        "GET", f"/api/jobs/{job_id}/events", headers={"Last-Event-ID": str(logs[-2]["id"])}
    ) as response:
        resumed = "".join(response.iter_text())
    assert resumed.count("event: log") == 1
    assert client.get("/api/jobs/unknown/events").status_code == 404


def test_every_api_route_goes_through_the_auth_hook(client: TestClient) -> None:
    """Swap in a provider that refuses everyone: every documented endpoint must refuse."""

    class DenyAll:
        def authenticate(self, request: object) -> Principal:
            raise ForbiddenError("not signed in")

    client.app.state.auth = DenyAll()  # type: ignore[attr-defined]
    paths = client.get("/api/openapi.json").json()["paths"]
    checked = 0
    for path, operations in paths.items():
        url = path.replace("{project_id}", "p").replace("{job_id}", "j")
        assert "{" not in url, f"unhandled path parameter in {path}"
        for method in operations:
            response = client.request(method.upper(), url, json={})
            assert response.status_code == 403, f"{method.upper()} {path} bypasses the auth hook"
            assert response.json()["error"]["code"] == "forbidden"
            checked += 1
    assert checked >= 14


def test_unknown_host_headers_are_refused(client: TestClient) -> None:
    """Protects the unauthenticated local API from DNS-rebinding attacks."""
    response = client.get("/api/projects", headers={"Host": "attacker.example"})
    assert response.status_code == 400


def test_cross_site_state_changes_are_refused(client: TestClient) -> None:
    body = {"company": "Acme", "role": "DS", "jd_text": "text"}
    evil = client.post("/api/projects", json=body, headers={"Origin": "https://attacker.example"})
    assert evil.status_code == 403
    assert client.get("/api/projects").json() == []
    same_origin = client.post("/api/projects", json=body, headers={"Origin": "http://testserver"})
    assert same_origin.status_code == 201


def test_responses_carry_security_headers_and_text_is_never_html(client: TestClient) -> None:
    payload = "<script>alert(1)</script>"
    created = client.post(
        "/api/projects", json={"company": payload, "role": "DS", "jd_text": payload}
    )
    assert created.headers["content-type"].startswith("application/json")
    assert created.headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in created.headers["content-security-policy"]
    assert created.json()["company"] == payload  # stored verbatim, rendered as text by the UI


def test_missing_frontend_build_is_explained(client: TestClient, ctx: AppContext) -> None:
    if ctx.settings.frontend_dist.joinpath("index.html").is_file():
        assert client.get("/").status_code == 200
    else:
        response = client.get("/")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "frontend_not_built"
    assert client.get("/api/nope").json()["error"]["code"] == "not_found"
