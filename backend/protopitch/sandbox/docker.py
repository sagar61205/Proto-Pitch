"""Docker sandbox driver (ARCHITECTURE §7.10).

Every container: non-root user, read-only root filesystem, no network, all capabilities
dropped, no new privileges, CPU / memory / process limits, an empty environment and only
the given workspace mounted. A wall-clock limit is enforced twice: by this process and by
``timeout`` inside the container, so a container cannot outlive a crashed worker.
"""

from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from protopitch.errors import SandboxUnavailableError
from protopitch.logging_setup import get_logger
from protopitch.sandbox.driver import (
    ProfileStatus,
    SandboxCapability,
    SandboxResult,
    SandboxSpec,
)
from protopitch.settings import SandboxLimits, Settings
from protopitch.storage.workspace import make_tree_writable_for_sandbox

log = get_logger("sandbox.docker")

LABEL = "protopitch.sandbox"
_PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")

# Platform-owned TCP forwarder used only by ``serve``. It is the single path between the
# host's loopback interface and a previewed application that has no network egress.
_FORWARDER = r"""
import socket, sys, threading
host, port, listen = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
def pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", listen))
server.listen(64)
while True:
    client, _ = server.accept()
    try:
        upstream = socket.create_connection((host, port), timeout=5)
        upstream.settimeout(None)
    except OSError:
        client.close()
        continue
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()
"""


def lock_hash_for(images_dir: Path, profile: str) -> str | None:
    lock = images_dir / profile / "requirements.lock"
    if not lock.is_file():
        return None
    return hashlib.sha256(lock.read_bytes()).hexdigest()


def image_reference(image: str, lock_hash: str) -> str:
    return f"{image}:{lock_hash[:12]}"


class _CappedReader(threading.Thread):
    """Drains a pipe, keeping at most ``limit`` bytes so output cannot exhaust memory."""

    def __init__(self, stream: object, limit: int) -> None:
        super().__init__(daemon=True)
        self._stream = stream
        self._limit = limit
        self.data = bytearray()
        self.truncated = False

    def run(self) -> None:
        read = self._stream.read  # type: ignore[attr-defined]
        while True:
            chunk = read(65536)
            if not chunk:
                return
            room = self._limit - len(self.data)
            if room > 0:
                self.data.extend(chunk[:room])
            if len(chunk) > room:
                self.truncated = True


class DockerServeHandle:
    def __init__(
        self, driver: DockerSandboxDriver, app: str, forwarder: str, network: str, host_port: int
    ) -> None:
        self._driver = driver
        self._app = app
        self._forwarder = forwarder
        self._network = network
        self.host_port = host_port
        self.url = f"http://127.0.0.1:{host_port}"
        self.app_container = app

    def wait_ready(self, path: str = "/", timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(self.url + path, timeout=2):  # noqa: S310
                    return True
            except urllib.error.HTTPError:
                return True  # the application answered; the status code is its business
            except (OSError, urllib.error.URLError):
                time.sleep(0.3)
        return False

    def logs(self) -> str:
        done = self._driver._docker("logs", "--tail", "200", self._app, check=False)
        return (done.stdout + done.stderr)[-20000:]

    def stop(self) -> None:
        self._driver._docker("rm", "-f", self._forwarder, self._app, check=False)
        self._driver._docker("network", "rm", self._network, check=False)


class DockerSandboxDriver:
    name = "docker"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._binary = settings.sandbox.docker_binary

    # ----- helpers -------------------------------------------------------------------------

    def _docker(
        self, *args: str, check: bool = True, timeout: float = 60
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._binary, *args], capture_output=True, text=True, check=check, timeout=timeout
        )

    def _profile(self, profile: str) -> ProfileStatus:
        configured = self._settings.sandbox.profiles.get(profile)
        if configured is None:
            return ProfileStatus(profile, None, False, None, None)
        lock_hash = lock_hash_for(self._settings.sandbox_images_dir, profile)
        if lock_hash is None:
            return ProfileStatus(profile, None, False, None, None)
        ref = image_reference(configured.image, lock_hash)
        try:
            done = self._docker("image", "inspect", "--format", "{{.Id}}", ref, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return ProfileStatus(profile, ref, False, None, lock_hash)
        if done.returncode != 0:
            return ProfileStatus(profile, ref, False, None, lock_hash)
        return ProfileStatus(profile, ref, True, done.stdout.strip(), lock_hash)

    def probe(self) -> SandboxCapability:
        """Report whether generated code can be executed. Never raises."""
        if shutil.which(self._binary) is None:
            return SandboxCapability(
                False,
                self.name,
                "Docker was not found on this machine. Install Docker to build, test and "
                "preview prototypes; everything else works without it.",
            )
        try:
            done = self._docker(
                "version", "--format", "{{.Server.Version}}", check=False, timeout=15
            )
        except (OSError, subprocess.TimeoutExpired):
            done = None
        if done is None or done.returncode != 0:
            return SandboxCapability(
                False,
                self.name,
                "Docker is installed but its daemon is not reachable. Start Docker and retry.",
            )
        profiles = [self._profile(name) for name in sorted(self._settings.sandbox.profiles)]
        core = next((p for p in profiles if p.profile == "core"), None)
        if core is None or not core.present:
            return SandboxCapability(
                False,
                self.name,
                "The sandbox image has not been built. Run `make sandbox-images`.",
                profiles,
            )
        return SandboxCapability(True, self.name, None, profiles)

    def _require(self, profile: str) -> ProfileStatus:
        capability = self.probe()
        status = next((p for p in capability.profiles if p.profile == profile), None)
        if status is None or not status.present:
            raise SandboxUnavailableError(
                capability.reason
                or f"The sandbox image for profile '{profile}' has not been built.",
                next_actions=["Start Docker, run `make sandbox-images`, then retry."],
            )
        return status

    def _hardening(
        self, spec: SandboxSpec, limits: SandboxLimits, name: str, role: str
    ) -> list[str]:
        uid = self._settings.sandbox.run_uid
        args = [
            "--name", name,
            "--label", f"{LABEL}={role}",
            "--read-only",
            "--tmpfs", f"/tmp:rw,nosuid,nodev,size={limits.tmpfs_mb}m,mode=1777",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(limits.pids),
            "--memory", f"{limits.memory_mb}m",
            "--memory-swap", f"{limits.memory_mb}m",
            "--cpus", str(limits.cpus),
            "--user", f"{uid}:{uid}",
            "--hostname", "sandbox",
            "--workdir", spec.workdir if spec.workspace is not None else "/tmp",
            "--env", "HOME=/tmp",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "PYTHONUNBUFFERED=1",
        ]  # fmt: skip
        # The Docker client can inject proxy settings from its own configuration; blank them
        # so nothing about the host's network set-up reaches the container.
        for var in _PROXY_VARS:
            args += ["--env", f"{var}="]
        for key, value in spec.env.items():
            if "=" in key or not key:
                raise ValueError(f"invalid environment variable name: {key!r}")
            args += ["--env", f"{key}={value}"]
        if spec.workspace is not None:
            workspace = spec.workspace.resolve()
            if not workspace.is_dir():
                raise ValueError(f"workspace does not exist: {workspace}")
            make_tree_writable_for_sandbox(workspace)
            args += ["--mount", f"type=bind,src={workspace},dst=/workspace"]
        for host_path, container_path in spec.readonly_mounts.items():
            source = Path(host_path).resolve()
            if not source.exists():
                raise ValueError(f"read-only mount does not exist: {source}")
            args += ["--mount", f"type=bind,src={source},dst={container_path},readonly"]
        return args

    @staticmethod
    def _wrapped(command: list[str], timeout_seconds: float | None) -> list[str]:
        # umask 000 keeps files created by the sandbox user manageable by the platform user.
        inner = ["/bin/sh", "-c", 'umask 000; exec "$@"', "sandbox", *command]
        if timeout_seconds is None:
            return inner
        return ["timeout", "--signal=KILL", str(int(timeout_seconds) + 5), *inner]

    # ----- run -----------------------------------------------------------------------------

    def run(self, spec: SandboxSpec) -> SandboxResult:
        status = self._require(spec.profile)
        assert status.image and status.image_digest and status.lock_hash
        limits = spec.limits or self._settings.sandbox.limits
        name = f"pp-sbx-{uuid.uuid4().hex[:16]}"
        args = [
            self._binary, "run", "--network", "none", "--log-driver", "none",
            *self._hardening(spec, limits, name, "run"),
            status.image,
            *self._wrapped(spec.command, limits.timeout_seconds),
        ]  # fmt: skip
        started = time.monotonic()
        timed_out = False
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = _CappedReader(process.stdout, limits.output_limit_bytes)
        err = _CappedReader(process.stderr, limits.output_limit_bytes)
        out.start()
        err.start()
        try:
            try:
                process.wait(timeout=limits.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._docker("kill", name, check=False)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            out.join(timeout=5)
            err.join(timeout=5)
            duration = time.monotonic() - started
            inspected = self._docker(
                "inspect", "--format", "{{.State.OOMKilled}}|{{.State.ExitCode}}", name, check=False
            )
            oom_killed = False
            exit_code = process.returncode if process.returncode is not None else -1
            if inspected.returncode == 0 and "|" in inspected.stdout:
                oom_text, code_text = inspected.stdout.strip().split("|", 1)
                oom_killed = oom_text == "true"
                if code_text.lstrip("-").isdigit():
                    exit_code = int(code_text)
        finally:
            self._docker("rm", "-f", name, check=False)
        return SandboxResult(
            exit_code=exit_code,
            stdout=out.data.decode("utf-8", "replace"),
            stderr=err.data.decode("utf-8", "replace"),
            timed_out=timed_out,
            oom_killed=oom_killed,
            duration_seconds=round(duration, 3),
            image=status.image,
            image_digest=status.image_digest,
            lock_hash=status.lock_hash,
            output_truncated=out.truncated or err.truncated,
        )

    # ----- serve ---------------------------------------------------------------------------

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])

    def serve(
        self, spec: SandboxSpec, container_port: int, host_port: int | None = None
    ) -> DockerServeHandle:
        """Run a long-lived process with no egress, reachable only on 127.0.0.1.

        The application sits on an internal Docker network that has no route out. A second
        container running only platform code forwards one loopback port to it.
        """
        status = self._require(spec.profile)
        assert status.image
        limits = spec.limits or self._settings.sandbox.limits
        token = uuid.uuid4().hex[:12]
        network, app, forwarder = f"pp-net-{token}", f"pp-app-{token}", f"pp-fwd-{token}"
        port = host_port or self._free_port()
        handle = DockerServeHandle(self, app, forwarder, network, port)
        try:
            self._docker("network", "create", "--internal", "--label", f"{LABEL}=serve", network)
            self._docker(
                "run", "--detach", "--network", network, "--network-alias", "app",
                *self._hardening(spec, limits, app, "serve"),
                status.image, *self._wrapped(spec.command, None),
            )  # fmt: skip
            forwarder_spec = SandboxSpec(command=[])
            forwarder_limits = SandboxLimits(cpus=0.5, memory_mb=64, pids=128, tmpfs_mb=8)
            self._docker(
                "run", "--detach", "--publish", f"127.0.0.1:{port}:8080",
                *self._hardening(forwarder_spec, forwarder_limits, forwarder, "forwarder"),
                status.image, "python", "-c", _FORWARDER, "app", str(container_port), "8080",
            )  # fmt: skip
            self._docker("network", "connect", network, forwarder)
        except BaseException:
            handle.stop()
            raise
        return handle

    # ----- housekeeping --------------------------------------------------------------------

    def remove_exited(self) -> int:
        """Remove sandbox containers left behind by an interrupted worker."""
        try:
            listed = self._docker(
                "ps", "-aq", "--filter", f"label={LABEL}", "--filter", "status=exited", check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return 0
        ids = listed.stdout.split()
        if ids:
            self._docker("rm", "-f", *ids, check=False)
        return len(ids)


def build_sandbox_driver(settings: Settings) -> DockerSandboxDriver:
    if settings.sandbox.driver != "docker":
        raise ValueError(f"unknown sandbox driver: {settings.sandbox.driver}")
    return DockerSandboxDriver(settings)
