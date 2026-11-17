"""Wiring: builds the platform's services from settings. API and worker both use this."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine

from protopitch.db.migrate import upgrade
from protopitch.db.session import SessionFactory, make_engine, make_session_factory
from protopitch.jobs.db_backend import DbJobBackend
from protopitch.jobs.registry import JobRegistry, build_registry
from protopitch.jobs.worker import Worker
from protopitch.sandbox.docker import DockerSandboxDriver, build_sandbox_driver
from protopitch.security.redaction import Redactor
from protopitch.settings import Settings, load_settings
from protopitch.storage.artifacts import LocalArtifactStore
from protopitch.storage.workspace import WorkspaceManager


@dataclass
class AppContext:
    settings: Settings
    engine: Engine
    sessions: SessionFactory
    artifacts: LocalArtifactStore
    workspaces: WorkspaceManager
    registry: JobRegistry
    jobs: DbJobBackend
    sandbox: DockerSandboxDriver
    redactor: Redactor

    def make_worker(self, worker_id: str | None = None) -> Worker:
        return Worker(
            settings=self.settings,
            backend=self.jobs,
            registry=self.registry,
            artifacts=self.artifacts,
            workspaces=self.workspaces,
            sandbox=self.sandbox,
            worker_id=worker_id,
        )

    def close(self) -> None:
        self.engine.dispose()


def build_context(settings: Settings | None = None, *, migrate: bool = True) -> AppContext:
    settings = settings or load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    try:
        settings.data_dir.chmod(0o700)  # project data is private to the owner's account
    except PermissionError:
        pass
    settings.workspaces_dir.mkdir(parents=True, exist_ok=True)
    if migrate:
        upgrade(settings.database_url)
    engine = make_engine(settings.database_url)
    sessions = make_session_factory(engine)
    redactor = Redactor.from_environment()
    artifacts = LocalArtifactStore(settings.artifacts_dir)
    registry = build_registry(settings.jobs.extra_modules)
    return AppContext(
        settings=settings,
        engine=engine,
        sessions=sessions,
        artifacts=artifacts,
        workspaces=WorkspaceManager(settings.workspaces_dir, artifacts),
        registry=registry,
        jobs=DbJobBackend(sessions, registry, redactor),
        sandbox=build_sandbox_driver(settings),
        redactor=redactor,
    )
