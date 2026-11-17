from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from protopitch.api.app import create_app
from protopitch.context import AppContext, build_context
from protopitch.settings import Settings, find_root, load_settings

REPO_ROOT = find_root()
BACKEND_DIR = Path(__file__).resolve().parent.parent
FIXTURE_JOBS = "tests.fixture_jobs"


@pytest.fixture(autouse=True)
def no_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never touch the internet: any non-loopback connection fails the test."""
    real_connect = socket.socket.connect

    def guarded(self: socket.socket, address: object) -> None:
        if isinstance(address, tuple):
            host = str(address[0])
            try:
                loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
            except ValueError:
                loopback = False
            if not loopback:
                raise AssertionError(f"test attempted an outbound connection to {address}")
        real_connect(self, address)  # unix sockets (e.g. the Docker daemon) pass through

    monkeypatch.setattr(socket.socket, "connect", guarded)


def env_for_tests(data_dir: Path, **extra: str) -> dict[str, str]:
    env = {
        "PROTOPITCH_STORAGE__DATA_DIR": str(data_dir),
        "PROTOPITCH_JOBS__EXTRA_MODULES": f'["{FIXTURE_JOBS}"]',
        "PROTOPITCH_JOBS__LEASE_SECONDS": "2",
        "PROTOPITCH_JOBS__HEARTBEAT_SECONDS": "0.3",
        "PROTOPITCH_JOBS__POLL_INTERVAL_SECONDS": "0.1",
        "PROTOPITCH_SERVER__ALLOWED_HOSTS": '["testserver", "localhost", "127.0.0.1"]',
    }
    env.update(extra)
    return env


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def settings(data_dir: Path) -> Settings:
    return load_settings(REPO_ROOT, env_for_tests(data_dir))


@pytest.fixture
def ctx(settings: Settings) -> Iterator[AppContext]:
    context = build_context(settings)
    yield context
    context.close()


@pytest.fixture
def client(ctx: AppContext) -> Iterator[TestClient]:
    with TestClient(create_app(context=ctx)) as test_client:
        yield test_client


def drain(ctx: AppContext, limit: int = 50) -> int:
    """Run queued jobs in-process until the queue is empty."""
    worker = ctx.make_worker("test-worker")
    count = 0
    while count < limit and worker.run_once():
        count += 1
    return count


JD_TEXT = """Senior Data Scientist - Recommendations

We are looking for a Senior Data Scientist to build personalisation and ranking models.
Requirements: Python, machine learning, recommender systems, offline evaluation.
"""


def new_project(client: TestClient, company: str = "Acme BV", role: str = "Senior Data Scientist"):
    response = client.post(
        "/api/projects", json={"company": company, "role": role, "jd_text": JD_TEXT}
    )
    assert response.status_code == 201, response.text
    return response.json()
