"""Job types that belong to the foundation (M1)."""

from __future__ import annotations

import json
from typing import Any

from protopitch.domain.hashing import text_hash
from protopitch.jobs.registry import (
    JobDefinition,
    JobRegistry,
    PermanentStepError,
    StepContext,
    StepDefinition,
)
from protopitch.sandbox.driver import SandboxSpec

PROJECT_BOOTSTRAP = "project.bootstrap"
SANDBOX_SELFTEST = "sandbox.selftest"


# ----- project.bootstrap ------------------------------------------------------------------


def verify_jd(ctx: StepContext) -> dict[str, Any]:
    """Confirm the stored job description is intact before anything depends on it."""
    sha256 = str(ctx.payload["jd_sha256"])
    data = ctx.artifacts.get_bytes(sha256)
    if text_hash(data.decode("utf-8")) != sha256:
        raise PermanentStepError("The stored job description does not match its hash.")
    ctx.log(f"Job description verified ({len(data)} bytes).")
    return {
        "artifacts": [
            {"kind": "jd_original", "name": "jd/original.txt", "sha256": sha256, "size": len(data)}
        ]
    }


def init_workspace(ctx: StepContext) -> dict[str, Any]:
    """Create the project's own, isolated workspace for this version."""
    assert ctx.workspace is not None
    meta = ctx.workspace / ".protopitch"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "project.json").write_text(
        json.dumps(
            {
                "project_id": ctx.job.project_id,
                "version": ctx.job.version,
                "jd_sha256": ctx.payload["jd_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    ctx.log("Workspace initialised.")
    return {"files": [".protopitch/project.json"]}


# ----- sandbox.selftest -------------------------------------------------------------------

_SELFTEST = r"""
import json, os, socket, sys
report = {"uid": os.getuid(), "python": sys.version.split()[0], "env_names": sorted(os.environ)}
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3).close()
    report["network"] = "reachable"
except OSError as exc:
    report["network"] = "blocked: " + exc.__class__.__name__
try:
    open("/etc/protopitch-selftest", "w").close()
    report["root_fs"] = "writable"
except OSError:
    report["root_fs"] = "read-only"
with open("/workspace/selftest.txt", "w") as handle:
    handle.write("ok\n")
report["workspace"] = "writable"
print(json.dumps(report))
"""


def selftest_probe(ctx: StepContext) -> dict[str, Any]:
    capability = ctx.sandbox.probe()
    if not capability.available:
        raise PermanentStepError(
            capability.reason or "The sandbox is unavailable.", code="sandbox_unavailable"
        )
    ctx.log("Sandbox driver and image are available.")
    return {"driver": capability.driver}


def selftest_run(ctx: StepContext) -> dict[str, Any]:
    """Run a platform-authored script in the sandbox and record what the sandbox allowed."""
    assert ctx.workspace is not None
    result = ctx.sandbox.run(
        SandboxSpec(command=["python", "-c", _SELFTEST], workspace=ctx.workspace)
    )
    if not result.ok:
        raise PermanentStepError(
            f"Sandbox self-test exited with {result.exit_code}: {result.stderr[-400:]}"
        )
    report = json.loads(result.stdout.strip().splitlines()[-1])
    problems = []
    if report["uid"] == 0:
        problems.append("the sandbox ran as root")
    if report["network"] == "reachable":
        problems.append("the sandbox reached the network")
    if report["root_fs"] != "read-only":
        problems.append("the sandbox root filesystem was writable")
    if problems:
        raise PermanentStepError("Sandbox isolation check failed: " + "; ".join(problems) + ".")
    ctx.log(
        f"Isolation confirmed: uid {report['uid']}, network {report['network']}, "
        f"root filesystem {report['root_fs']}."
    )
    # The image digest and lock hash are recorded on the run (M1 acceptance criterion).
    return {
        "report": report,
        "sandbox": result.provenance(),
        "duration_seconds": result.duration_seconds,
    }


def register(registry: JobRegistry) -> None:
    registry.register(
        JobDefinition(
            type=PROJECT_BOOTSTRAP,
            steps=(
                StepDefinition("verify_jd", verify_jd),
                StepDefinition("init_workspace", init_workspace),
            ),
            uses_workspace=True,
            fails_project=True,
        )
    )
    registry.register(
        JobDefinition(
            type=SANDBOX_SELFTEST,
            steps=(
                StepDefinition("probe", selftest_probe),
                StepDefinition("run_isolation_check", selftest_run),
            ),
            uses_workspace=True,
        )
    )
