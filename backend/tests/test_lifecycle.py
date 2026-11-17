"""State-machine tests, including property tests over random walks."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from protopitch.domain.lifecycle import (
    APPROVAL_REQUIRED,
    FORWARD,
    WORKING_STATES,
    ProjectStatus,
    TransitionKind,
    TransitionRefused,
    allowed_targets,
    plan_transition,
)

S = ProjectStatus
states = st.sampled_from(list(ProjectStatus))


def test_states_match_the_specification() -> None:
    assert [s.value for s in ProjectStatus] == [
        "CREATED", "JD_ANALYZED", "RESEARCHED", "OPPORTUNITIES_IDENTIFIED",
        "ARCHITECTURE_PROPOSED", "AWAITING_APPROVAL", "APPROVED", "GENERATING", "TESTING",
        "READY_FOR_REVIEW", "DEPLOYMENT_PENDING", "DEPLOYED", "OUTREACH_READY", "FAILED",
        "ARCHIVED",
    ]  # fmt: skip


def test_happy_path_is_allowed() -> None:
    path = [
        S.CREATED, S.JD_ANALYZED, S.RESEARCHED, S.OPPORTUNITIES_IDENTIFIED,
        S.ARCHITECTURE_PROPOSED, S.AWAITING_APPROVAL, S.APPROVED, S.GENERATING, S.TESTING,
        S.READY_FOR_REVIEW, S.DEPLOYMENT_PENDING, S.DEPLOYED, S.OUTREACH_READY,
    ]  # fmt: skip
    for current, target in zip(path, path[1:], strict=False):
        assert plan_transition(current, target).kind is TransitionKind.FORWARD


def test_documented_loops_and_optional_paths() -> None:
    assert plan_transition(S.AWAITING_APPROVAL, S.ARCHITECTURE_PROPOSED)  # modify
    assert plan_transition(S.AWAITING_APPROVAL, S.OPPORTUNITIES_IDENTIFIED)  # regenerate
    assert plan_transition(S.TESTING, S.GENERATING)  # bounded repair
    assert plan_transition(S.READY_FOR_REVIEW, S.OUTREACH_READY)  # outreach without deployment
    assert plan_transition(S.DEPLOYMENT_PENDING, S.READY_FOR_REVIEW)  # deployment failed
    assert plan_transition(S.READY_FOR_REVIEW, S.OPPORTUNITIES_IDENTIFIED)  # new version


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.CREATED, S.APPROVED),
        (S.CREATED, S.GENERATING),
        (S.JD_ANALYZED, S.READY_FOR_REVIEW),
        (S.AWAITING_APPROVAL, S.GENERATING),  # building requires APPROVED first
        (S.GENERATING, S.READY_FOR_REVIEW),  # cannot skip TESTING
        (S.TESTING, S.DEPLOYED),
        (S.READY_FOR_REVIEW, S.DEPLOYED),  # cannot skip the deployment approval step
        (S.OUTREACH_READY, S.CREATED),
    ],
)
def test_illegal_transitions_are_refused(current: S, target: S) -> None:
    with pytest.raises(TransitionRefused) as info:
        plan_transition(current, target)
    assert "allowed" in info.value.reason


def test_approval_gated_edges() -> None:
    assert plan_transition(S.AWAITING_APPROVAL, S.APPROVED).approval_kind == "architecture"
    assert plan_transition(S.READY_FOR_REVIEW, S.DEPLOYMENT_PENDING).approval_kind == "deployment"
    for edge in APPROVAL_REQUIRED:
        assert edge[1] in FORWARD[edge[0]]


def test_every_state_is_reachable_from_created() -> None:
    seen, frontier = {S.CREATED}, [S.CREATED]
    while frontier:
        for target in FORWARD[frontier.pop()]:
            if target not in seen:
                seen.add(target)
                frontier.append(target)
    assert seen == set(WORKING_STATES)


@given(current=states, target=states)
def test_forward_transitions_are_exactly_the_table(current: S, target: S) -> None:
    special = {S.FAILED, S.ARCHIVED}
    if current in special or target in special or current == target:
        return
    if target in FORWARD[current]:
        assert plan_transition(current, target).kind is TransitionKind.FORWARD
    else:
        with pytest.raises(TransitionRefused):
            plan_transition(current, target)


@given(current=states)
def test_no_self_transitions(current: S) -> None:
    with pytest.raises(TransitionRefused):
        plan_transition(current, current, failed_from=current, previous_status=current)


@given(current=states)
def test_failure_remembers_where_it_happened_and_resumes_only_there(current: S) -> None:
    if current not in WORKING_STATES:
        with pytest.raises(TransitionRefused):
            plan_transition(current, S.FAILED)
        return
    assert plan_transition(current, S.FAILED).kind is TransitionKind.FAIL
    assert plan_transition(S.FAILED, current, failed_from=current).kind is TransitionKind.RESUME
    for other in WORKING_STATES - {current}:
        with pytest.raises(TransitionRefused):
            plan_transition(S.FAILED, other, failed_from=current)


@given(current=states, other=states)
def test_archive_round_trip_restores_only_the_previous_state(current: S, other: S) -> None:
    if current is S.ARCHIVED:
        return
    assert plan_transition(current, S.ARCHIVED).kind is TransitionKind.ARCHIVE
    restored = plan_transition(S.ARCHIVED, current, previous_status=current)
    assert restored.kind is TransitionKind.UNARCHIVE
    if other not in (current, S.ARCHIVED):
        with pytest.raises(TransitionRefused):
            plan_transition(S.ARCHIVED, other, previous_status=current)


@settings(max_examples=200)
@given(data=st.data())
def test_random_walks_never_leave_the_allowed_graph(data: st.DataObject) -> None:
    """Follow only transitions the machine offers; its bookkeeping must stay consistent."""
    current, failed_from, previous = S.CREATED, None, None
    for _ in range(data.draw(st.integers(min_value=1, max_value=40))):
        options = allowed_targets(current, failed_from=failed_from, previous_status=previous)
        if not options:
            assert current is S.OUTREACH_READY or current in (S.FAILED, S.ARCHIVED)
            break
        target = data.draw(st.sampled_from(options))
        plan = plan_transition(current, target, failed_from=failed_from, previous_status=previous)
        if plan.kind is TransitionKind.FAIL:
            failed_from = current
        elif plan.kind is TransitionKind.RESUME:
            assert target == failed_from
            failed_from = None
        elif plan.kind is TransitionKind.ARCHIVE:
            previous = current
        elif plan.kind is TransitionKind.UNARCHIVE:
            assert target == previous
            previous = None
        else:
            assert target in FORWARD[current]
        current = target
