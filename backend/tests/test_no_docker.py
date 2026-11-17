"""The platform must start and work with Docker absent, with no API keys and no models."""

from __future__ import annotations

import json
import signal
import socket
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from protopitch.api.app import create_app
from protopitch.context import AppContext, build_context
from protopitch.settings import load_settings

from .conftest import REPO_ROOT, drain, env_for_tests, new_project
from .helpers import spawn, wait_for

NO_DOCKER = {"PROTOPITCH_SANDBOX__DOCKER_BINARY": "/nonexistent/bin/docker"}


@pytest.fixture
def ctx_without_docker(data_dir: Path) -> Iterator[AppContext]:
    context = build_context(load_settings(REPO_ROOT, env_for_tests(data_dir, **NO_DOCKER)))
    yield context
    context.close()


def test_probe_reports_generation_unavailable_and_nothing_else_is_affected(
    ctx_without_docker: AppContext,
) -> None:
    ctx = ctx_without_docker
    with TestClient(create_app(context=ctx)) as client:
        status = client.get("/api/system/status")
        assert status.status_code == 200
        body = status.json()
        assert body["generation_available"] is False
        assert body["sandbox"]["available"] is False
        assert "Docker was not found" in body["sandbox"]["reason"]

        # Everything that does not execute generated code still works.
        project = new_project(client)
        drain(ctx)
        detail = client.get(f"/api/projects/{project['id']}").json()
        assert detail["jobs"][0]["status"] == "succeeded"
        archive = client.post(
            f"/api/projects/{project['id']}/transitions", json={"action": "archive"}
        )
        assert archive.json()["status"] == "ARCHIVED"

        # Work that needs the sandbox fails honestly and says why.
        queued = client.post("/api/system/sandbox-selftest")
        assert queued.status_code == 202
        drain(ctx)
        job = client.get(f"/api/jobs/{queued.json()['id']}").json()
        assert job["status"] == "failed"
        assert job["error"]["code"] == "sandbox_unavailable"
        assert "Docker was not found" in job["error"]["message"]
        assert job["steps"][0]["attempt"] == 1  # not retried: retrying cannot help


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read())


def test_real_server_starts_with_no_docker_no_keys_and_runs_a_job(data_dir: Path) -> None:
    """Start the actual server process with a minimal environment and use it over HTTP."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = spawn(data_dir, "serve", "--with-worker", "--port", str(port), **NO_DOCKER)
    base = f"http://127.0.0.1:{port}"
    try:

        def up() -> bool:
            try:
                return _get(f"{base}/api/health") == {"status": "ok"}
            except (OSError, urllib.error.URLError):
                assert server.poll() is None, "the server exited during start-up"
                return False

        wait_for(up, timeout=40, what="the server to start")
        status = _get(f"{base}/api/system/status")
        assert status["generation_available"] is False
        assert status["model_providers_configured"] == []

        request = urllib.request.Request(
            f"{base}/api/projects",
            data=json.dumps({"company": "Acme", "role": "DS", "jd_text": "A job."}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            project = json.loads(response.read())

        def bootstrapped() -> bool:
            jobs = _get(f"{base}/api/projects/{project['id']}")["jobs"]
            return jobs[0]["status"] == "succeeded"

        wait_for(bootstrapped, timeout=30, what="the worker to finish the bootstrap job")
    finally:
        server.send_signal(signal.SIGTERM)
        server.wait(timeout=30)
    assert (data_dir / "protopitch.db").is_file()
