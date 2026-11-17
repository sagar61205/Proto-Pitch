"""Job types used only by tests. Loaded through the registry's extension mechanism."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from protopitch.jobs.registry import (
    JobDefinition,
    JobRegistry,
    PermanentStepError,
    StepContext,
    StepDefinition,
)


def _record(ctx: StepContext, label: str) -> None:
    """Append to a file outside the workspace so a test can count real executions."""
    marker_dir = ctx.payload.get("marker_dir")
    if marker_dir:
        with (Path(marker_dir) / f"{label}.runs").open("a", encoding="utf-8") as handle:
            handle.write(f"attempt={ctx.attempt}\n")


def _append(ctx: StepContext, text: str) -> None:
    assert ctx.workspace is not None
    with (ctx.workspace / "trace.txt").open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")


def step_one(ctx: StepContext) -> dict[str, Any]:
    _record(ctx, "one")
    _append(ctx, "1")
    ctx.log("step one wrote its line")
    return {"wrote": "1"}


def step_two_gated(ctx: StepContext) -> dict[str, Any]:
    """Blocks until the gate file exists, so a test can interrupt the worker mid-step."""
    _record(ctx, "two")
    assert ctx.workspace is not None
    # Half-finished work that must not survive an interruption:
    (ctx.workspace / "partial.tmp").write_text("incomplete", encoding="utf-8")
    gate = ctx.payload.get("gate")
    deadline = time.monotonic() + 60
    while gate and not Path(gate).exists():
        if time.monotonic() > deadline:
            raise PermanentStepError("gate never opened")
        time.sleep(0.05)
    (ctx.workspace / "partial.tmp").unlink()
    _append(ctx, "2")
    return {"saw_step_one": ctx.previous.get("one", {}).get("wrote")}


def step_three(ctx: StepContext) -> dict[str, Any]:
    _record(ctx, "three")
    _append(ctx, "3")
    return {}


def flaky(ctx: StepContext) -> dict[str, Any]:
    _record(ctx, "flaky")
    if ctx.attempt < int(ctx.payload.get("succeed_on", 3)):
        raise RuntimeError("transient problem with secret password=hunter2hunter2")
    return {"attempt": ctx.attempt}


def always_fails(ctx: StepContext) -> dict[str, Any]:
    _record(ctx, "always")
    raise RuntimeError("this step can never succeed")


def permanent(ctx: StepContext) -> dict[str, Any]:
    _record(ctx, "permanent")
    raise PermanentStepError("retrying cannot help", code="unsupported")


def register(registry: JobRegistry) -> None:
    registry.register(
        JobDefinition(
            type="test.three_steps",
            steps=(
                StepDefinition("one", step_one),
                StepDefinition("two", step_two_gated),
                StepDefinition("three", step_three),
            ),
            uses_workspace=True,
            fails_project=True,
        )
    )
    registry.register(JobDefinition("test.flaky", (StepDefinition("flaky", flaky),)))
    registry.register(
        JobDefinition(
            "test.always_fails", (StepDefinition("always", always_fails),), fails_project=True
        )
    )
    registry.register(JobDefinition("test.permanent", (StepDefinition("permanent", permanent),)))
