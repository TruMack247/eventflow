"""Workflow and schedule execution engine for event planning."""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union

from event_planner.models import Event, Task, TaskStatus


class WorkflowError(Exception):
    """Base exception for workflow and scheduling errors."""
    pass


class BlockedTaskError(WorkflowError):
    """Raised when attempting to advance a task whose dependencies are not yet completed."""
    pass


class DependentTasksBlockReopenError(WorkflowError):
    """Raised when reopening a completed task is blocked by downstream tasks in progress/done."""
    pass


def transition_task_status(
    task: Task,
    new_status: TaskStatus,
    all_tasks: List[Task],
    force: bool = False,
) -> Task:
    """
    Validates and applies a status transition to a task within the context of all event tasks.

    Rules:
      1. To transition to IN_PROGRESS or DONE, all tasks in `task.depends_on` must have status == DONE.
      2. If transitioning from DONE back to TODO or IN_PROGRESS:
         - Any downstream task that depends on this task and is IN_PROGRESS or DONE blocks reopening,
           unless `force=True`, in which case downstream tasks are reset to TODO.

    Returns:
      The updated Task instance.
    """
    if task.status == new_status:
        return task

    task_map: Dict[str, Task] = {t.id: t for t in all_tasks}

    # Advancing gate: cannot start or complete if dependencies aren't DONE
    if new_status in (TaskStatus.IN_PROGRESS, TaskStatus.DONE):
        unmet_deps = []
        for dep_id in task.depends_on:
            dep_task = task_map.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.DONE:
                unmet_deps.append(dep_id)

        if unmet_deps:
            raise BlockedTaskError(
                f"Cannot transition task '{task.id}' to '{new_status.value}'. "
                f"Unfinished prerequisite tasks: {unmet_deps}"
            )

    # Reopening gate: moving backward from DONE
    if task.status == TaskStatus.DONE and new_status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS):
        downstream_active: List[str] = [
            t.id
            for t in all_tasks
            if task.id in t.depends_on and t.status in (TaskStatus.IN_PROGRESS, TaskStatus.DONE)
        ]
        if downstream_active:
            if not force:
                raise DependentTasksBlockReopenError(
                    f"Cannot reopen completed task '{task.id}'. "
                    f"Downstream dependent tasks are active/done: {downstream_active}. "
                    "Use force=True to cascade reopen."
                )
            else:
                # Reset downstream active tasks
                for t_id in downstream_active:
                    task_map[t_id].status = TaskStatus.TODO

    task.status = new_status
    return task


def get_actionable_tasks(tasks: List[Task]) -> List[Task]:
    """
    Returns all tasks currently actionable (in TODO status) whose prerequisites
    are all in DONE status (or tasks with no prerequisites).

    Tasks already IN_PROGRESS or DONE are excluded from this query.
    """
    task_map: Dict[str, Task] = {t.id: t for t in tasks}
    actionable: List[Task] = []

    for task in tasks:
        if task.status != TaskStatus.TODO:
            continue

        all_deps_done = True
        for dep_id in task.depends_on:
            dep_task = task_map.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.DONE:
                all_deps_done = False
                break

        if all_deps_done:
            actionable.append(task)

    return actionable


def reschedule_event(
    event: Event,
    tasks: List[Task],
    new_date: Union[date, datetime],
) -> Tuple[Event, List[Task]]:
    """
    Shifts the event date and cascades the identical relative delta to all tasks.

    Returns:
      A tuple of (updated_event, updated_tasks_list).
    """
    old_date = event.date

    # Normalize dates to compute delta
    old_base = old_date.date() if isinstance(old_date, datetime) else old_date
    new_base = new_date.date() if isinstance(new_date, datetime) else new_date
    delta = new_base - old_base

    event.date = new_date

    for task in tasks:
        task_due = task.due_date
        if isinstance(task_due, datetime):
            task.due_date = task_due + delta
        else:
            task.due_date = task_due + delta

    return event, tasks


def shift_task_due_date(
    tasks: List[Task],
    task_id: str,
    new_due_date: Union[date, datetime],
    cascade: bool = True,
    max_boundary_date: Optional[Union[date, datetime]] = None,
) -> List[Task]:
    """
    Updates the due date of a task, optionally cascading delays to downstream dependent tasks.

    If a prerequisite task's due date is moved beyond a downstream task's due date:
      - If cascade is True, downstream dependent tasks are pushed forward to match the prerequisite date.
      - If max_boundary_date (e.g. event date) is specified and any task is pushed past it,
        a WorkflowError is raised.

    Returns:
      The list of updated tasks.
    """
    task_map: Dict[str, Task] = {t.id: t for t in tasks}
    target_task = task_map.get(task_id)
    if not target_task:
        raise WorkflowError(f"Task '{task_id}' not found in task set")

    target_task.due_date = new_due_date

    if not cascade:
        return tasks

    # Build adjacency list: prerequisite -> [downstream dependents]
    downstream_graph: Dict[str, List[str]] = {t.id: [] for t in tasks}
    for task in tasks:
        for dep_id in task.depends_on:
            if dep_id in downstream_graph:
                downstream_graph[dep_id].append(task.id)

    queue = [task_id]
    while queue:
        curr_id = queue.pop(0)
        curr_task = task_map[curr_id]
        curr_due_base = (
            curr_task.due_date.date()
            if isinstance(curr_task.due_date, datetime)
            else curr_task.due_date
        )

        for dep_task_id in downstream_graph.get(curr_id, []):
            child_task = task_map[dep_task_id]
            child_due_base = (
                child_task.due_date.date()
                if isinstance(child_task.due_date, datetime)
                else child_task.due_date
            )

            # If prerequisite is scheduled AFTER downstream task, push downstream task
            if curr_due_base > child_due_base:
                if isinstance(child_task.due_date, datetime):
                    child_task.due_date = curr_task.due_date
                else:
                    child_task.due_date = curr_due_base
                queue.append(dep_task_id)

    if max_boundary_date is not None:
        boundary_base = (
            max_boundary_date.date()
            if isinstance(max_boundary_date, datetime)
            else max_boundary_date
        )
        for task in tasks:
            t_base = (
                task.due_date.date()
                if isinstance(task.due_date, datetime)
                else task.due_date
            )
            if t_base > boundary_base:
                raise WorkflowError(
                    f"Task '{task.id}' due date {task.due_date} exceeds maximum boundary {max_boundary_date}"
                )

    return tasks
