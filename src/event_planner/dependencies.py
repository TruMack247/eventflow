"""Dependency validation and topological sorting for tasks."""
from typing import Dict, List, Set
from event_planner.models import Task


class DependencyValidationError(Exception):
    """Raised when task dependency graph is invalid (cyclic or missing tasks)."""
    pass


def validate_task_dependencies(tasks: List[Task]) -> List[str]:
    """
    Validates task dependencies within an event.
    Ensures:
      1. Every task belongs to the same event.
      2. No duplicate task IDs exist.
      3. All referenced prerequisite tasks exist in the task set.
      4. No self-dependencies or cyclic dependency loops exist.

    Returns:
      Topologically sorted list of task IDs (dependencies first).

    Raises:
      DependencyValidationError if any validation check fails.
    """
    if not tasks:
        return []

    event_ids = {t.event_id for t in tasks}
    if len(event_ids) > 1:
        raise DependencyValidationError(f"Tasks belong to multiple events: {event_ids}")

    task_map: Dict[str, Task] = {}
    for task in tasks:
        if task.id in task_map:
            raise DependencyValidationError(f"Duplicate task ID detected: '{task.id}'")
        task_map[task.id] = task

    # Referential integrity check
    for task in tasks:
        for dep_id in task.depends_on:
            if dep_id == task.id:
                raise DependencyValidationError(
                    f"Task '{task.id}' cannot depend on itself (self-dependency)"
                )
            if dep_id not in task_map:
                raise DependencyValidationError(
                    f"Task '{task.id}' depends on missing task ID '{dep_id}'"
                )

    # Cycle detection via Kahn's algorithm
    in_degree: Dict[str, int] = {t.id: 0 for t in tasks}
    graph: Dict[str, List[str]] = {t.id: [] for t in tasks}

    for task in tasks:
        for dep_id in task.depends_on:
            # dep_id -> task.id (dep_id must finish before task.id)
            graph[dep_id].append(task.id)
            in_degree[task.id] += 1

    # Queue of nodes with no incoming dependencies
    queue: List[str] = [task_id for task_id, deg in in_degree.items() if deg == 0]
    topological_order: List[str] = []

    while queue:
        current = queue.pop(0)
        topological_order.append(current)

        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(topological_order) != len(tasks):
        cyclic_tasks = [t_id for t_id, deg in in_degree.items() if deg > 0]
        raise DependencyValidationError(
            f"Circular dependency detected involving tasks: {cyclic_tasks}"
        )

    return topological_order
