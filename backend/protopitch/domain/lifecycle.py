"""Project lifecycle: states and the only transitions that are allowed (ARCHITECTURE §5).

This module is pure: no database, no I/O. It imports nothing from the rest of the package.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProjectStatus(StrEnum):
    CREATED = "CREATED"
    JD_ANALYZED = "JD_ANALYZED"
    RESEARCHED = "RESEARCHED"
    OPPORTUNITIES_IDENTIFIED = "OPPORTUNITIES_IDENTIFIED"
    ARCHITECTURE_PROPOSED = "ARCHITECTURE_PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    GENERATING = "GENERATING"
    TESTING = "TESTING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    DEPLOYMENT_PENDING = "DEPLOYMENT_PENDING"
    DEPLOYED = "DEPLOYED"
    OUTREACH_READY = "OUTREACH_READY"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


S = ProjectStatus

# Ordinary transitions. FAILED and ARCHIVED are handled by the rules in plan_transition.
FORWARD: dict[ProjectStatus, frozenset[ProjectStatus]] = {
    S.CREATED: frozenset({S.JD_ANALYZED}),
    S.JD_ANALYZED: frozenset({S.RESEARCHED}),
    S.RESEARCHED: frozenset({S.OPPORTUNITIES_IDENTIFIED}),
    S.OPPORTUNITIES_IDENTIFIED: frozenset({S.ARCHITECTURE_PROPOSED}),
    S.ARCHITECTURE_PROPOSED: frozenset({S.AWAITING_APPROVAL}),
    # modify -> ARCHITECTURE_PROPOSED; regenerate -> OPPORTUNITIES_IDENTIFIED; approve -> APPROVED
    S.AWAITING_APPROVAL: frozenset(
        {S.ARCHITECTURE_PROPOSED, S.OPPORTUNITIES_IDENTIFIED, S.APPROVED}
    ),
    S.APPROVED: frozenset({S.GENERATING}),
    S.GENERATING: frozenset({S.TESTING}),
    S.TESTING: frozenset({S.GENERATING, S.READY_FOR_REVIEW}),
    # deployment and outreach are optional and independent; a new version restarts discovery
    S.READY_FOR_REVIEW: frozenset(
        {S.DEPLOYMENT_PENDING, S.OUTREACH_READY, S.OPPORTUNITIES_IDENTIFIED}
    ),
    S.DEPLOYMENT_PENDING: frozenset({S.DEPLOYED, S.READY_FOR_REVIEW}),
    S.DEPLOYED: frozenset({S.OUTREACH_READY, S.OPPORTUNITIES_IDENTIFIED}),
    S.OUTREACH_READY: frozenset({S.OPPORTUNITIES_IDENTIFIED}),
    S.FAILED: frozenset(),
    S.ARCHIVED: frozenset(),
}

# Transitions that are refused without a recorded approval of the given kind.
APPROVAL_REQUIRED: dict[tuple[ProjectStatus, ProjectStatus], str] = {
    (S.AWAITING_APPROVAL, S.APPROVED): "architecture",
    (S.READY_FOR_REVIEW, S.DEPLOYMENT_PENDING): "deployment",
}

# States from which a project can fail: everything that is not already terminal-ish.
WORKING_STATES: frozenset[ProjectStatus] = frozenset(
    s for s in ProjectStatus if s not in (S.FAILED, S.ARCHIVED)
)


class TransitionKind(StrEnum):
    FORWARD = "forward"
    FAIL = "fail"
    RESUME = "resume"
    ARCHIVE = "archive"
    UNARCHIVE = "unarchive"


class TransitionRefused(Exception):  # noqa: N818 - domain vocabulary
    def __init__(self, current: ProjectStatus, target: ProjectStatus, reason: str) -> None:
        super().__init__(f"{current} -> {target}: {reason}")
        self.current = current
        self.target = target
        self.reason = reason


@dataclass(frozen=True)
class TransitionPlan:
    kind: TransitionKind
    current: ProjectStatus
    target: ProjectStatus
    approval_kind: str | None = None


def plan_transition(
    current: ProjectStatus,
    target: ProjectStatus,
    *,
    failed_from: ProjectStatus | None = None,
    previous_status: ProjectStatus | None = None,
) -> TransitionPlan:
    """Return how ``current -> target`` is allowed, or raise ``TransitionRefused``."""
    if current == target:
        raise TransitionRefused(current, target, "the project is already in this state")

    if current == S.ARCHIVED:
        if previous_status is not None and target == previous_status:
            return TransitionPlan(TransitionKind.UNARCHIVE, current, target)
        raise TransitionRefused(
            current, target, "an archived project can only be restored to its previous state"
        )

    if target == S.ARCHIVED:
        return TransitionPlan(TransitionKind.ARCHIVE, current, target)

    if current == S.FAILED:
        if failed_from is not None and target == failed_from:
            return TransitionPlan(TransitionKind.RESUME, current, target)
        raise TransitionRefused(
            current, target, "a failed project can only be resumed from where it failed"
        )

    if target == S.FAILED:
        if current in WORKING_STATES:
            return TransitionPlan(TransitionKind.FAIL, current, target)
        raise TransitionRefused(current, target, "this state cannot fail")

    if target in FORWARD[current]:
        return TransitionPlan(
            TransitionKind.FORWARD, current, target, APPROVAL_REQUIRED.get((current, target))
        )
    allowed = ", ".join(sorted(FORWARD[current])) or "none"
    raise TransitionRefused(current, target, f"not an allowed transition (allowed: {allowed})")


def allowed_targets(
    current: ProjectStatus,
    *,
    failed_from: ProjectStatus | None = None,
    previous_status: ProjectStatus | None = None,
) -> list[ProjectStatus]:
    out = []
    for target in ProjectStatus:
        try:
            plan_transition(
                current, target, failed_from=failed_from, previous_status=previous_status
            )
        except TransitionRefused:
            continue
        out.append(target)
    return out
