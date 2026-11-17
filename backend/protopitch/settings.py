"""Configuration: YAML files in ``config/`` overridden by ``PROTOPITCH_*`` variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

ENV_PREFIX = "PROTOPITCH_"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServerSettings(_Section):
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    allowed_origins: list[str] = Field(default_factory=list)


class StorageSettings(_Section):
    data_dir: Path = Path("data")
    database_url: str | None = None


class AuthSettings(_Section):
    provider: str = "local_no_auth"


class JobSettings(_Section):
    lease_seconds: float = 30
    heartbeat_seconds: float = 5
    poll_interval_seconds: float = 1.0
    max_step_attempts: int = Field(default=3, ge=1, le=10)
    job_deadline_seconds: float = 3600
    worker_report_seconds: float = 10
    # Import paths of modules that register additional job types (extension by registration).
    extra_modules: list[str] = Field(default_factory=list)


class SandboxLimits(_Section):
    cpus: float = Field(default=2.0, gt=0)
    memory_mb: int = Field(default=2048, ge=16)
    pids: int = Field(default=256, ge=8)
    timeout_seconds: float = Field(default=600, gt=0)
    tmpfs_mb: int = Field(default=256, ge=1)
    output_limit_bytes: int = Field(default=1_000_000, ge=1024)


class SandboxProfile(_Section):
    image: str


class SandboxSettings(_Section):
    driver: str = "docker"
    docker_binary: str = "docker"
    run_uid: int = Field(default=10001, ge=1000)
    profiles: dict[str, SandboxProfile] = Field(
        default_factory=lambda: {"core": SandboxProfile(image="protopitch-sbx-core")}
    )
    limits: SandboxLimits = Field(default_factory=SandboxLimits)


class Settings(_Section):
    root_dir: Path
    server: ServerSettings = Field(default_factory=ServerSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    jobs: JobSettings = Field(default_factory=JobSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)

    @property
    def data_dir(self) -> Path:
        path = self.storage.data_dir
        return path if path.is_absolute() else (self.root_dir / path)

    @property
    def database_url(self) -> str:
        return self.storage.database_url or f"sqlite:///{self.data_dir / 'protopitch.db'}"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"

    @property
    def sandbox_images_dir(self) -> Path:
        return self.root_dir / "sandbox-images"

    @property
    def frontend_dist(self) -> Path:
        return self.root_dir / "frontend" / "dist"


def find_root(start: Path | None = None) -> Path:
    """Locate the repository root: the nearest ancestor that contains ``config/``."""
    explicit = os.environ.get(f"{ENV_PREFIX}ROOT")
    if explicit:
        return Path(explicit).resolve()
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "config" / "platform.yaml").is_file():
            return candidate
    return Path.cwd().resolve()


def _deep_merge(base: dict[str, Any], extra: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _env_overrides(env: Mapping[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, raw in env.items():
        if not name.startswith(ENV_PREFIX) or name == f"{ENV_PREFIX}ROOT":
            continue
        parts = [p.lower() for p in name[len(ENV_PREFIX) :].split("__")]
        if len(parts) < 2:
            continue
        node = out
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        try:
            node[parts[-1]] = yaml.safe_load(raw)
        except yaml.YAMLError:
            node[parts[-1]] = raw
    return out


def load_settings(root: Path | None = None, env: Mapping[str, str] | None = None) -> Settings:
    root_dir = (root or find_root()).resolve()
    merged: dict[str, Any] = {}
    config_dir = root_dir / "config"
    for name in ("platform.yaml", "limits.yaml"):
        path = config_dir / name
        if path.is_file():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"{path} must contain a mapping at the top level")
            _deep_merge(merged, loaded)
    _deep_merge(merged, _env_overrides(os.environ if env is None else env))
    merged["root_dir"] = root_dir
    return Settings.model_validate(merged)
