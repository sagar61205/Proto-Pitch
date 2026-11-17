from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from protopitch import __version__
from protopitch.api.deps import Ctx
from protopitch.api.schemas import ERROR_RESPONSES, JobOut, SandboxStatus, SystemStatus
from protopitch.jobs.builtin import SANDBOX_SELFTEST

router = APIRouter(tags=["system"], responses=ERROR_RESPONSES)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system/status", response_model=SystemStatus)
def status(ctx: Ctx) -> SystemStatus:
    """What this installation can do right now. Never fails because Docker is missing."""
    # Generated code runs where the worker runs, so a live worker's report is authoritative.
    # Without one, describe what this process can see.
    reported = ctx.jobs.latest_worker_report(ctx.settings.jobs.worker_report_seconds * 3)
    sandbox = SandboxStatus.model_validate(reported or asdict(ctx.sandbox.probe()))
    return SystemStatus(
        version=__version__,
        worker_online=reported is not None,
        generation_available=sandbox.available,
        sandbox=sandbox,
        model_providers_configured=[],
        job_types=ctx.registry.types(),
    )


@router.post("/system/sandbox-selftest", response_model=JobOut, status_code=202)
def sandbox_selftest(ctx: Ctx) -> JobOut:
    """Queue an isolation self-test. If the sandbox is unavailable the job fails and says why."""
    job_id = ctx.jobs.enqueue(SANDBOX_SELFTEST)
    return JobOut.model_validate(asdict(ctx.jobs.get_job(job_id)))
