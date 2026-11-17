"""Job engine: ordering, bounded retries, leases, recovery, workspace re-materialisation."""

from __future__ import annotations

import shutil
import signal
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import select

from protopitch.context import AppContext
from protopitch.db.models import Project, ProjectVersion
from protopitch.db.session import session_scope
from protopitch.errors import LeaseLostError
from protopitch.jobs.backend import JobStatus, StepStatus
from protopitch.settings import load_settings

from .conftest import REPO_ROOT, drain, env_for_tests
from .helpers import lines, make_project, snapshot_files, spawn, wait_for, wait_job


def _three_steps(
    ctx: AppContext, tmp_path: Path, *, gate_open: bool
) -> tuple[str, str, Path, Path]:
    project_id = make_project(ctx)
    markers = tmp_path / "markers"
    markers.mkdir()
    gate = tmp_path / "gate"
    if gate_open:
        gate.touch()
    job_id = ctx.jobs.enqueue(
        "test.three_steps",
        project_id=project_id,
        version=1,
        payload={"marker_dir": str(markers), "gate": str(gate)},
    )
    return project_id, job_id, markers, gate


def _version_snapshot(ctx: AppContext, project_id: str) -> str | None:
    with session_scope(ctx.sessions) as session:
        return session.scalars(
            select(ProjectVersion.workspace_snapshot).where(ProjectVersion.project_id == project_id)
        ).one()


def test_steps_run_in_order_and_the_result_is_saved(ctx: AppContext, tmp_path: Path) -> None:
    project_id, job_id, markers, _ = _three_steps(ctx, tmp_path, gate_open=True)
    assert drain(ctx) == 1
    job = ctx.jobs.get_job(job_id)
    assert job.status == JobStatus.SUCCEEDED
    assert [s.status for s in job.steps] == [StepStatus.SUCCEEDED] * 3
    assert [s.attempt for s in job.steps] == [1, 1, 1]
    assert job.steps[1].output == {"saw_step_one": "1"}
    snapshot = _version_snapshot(ctx, project_id)
    assert snapshot == job.workspace_snapshot
    assert snapshot_files(ctx, snapshot) == {"trace.txt": "1\n2\n3\n"}
    messages = [e.message for e in ctx.jobs.events_after(job_id, 0)]
    assert messages[0].startswith("Queued") and messages[-1] == "Job completed."
    assert "step one wrote its line" in messages


def test_transient_failures_are_retried_and_secrets_never_reach_the_log(
    ctx: AppContext, tmp_path: Path
) -> None:
    job_id = ctx.jobs.enqueue("test.flaky", payload={"marker_dir": str(tmp_path), "succeed_on": 3})
    drain(ctx)
    job = ctx.jobs.get_job(job_id)
    assert job.status == JobStatus.SUCCEEDED
    assert job.steps[0].attempt == 3
    assert len(lines(tmp_path / "flaky.runs")) == 3
    log = " ".join(e.message for e in ctx.jobs.events_after(job_id, 0))
    assert "Retrying" in log
    assert "hunter2hunter2" not in log


def test_retries_are_bounded(ctx: AppContext, tmp_path: Path) -> None:
    job_id = ctx.jobs.enqueue("test.flaky", payload={"marker_dir": str(tmp_path), "succeed_on": 99})
    drain(ctx)
    job = ctx.jobs.get_job(job_id)
    assert job.status == JobStatus.FAILED
    assert len(lines(tmp_path / "flaky.runs")) == ctx.settings.jobs.max_step_attempts == 3
    assert job.error is not None and job.error["step"] == "flaky"
    assert "hunter2hunter2" not in str(job.error)
    assert drain(ctx) == 0  # a failed job is not picked up again


def test_permanent_errors_are_not_retried(ctx: AppContext, tmp_path: Path) -> None:
    job_id = ctx.jobs.enqueue("test.permanent", payload={"marker_dir": str(tmp_path)})
    drain(ctx)
    job = ctx.jobs.get_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error is not None and job.error["code"] == "unsupported"
    assert len(lines(tmp_path / "permanent.runs")) == 1


def test_a_failed_job_fails_its_project_and_records_where(ctx: AppContext, tmp_path: Path) -> None:
    project_id = make_project(ctx)
    job_id = ctx.jobs.enqueue(
        "test.always_fails", project_id=project_id, version=1, payload={"marker_dir": str(tmp_path)}
    )
    drain(ctx)
    with session_scope(ctx.sessions) as session:
        project = session.get(Project, project_id)
        assert project is not None
        assert project.status == "FAILED"
        assert project.failed_from == "CREATED"
        assert project.failure is not None
        assert project.failure["job_id"] == job_id
        assert project.failure["step"] == "always"


def test_a_job_can_only_be_leased_by_one_worker(ctx: AppContext) -> None:
    job_ids = {ctx.jobs.enqueue("test.permanent") for _ in range(12)}
    taken: list[str] = []
    lock = threading.Lock()

    def take(name: str) -> None:
        while True:
            job = ctx.jobs.lease_next(name, 60)
            if job is None:
                return
            with lock:
                taken.append(job.id)

    threads = [threading.Thread(target=take, args=(f"w{i}",)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(taken) == sorted(job_ids)  # every job exactly once
    assert ctx.jobs.lease_next("late", 60) is None


def test_a_worker_that_lost_its_lease_cannot_write_results(ctx: AppContext) -> None:
    job_id = ctx.jobs.enqueue("test.permanent")
    first = ctx.jobs.lease_next("worker-a", 0.05)
    assert first is not None
    ctx.jobs.start_step(job_id, "worker-a", 0)
    time.sleep(0.2)  # lease expires
    second = ctx.jobs.lease_next("worker-b", 60)
    assert second is not None and second.id == job_id and second.leases == 2
    assert ctx.jobs.heartbeat(job_id, "worker-a", 60) is False
    with pytest.raises(LeaseLostError):
        ctx.jobs.complete_step(job_id, "worker-a", 0, {"stale": True}, None)
    with pytest.raises(LeaseLostError):
        ctx.jobs.fail_job(job_id, "worker-a", {"message": "stale"})
    assert ctx.jobs.get_job(job_id).steps[0].output is None


def test_workspace_is_recovered_from_the_store_when_its_directory_disappears(
    ctx: AppContext, tmp_path: Path
) -> None:
    """Delete every local workspace file after each step: the job must still be correct."""
    project_id, job_id, _, _ = _three_steps(ctx, tmp_path, gate_open=True)
    real_save = ctx.workspaces.save
    deletions = 0

    def save_then_lose_everything(directory: Path) -> str:
        nonlocal deletions
        snapshot = real_save(directory)
        shutil.rmtree(ctx.settings.workspaces_dir)
        ctx.settings.workspaces_dir.mkdir()
        deletions += 1
        return snapshot

    ctx.workspaces.save = save_then_lose_everything  # type: ignore[method-assign]
    drain(ctx)
    job = ctx.jobs.get_job(job_id)
    assert job.status == JobStatus.SUCCEEDED
    assert deletions == 3
    assert snapshot_files(ctx, _version_snapshot(ctx, project_id)) == {"trace.txt": "1\n2\n3\n"}


def test_a_stale_local_directory_is_not_trusted(ctx: AppContext, tmp_path: Path) -> None:
    """Local changes made outside a completed step never leak into the next step."""
    project_id, job_id, _, _ = _three_steps(ctx, tmp_path, gate_open=True)
    real_save = ctx.workspaces.save

    def save_then_tamper(directory: Path) -> str:
        snapshot = real_save(directory)
        ctx.workspaces.begin_changes(directory)  # what an interrupted step leaves behind
        (directory / "trace.txt").write_text("tampered\n")
        return snapshot

    ctx.workspaces.save = save_then_tamper  # type: ignore[method-assign]
    drain(ctx)
    assert ctx.jobs.get_job(job_id).status == JobStatus.SUCCEEDED
    assert snapshot_files(ctx, _version_snapshot(ctx, project_id)) == {"trace.txt": "1\n2\n3\n"}


def test_killing_the_worker_mid_job_resumes_from_the_last_completed_step(
    ctx: AppContext, data_dir: Path, tmp_path: Path
) -> None:
    project_id, job_id, markers, gate = _three_steps(ctx, tmp_path, gate_open=False)

    first = spawn(data_dir, "worker")
    try:
        wait_for(lambda: len(lines(markers / "two.runs")) == 1, what="step two to start")
        job = ctx.jobs.get_job(job_id)
        assert job.steps[0].status == StepStatus.SUCCEEDED
        assert job.steps[1].status == StepStatus.RUNNING
        first.send_signal(signal.SIGKILL)  # no chance to clean up
        first.wait(timeout=10)
    finally:
        if first.poll() is None:
            first.kill()

    assert ctx.jobs.get_job(job_id).status == JobStatus.RUNNING  # still held by the dead worker
    shutil.rmtree(ctx.settings.workspaces_dir)  # and its local files are gone as well

    second = spawn(data_dir, "worker")
    try:
        wait_for(lambda: len(lines(markers / "two.runs")) == 2, what="step two to restart")
        gate.touch()
        job = wait_job(ctx, job_id, JobStatus.SUCCEEDED)
    finally:
        second.send_signal(signal.SIGTERM)
        assert second.wait(timeout=20) == 0  # graceful shutdown

    assert len(lines(markers / "one.runs")) == 1, "the completed step must not run again"
    assert len(lines(markers / "three.runs")) == 1
    assert [s.attempt for s in job.steps] == [1, 2, 1]
    assert job.leases == 2
    files = snapshot_files(ctx, _version_snapshot(ctx, project_id))
    assert files == {"trace.txt": "1\n2\n3\n"}, "no half-finished work from the killed step"
    assert any("Recovered" in e.message for e in ctx.jobs.events_after(job_id, 0))


def test_a_stopping_worker_gives_the_job_back(ctx: AppContext, tmp_path: Path) -> None:
    _, job_id, markers, _ = _three_steps(ctx, tmp_path, gate_open=True)
    worker = ctx.make_worker("stopping")
    worker.request_stop()
    assert worker.run_once() is True
    job = ctx.jobs.get_job(job_id)
    assert job.status == JobStatus.QUEUED
    assert not (markers / "one.runs").exists()
    drain(ctx)
    assert ctx.jobs.get_job(job_id).status == JobStatus.SUCCEEDED


def test_jobs_have_a_deadline(data_dir: Path, tmp_path: Path) -> None:
    from protopitch.context import build_context

    settings = load_settings(
        REPO_ROOT, env_for_tests(data_dir, PROTOPITCH_JOBS__JOB_DEADLINE_SECONDS="0.01")
    )
    ctx = build_context(settings)
    try:
        job_id = ctx.jobs.enqueue("test.flaky", payload={"marker_dir": str(tmp_path)})
        time.sleep(0.05)
        drain(ctx)
        job = ctx.jobs.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error is not None and job.error["code"] == "deadline_exceeded"
        assert not (tmp_path / "flaky.runs").exists()
    finally:
        ctx.close()


def test_unknown_job_types_cannot_be_queued(ctx: AppContext) -> None:
    with pytest.raises(KeyError):
        ctx.jobs.enqueue("no.such.job")
