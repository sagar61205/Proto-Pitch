from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import time
from collections.abc import Callable
from pathlib import Path

from protopitch.context import AppContext
from protopitch.db.models import JDDocument, Project, ProjectVersion
from protopitch.db.session import session_scope
from protopitch.domain.hashing import text_hash
from protopitch.jobs.backend import JobView

from .conftest import BACKEND_DIR, env_for_tests


def make_project(ctx: AppContext, company: str = "Acme BV") -> str:
    with session_scope(ctx.sessions) as session:
        project = Project(company=company, role="Data Scientist", status="CREATED")
        project.jd_documents = [JDDocument(raw_text="jd", content_hash=text_hash("jd"))]
        project.versions = [ProjectVersion(number=1)]
        session.add(project)
        session.flush()
        return project.id


def wait_for(predicate: Callable[[], bool], timeout: float = 30.0, what: str = "condition") -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


def wait_job(ctx: AppContext, job_id: str, status: str, timeout: float = 30.0) -> JobView:
    wait_for(lambda: ctx.jobs.get_job(job_id).status == status, timeout, f"job to be {status}")
    return ctx.jobs.get_job(job_id)


def snapshot_files(ctx: AppContext, snapshot: str) -> dict[str, str]:
    with tarfile.open(fileobj=io.BytesIO(ctx.artifacts.get_bytes(snapshot))) as tar:
        out = {}
        for member in tar.getmembers():
            if member.isfile():
                handle = tar.extractfile(member)
                assert handle is not None
                out[member.name] = handle.read().decode()
        return out


def lines(path: Path) -> list[str]:
    return path.read_text().splitlines() if path.exists() else []


def clean_env(data_dir: Path, **extra: str) -> dict[str, str]:
    """A minimal environment: no API keys, tokens or proxy settings from the host."""
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")}
    env.update(env_for_tests(data_dir, **extra))
    env["PYTHONPATH"] = str(BACKEND_DIR)
    return env


def spawn(data_dir: Path, *args: str, **extra_env: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-m", "protopitch.cli", *args],
        cwd=BACKEND_DIR,
        env=clean_env(data_dir, **extra_env),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
