from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from protopitch.api.deps import Ctx
from protopitch.api.schemas import JobOut
from protopitch.jobs.backend import JobStatus

router = APIRouter(tags=["jobs"])

POLL_SECONDS = 0.4
KEEPALIVE_SECONDS = 15.0


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(ctx: Ctx, project_id: str | None = None, limit: int = 50) -> list[JobOut]:
    jobs = ctx.jobs.list_jobs(project_id, max(1, min(limit, 200)))
    return [JobOut.model_validate(asdict(job)) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, ctx: Ctx) -> JobOut:
    return JobOut.model_validate(asdict(ctx.jobs.get_job(job_id)))


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    request: Request,
    ctx: Ctx,
    last_event_id: str | None = Header(default=None),
    after: int = 0,
) -> StreamingResponse:
    """Server-sent events: the job's log lines, then ``end`` once the job has finished.

    Reconnecting clients send ``Last-Event-ID`` and receive only what they missed.
    """
    await run_in_threadpool(ctx.jobs.get_job, job_id)  # 404 before the stream starts
    cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else after

    async def stream() -> AsyncIterator[str]:
        nonlocal cursor
        idle = 0.0
        while True:
            if await request.is_disconnected():
                return
            job = await run_in_threadpool(ctx.jobs.get_job, job_id)
            events = await run_in_threadpool(ctx.jobs.events_after, job_id, cursor)
            for event in events:
                cursor = event.id
                data = json.dumps(
                    {
                        "id": event.id,
                        "step": event.step,
                        "level": event.level,
                        "message": event.message,
                        "created_at": event.created_at.isoformat(),
                    }
                )
                yield f"id: {event.id}\nevent: log\ndata: {data}\n\n"
            if events:
                idle = 0.0
                continue
            if job.status in JobStatus.TERMINAL:
                yield f"event: end\ndata: {json.dumps({'status': job.status})}\n\n"
                return
            await asyncio.sleep(POLL_SECONDS)
            idle += POLL_SECONDS
            if idle >= KEEPALIVE_SECONDS:
                idle = 0.0
                yield ": keep-alive\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
