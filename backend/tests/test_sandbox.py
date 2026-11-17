"""Sandbox isolation ("escape") suite. Needs Docker and the built core image.

Run with ``make sandbox-test``. These tests fail, rather than skip, when the sandbox is
unavailable: an isolation suite that silently does not run proves nothing.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

import pytest

from protopitch.context import AppContext
from protopitch.jobs.backend import JobStatus
from protopitch.jobs.builtin import SANDBOX_SELFTEST
from protopitch.sandbox.docker import DockerSandboxDriver
from protopitch.sandbox.driver import SandboxResult, SandboxSpec
from protopitch.settings import SandboxLimits

from .conftest import drain

pytestmark = pytest.mark.docker

HOST_SECRET = "host-secret-value-9f3c1a77"
FAST = SandboxLimits(cpus=1, memory_mb=256, pids=128, timeout_seconds=60, tmpfs_mb=32)


@pytest.fixture
def driver(ctx: AppContext) -> DockerSandboxDriver:
    capability = ctx.sandbox.probe()
    assert capability.available, f"sandbox unavailable: {capability.reason}"
    return ctx.sandbox


@pytest.fixture
def workspaces(ctx: AppContext) -> tuple[Path, Path]:
    """Two projects' workspaces side by side, as the platform lays them out."""
    mine = ctx.workspaces.path_for("project-a", 1)
    other = ctx.workspaces.path_for("project-b", 1)
    for directory in (mine, other):
        directory.mkdir(parents=True)
    (other / "other-project.txt").write_text(HOST_SECRET)
    return mine, other


def run_py(
    driver: DockerSandboxDriver,
    code: str,
    workspace: Path | None = None,
    limits: SandboxLimits = FAST,
    **kwargs: object,
) -> SandboxResult:
    return driver.run(
        SandboxSpec(command=["python", "-c", code], workspace=workspace, limits=limits, **kwargs)  # type: ignore[arg-type]
    )


def test_host_environment_is_not_visible(
    driver: DockerSandboxDriver, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROTOPITCH_TEST_API_KEY", HOST_SECRET)
    monkeypatch.setenv("SOME_PROVIDER_TOKEN", HOST_SECRET)
    result = run_py(driver, "import os, json; print(json.dumps(dict(os.environ)))")
    assert result.ok, result.stderr
    env = json.loads(result.stdout)
    assert HOST_SECRET not in result.stdout
    assert "PROTOPITCH_TEST_API_KEY" not in env and "SOME_PROVIDER_TOKEN" not in env
    assert env["HOME"] == "/tmp"
    for proxy in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        assert env.get(proxy, "") == ""
    # PWD is set by the container's own shell to the container's working directory.
    assert env.get("PWD", "/tmp") in ("/tmp", "/workspace")
    allowed = {
        "HOME",
        "PATH",
        "PWD",
        "HOSTNAME",
        "LANG",
        "GPG_KEY",
        "PIP_DISABLE_PIP_VERSION_CHECK",
    }
    unexpected = {
        k for k in env
        if k not in allowed and not k.startswith("PYTHON") and not k.lower().endswith("_proxy")
    }  # fmt: skip
    assert unexpected == set(), f"unexpected variables in the sandbox: {unexpected}"


def test_explicit_variables_are_the_only_way_in(driver: DockerSandboxDriver) -> None:
    result = run_py(driver, "import os; print(os.environ['SEED'])", env={"SEED": "42"})
    assert result.stdout.strip() == "42"


def test_a_planted_secret_file_on_the_host_cannot_be_read(
    driver: DockerSandboxDriver, ctx: AppContext, workspaces: tuple[Path, Path], tmp_path: Path
) -> None:
    mine, _ = workspaces
    in_data_dir = ctx.settings.data_dir / "platform-secret.txt"
    elsewhere = tmp_path / "platform-secret.txt"
    for path in (in_data_dir, elsewhere):
        path.write_text(HOST_SECRET)
    code = f"""
import os
found = []
for path in ({str(in_data_dir)!r}, {str(elsewhere)!r}):
    try:
        found.append(open(path).read())
    except OSError:
        pass
for root, dirs, files in os.walk('/'):
    dirs[:] = [d for d in dirs if os.path.join(root, d) not in ('/proc', '/sys', '/dev')]
    if 'platform-secret.txt' in files:
        found.append(os.path.join(root, 'platform-secret.txt'))
print('FOUND', found)
"""
    result = run_py(driver, code, workspace=mine)
    assert result.ok, result.stderr
    assert result.stdout.strip() == "FOUND []"
    assert HOST_SECRET not in result.stdout + result.stderr


def test_another_projects_workspace_cannot_be_reached(
    driver: DockerSandboxDriver, workspaces: tuple[Path, Path]
) -> None:
    mine, other = workspaces
    # A link planted in my workspace that points at the other project on the host.
    (mine / "link-to-other").symlink_to(other)
    (mine / "link-to-file").symlink_to(other / "other-project.txt")
    code = f"""
import os
attempts = [
    {str(other / "other-project.txt")!r},
    '/workspace/../project-b/v1/other-project.txt',
    '/workspace/../../project-b/v1/other-project.txt',
    '/workspace/link-to-other/other-project.txt',
    '/workspace/link-to-file',
]
leaked = []
for path in attempts:
    try:
        leaked.append(open(path).read())
    except OSError:
        pass
print('LEAKED', leaked)
print('PARENT', sorted(os.listdir('/workspace/..')))
"""
    result = run_py(driver, code, workspace=mine)
    assert result.ok, result.stderr
    assert "LEAKED []" in result.stdout
    assert HOST_SECRET not in result.stdout
    assert "project-b" not in result.stdout
    assert (other / "other-project.txt").read_text() == HOST_SECRET  # and it was not modified


def test_there_is_no_network(driver: DockerSandboxDriver) -> None:
    code = """
import os, socket
results = {}
for name, target in (('ip', ('1.1.1.1', 53)), ('dns', ('example.com', 443))):
    try:
        socket.create_connection(target, timeout=4).close()
        results[name] = 'CONNECTED'
    except OSError as exc:
        results[name] = type(exc).__name__
results['interfaces'] = sorted(os.listdir('/sys/class/net'))
print(results)
"""
    result = run_py(driver, code)
    assert result.ok, result.stderr
    assert "CONNECTED" not in result.stdout
    assert "'interfaces': ['lo']" in result.stdout


def test_time_limit_kills_the_run_and_leaves_no_container(driver: DockerSandboxDriver) -> None:
    limits = FAST.model_copy(update={"timeout_seconds": 2})
    result = run_py(driver, "import time; time.sleep(120)", limits=limits)
    assert result.timed_out and not result.ok
    assert result.duration_seconds < 20
    listed = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "label=protopitch.sandbox=run"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert listed.stdout.strip() == ""


def test_memory_limit_kills_the_run(driver: DockerSandboxDriver) -> None:
    limits = FAST.model_copy(update={"memory_mb": 64})
    result = run_py(
        driver, "x = bytearray(600 * 1024 * 1024); print('SURVIVED', len(x))", limits=limits
    )
    assert not result.ok
    assert "SURVIVED" not in result.stdout
    assert result.oom_killed or result.exit_code == 137


def test_process_limit_is_enforced(driver: DockerSandboxDriver) -> None:
    limits = FAST.model_copy(update={"pids": 24})
    code = """
import subprocess, sys
children, failed = [], False
try:
    for _ in range(200):
        children.append(subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)']))
except OSError:
    failed = True
print('STARTED', len(children), 'REFUSED', failed)
for child in children:
    child.kill()
"""
    result = run_py(driver, code, limits=limits)
    started = int(result.stdout.split("STARTED")[1].split()[0])
    assert "REFUSED True" in result.stdout
    assert started < 24


def test_unprivileged_user_read_only_root_and_no_capabilities(
    driver: DockerSandboxDriver, workspaces: tuple[Path, Path]
) -> None:
    mine, _ = workspaces
    code = """
import os
status = open('/proc/self/status').read()
def writable(path):
    try:
        open(path, 'w').close(); return True
    except OSError:
        return False
print({
    'uid': os.getuid(), 'gid': os.getgid(),
    'etc': writable('/etc/x'), 'usr': writable('/usr/local/lib/x'), 'root': writable('/x'),
    'workspace': writable('/workspace/out.txt'), 'tmp': writable('/tmp/x'),
    'cap_eff': [l.split()[1] for l in status.splitlines() if l.startswith('CapEff')][0],
    'no_new_privs': [l.split()[1] for l in status.splitlines() if l.startswith('NoNewPrivs')][0],
    'docker_sock': os.path.exists('/var/run/docker.sock') or os.path.exists('/run/docker.sock'),
})
"""
    result = run_py(driver, code, workspace=mine)
    assert result.ok, result.stderr
    report = eval(result.stdout)  # noqa: S307 - output of our own script
    assert report == {
        "uid": 10001, "gid": 10001, "etc": False, "usr": False, "root": False,
        "workspace": True, "tmp": True, "cap_eff": "0000000000000000", "no_new_privs": "1",
        "docker_sock": False,
    }  # fmt: skip


def test_read_only_mounts_cannot_be_modified(
    driver: DockerSandboxDriver, workspaces: tuple[Path, Path], tmp_path: Path
) -> None:
    mine, _ = workspaces
    platform_input = tmp_path / "evaluator"
    platform_input.mkdir()
    (platform_input / "expected.json").write_text('{"answer": 1}')
    code = """
print(open('/opt/input/expected.json').read())
try:
    open('/opt/input/expected.json', 'w').write('tampered'); print('MODIFIED')
except OSError:
    print('READ-ONLY')
"""
    result = run_py(driver, code, workspace=mine, readonly_mounts={platform_input: "/opt/input"})
    assert "READ-ONLY" in result.stdout and "MODIFIED" not in result.stdout
    assert (platform_input / "expected.json").read_text() == '{"answer": 1}'


def test_output_is_capped(driver: DockerSandboxDriver) -> None:
    limits = FAST.model_copy(update={"output_limit_bytes": 4096})
    result = run_py(driver, "print('x' * 5_000_000)", limits=limits)
    assert result.output_truncated
    assert len(result.stdout) <= 4096


def test_files_written_by_the_sandbox_can_be_saved_and_removed(
    driver: DockerSandboxDriver, ctx: AppContext, workspaces: tuple[Path, Path]
) -> None:
    mine, _ = workspaces
    result = run_py(
        driver,
        "import os; os.makedirs('/workspace/out/deep'); open('/workspace/out/deep/r.txt','w').write('r')",
        workspace=mine,
    )
    assert result.ok, result.stderr
    snapshot = ctx.workspaces.save(mine)
    ctx.workspaces.materialise(mine, None)  # wipes the directory, including sandbox-owned files
    ctx.workspaces.materialise(mine, snapshot)
    assert (mine / "out" / "deep" / "r.txt").read_text() == "r"


def test_image_digest_and_lock_hash_are_reported(
    driver: DockerSandboxDriver, ctx: AppContext
) -> None:
    result = run_py(driver, "print('ok')")
    lock = ctx.settings.sandbox_images_dir / "core" / "requirements.lock"
    assert result.lock_hash == hashlib.sha256(lock.read_bytes()).hexdigest()
    assert result.image == f"protopitch-sbx-core:{result.lock_hash[:12]}"
    assert result.image_digest.startswith("sha256:") and len(result.image_digest) == 71


def test_selftest_job_records_digest_and_lock_hash_on_the_run(ctx: AppContext) -> None:
    job_id = ctx.jobs.enqueue(SANDBOX_SELFTEST)
    drain(ctx)
    job = ctx.jobs.get_job(job_id)
    assert job.status == JobStatus.SUCCEEDED, job.error
    recorded = job.steps[1].output
    assert recorded is not None
    assert recorded["sandbox"]["image_digest"].startswith("sha256:")
    assert len(recorded["sandbox"]["lock_hash"]) == 64
    assert recorded["report"]["uid"] == 10001
    assert recorded["report"]["network"].startswith("blocked")
    assert recorded["report"]["root_fs"] == "read-only"
    # Platform variables never reach the sandbox either.
    assert not [n for n in recorded["report"]["env_names"] if n.startswith("PROTOPITCH")]


def test_core_profile_contains_the_pinned_stack(driver: DockerSandboxDriver) -> None:
    code = "import numpy, pandas, scipy, sklearn, fastapi, pytest, rank_bm25, faiss, langgraph; print('IMPORTS OK')"
    result = run_py(driver, code, limits=FAST.model_copy(update={"memory_mb": 1024}))
    assert "IMPORTS OK" in result.stdout, result.stderr


def test_serve_is_reachable_on_loopback_only_and_has_no_egress(
    driver: DockerSandboxDriver, workspaces: tuple[Path, Path]
) -> None:
    mine, _ = workspaces
    (mine / "index.html").write_text("<h1>preview works</h1>")
    handle = driver.serve(
        SandboxSpec(
            command=[
                "python",
                "-m",
                "http.server",
                "8000",
                "--bind",
                "0.0.0.0",
                "--directory",
                "/workspace",
            ],
            workspace=mine,
            limits=FAST,
        ),
        container_port=8000,
    )
    try:
        assert handle.wait_ready(timeout=40), handle.logs()
        with urllib.request.urlopen(handle.url + "/index.html", timeout=5) as response:
            assert b"preview works" in response.read()
        published = subprocess.run(
            ["docker", "ps", "--filter", "label=protopitch.sandbox=forwarder", "--format", "{{.Ports}}"],
            capture_output=True, text=True, check=True,
        ).stdout  # fmt: skip
        assert f"127.0.0.1:{handle.host_port}->" in published and "0.0.0.0" not in published
        egress = subprocess.run(
            ["docker", "exec", handle.app_container, "python", "-c",
             "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 53), timeout=4); print('CONNECTED')\n"
             "except OSError as e:\n    print('BLOCKED', type(e).__name__)"],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        assert "BLOCKED" in egress.stdout and "CONNECTED" not in egress.stdout
    finally:
        handle.stop()
    leftovers = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "label=protopitch.sandbox"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    networks = subprocess.run(
        ["docker", "network", "ls", "-q", "--filter", "label=protopitch.sandbox=serve"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    assert leftovers.strip() == "" and networks.strip() == ""
