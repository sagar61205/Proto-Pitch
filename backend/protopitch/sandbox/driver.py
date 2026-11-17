"""Sandbox driver interface. Generated or untrusted code runs only through a driver."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from protopitch.settings import SandboxLimits


@dataclass(frozen=True)
class SandboxSpec:
    command: list[str]
    profile: str = "core"
    # Mounted read-write at /workspace. Nothing else from the host is writable.
    workspace: Path | None = None
    # Platform-owned inputs: host path -> container path, always read-only.
    readonly_mounts: Mapping[Path, str] = field(default_factory=dict)
    # Explicit variables only. The host environment is never passed through.
    env: Mapping[str, str] = field(default_factory=dict)
    limits: SandboxLimits | None = None
    workdir: str = "/workspace"


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    oom_killed: bool
    duration_seconds: float
    image: str
    image_digest: str
    lock_hash: str
    output_truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.oom_killed

    def provenance(self) -> dict[str, str]:
        return {"image": self.image, "image_digest": self.image_digest, "lock_hash": self.lock_hash}


@dataclass(frozen=True)
class ProfileStatus:
    profile: str
    image: str | None
    present: bool
    image_digest: str | None
    lock_hash: str | None


@dataclass(frozen=True)
class SandboxCapability:
    available: bool
    driver: str
    reason: str | None
    profiles: list[ProfileStatus] = field(default_factory=list)


class ServeHandle(Protocol):
    url: str
    host_port: int

    def wait_ready(self, path: str = "/", timeout: float = 30.0) -> bool: ...
    def logs(self) -> str: ...
    def stop(self) -> None: ...


class SandboxDriver(Protocol):
    name: str

    def probe(self) -> SandboxCapability: ...
    def run(self, spec: SandboxSpec) -> SandboxResult: ...
    def serve(
        self, spec: SandboxSpec, container_port: int, host_port: int | None = None
    ) -> ServeHandle: ...
