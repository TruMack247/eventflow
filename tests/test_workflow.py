"""Unit tests for workflow and schedule execution engine."""
from datetime import date, timedelta
from decimal import Decimal
import pytest

from event_planner.models import Event, EventStatus, Task, TaskStatus
from event_planner.workflow import (
    transition_task_status,
    get_actionable_tasks,
    reschedule_event,
    shift_task_due_date,
    BlockedTaskError,
    DependentTasksBlockReopenError,
    WorkflowError,
)


def _build_task_chain():
    """Returns a chain: t1 -> t2 -> t3."""
    t1 = Task(id="t1", event_id="evt-1", title="Task 1", due_date=date(2027, 4, 1), status=TaskStatus.TODO)
    t2 = Task(id="t2", event_id="evt-1", title="Task 2", due_date=date(2027, 4, 10), status=TaskStatus.TODO, depends_on=["t1"])
    t3 = Task(id="t3", event_id="evt-1", title="Task 3", due_date=date(2027, 4, 20), status=TaskStatus.TODO, depends_on=["t2"])
    return [t1, t2, t3]


def test_transition_independent_task():
    tasks = _build_task_chain()
    t1 = tasks[0]
    updated = transition_task_status(t1, TaskStatus.IN_PROGRESS, tasks)
    assert updated.status == TaskStatus.IN_PROGRESS

    updated = transition_task_status(t1, TaskStatus.DONE, tasks)
    assert updated.status == TaskStatus.DONE


def test_transition_blocked_by_unmet_dependency():
    tasks = _build_task_chain()
    t2 = tasks[1]

    # t1 is still TODO
    with pytest.raises(BlockedTaskError, match="Unfinished prerequisite tasks: \\['t1'\\]"):
        transition_task_status(t2, TaskStatus.IN_PROGRESS, tasks)

    with pytest.raises(BlockedTaskError, match="Unfinished prerequisite tasks: \\['t1'\\]"):
        transition_task_status(t2, TaskStatus.DONE, tasks)


def test_transition_allowed_when_dependencies_done():
    tasks = _build_task_chain()
    tasks[0].status = TaskStatus.DONE
    t2 = tasks[1]

    updated = transition_task_status(t2, TaskStatus.IN_PROGRESS, tasks)
    assert updated.status == TaskStatus.IN_PROGRESS

    updated = transition_task_status(t2, TaskStatus.DONE, tasks)
    assert updated.status == TaskStatus.DONE


def test_reopen_completed_task_prevented_when_downstream_active():
    tasks = _build_task_chain()
    tasks[0].status = TaskStatus.DONE
    tasks[1].status = TaskStatus.IN_PROGRESS
    t1 = tasks[0]

    # Reopening t1 should fail because t2 is in progress
    with pytest.raises(DependentTasksBlockReopenError, match="Downstream dependent tasks are active/done: \\['t2'\\]"):
        transition_task_status(t1, TaskStatus.TODO, tasks)


def test_reopen_completed_task_with_force_resets_downstream():
    tasks = _build_task_chain()
    tasks[0].status = TaskStatus.DONE
    tasks[1].status = TaskStatus.DONE
    tasks[2].status = TaskStatus.IN_PROGRESS
    t1 = tasks[0]

    transition_task_status(t1, TaskStatus.TODO, tasks, force=True)
    assert t1.status == TaskStatus.TODO
    # t2 depends on t1 so it should be reset to TODO
    assert tasks[1].status == TaskStatus.TODO


def test_get_actionable_tasks_initial_state():
    tasks = _build_task_chain()
    actionable = get_actionable_tasks(tasks)
    # Only t1 has no dependencies
    assert len(actionable) == 1
    assert actionable[0].id == "t1"


def test_get_actionable_tasks_progressing():
    tasks = _build_task_chain()
    tasks[0].status = TaskStatus.DONE
    actionable = get_actionable_tasks(tasks)
    # With t1 done, t2 is now actionable
    assert len(actionable) == 1
    assert actionable[0].id == "t2"

    tasks[1].status = TaskStatus.IN_PROGRESS
    actionable = get_actionable_tasks(tasks)
    # t2 is already in progress, not TODO
    assert len(actionable) == 0

    tasks[1].status = TaskStatus.DONE
    actionable = get_actionable_tasks(tasks)
    # With t2 done, t3 is now actionable
    assert len(actionable) == 1
    assert actionable[0].id == "t3"


def test_reschedule_event_shifts_all_tasks():
    event = Event(id="e1", name="Gala", date=date(2027, 6, 1), budget=Decimal("1000"))
    tasks = _build_task_chain()

    # Move event by +10 days
    new_event_date = date(2027, 6, 11)
    updated_evt, updated_tasks = reschedule_event(event, tasks, new_event_date)

    assert updated_evt.date == date(2027, 6, 11)
    assert updated_tasks[0].due_date == date(2027, 4, 11)
    assert updated_tasks[1].due_date == date(2027, 4, 20)
    assert updated_tasks[2].due_date == date(2027, 4, 30)


def test_shift_task_due_date_cascading():
    tasks = _build_task_chain()
    # t1 originally due 2027-04-01, t2 due 2027-04-10, t3 due 2027-04-20
    # Delay t1 to 2027-04-15 (past t2's due date)
    shift_task_due_date(tasks, "t1", date(2027, 4, 15), cascade=True)

    assert tasks[0].due_date == date(2027, 4, 15)
    # t2 pushed forward to match t1
    assert tasks[1].due_date == date(2027, 4, 15)
    # t3 remains 2027-04-20 because 2027-04-20 >= 2027-04-15
    assert tasks[2].due_date == date(2027, 4, 20)


def test_shift_task_due_date_exceeds_max_boundary_raises():
    tasks = _build_task_chain()
    event_date = date(2027, 4, 25)

    with pytest.raises(WorkflowError, match="exceeds maximum boundary"):
        shift_task_due_date(
            tasks,
            "t1",
            date(2027, 4, 26),
            cascade=True,
            max_boundary_date=event_date,
        )
