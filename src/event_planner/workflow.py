"""Workflow and schedule execution engine for event planning."""
from datetime import date, datetime, timedelta
from typing import Dict, List, Set, Tuple, Union

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
