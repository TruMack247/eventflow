"""Tests for task dependency validation and cycle detection."""
from datetime import date
import pytest
from event_planner.models import Task, TaskStatus
from event_planner.dependencies import (
    validate_task_dependencies,
    DependencyValidationError,
)


def _make_task(task_id: str, depends_on: list[str] = None, event_id: str = "evt-1") -> Task:
    return Task(
        id=task_id,
        event_id=event_id,
        title=f"Task {task_id}",
        due_date=date(2027, 5, 1),
        status=TaskStatus.TODO,
        depends_on=depends_on or [],
    )


def test_empty_tasks_validation():
    assert validate_task_dependencies([]) == []


def test_independent_tasks():
    tasks = [_make_task("t1"), _make_task("t2")]
    order = validate_task_dependencies(tasks)
    assert set(order) == {"t1", "t2"}


def test_linear_dependency_order():
    # t1 -> t2 -> t3
    tasks = [
        _make_task("t3", depends_on=["t2"]),
        _make_task("t1"),
        _make_task("t2", depends_on=["t1"]),
    ]
    order = validate_task_dependencies(tasks)
    assert order == ["t1", "t2", "t3"]


def test_diamond_dependency_order():
    # t1 -> t2, t1 -> t3; t2 -> t4, t3 -> t4
    tasks = [
        _make_task("t4", depends_on=["t2", "t3"]),
        _make_task("t2", depends_on=["t1"]),
        _make_task("t3", depends_on=["t1"]),
        _make_task("t1"),
    ]
    order = validate_task_dependencies(tasks)
    assert order[0] == "t1"
    assert order[-1] == "t4"
    assert set(order[1:3]) == {"t2", "t3"}


def test_missing_dependency_raises():
    tasks = [_make_task("t1", depends_on=["missing-task"])]
    with pytest.raises(DependencyValidationError, match="depends on missing task"):
        validate_task_dependencies(tasks)


def test_self_dependency_raises():
    tasks = [_make_task("t1", depends_on=["t1"])]
    with pytest.raises(DependencyValidationError, match="cannot depend on itself"):
        validate_task_dependencies(tasks)


def test_circular_dependency_raises():
    # t1 -> t2 -> t3 -> t1
    tasks = [
        _make_task("t1", depends_on=["t3"]),
        _make_task("t2", depends_on=["t1"]),
        _make_task("t3", depends_on=["t2"]),
    ]
    with pytest.raises(DependencyValidationError, match="Circular dependency"):
        validate_task_dependencies(tasks)


def test_multiple_events_mismatch_raises():
    tasks = [
        _make_task("t1", event_id="evt-1"),
        _make_task("t2", event_id="evt-2"),
    ]
    with pytest.raises(DependencyValidationError, match="multiple events"):
        validate_task_dependencies(tasks)


def test_duplicate_task_id_raises():
    tasks = [
        _make_task("t1"),
        _make_task("t1"),
    ]
    with pytest.raises(DependencyValidationError, match="Duplicate task ID"):
        validate_task_dependencies(tasks)
