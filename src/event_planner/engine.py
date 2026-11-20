"""Template loader and event generation engine."""
from datetime import date, datetime, timedelta
from typing import List, Tuple
import uuid

from event_planner.models import Event, Task, Template, TaskStatus
from event_planner.dependencies import validate_task_dependencies


def instantiate_event_from_template(
    event: Event,
    template: Template,
    id_generator=None,
) -> List[Task]:
    """
    Instantiates tasks for an event from a template blueprint.

    Calculates task due dates based on `relative_days` from the event date.
    Remaps intra-template task dependencies to the newly generated task IDs.
    Validates the generated task dependency graph before returning.

    Args:
        event: The target event.
        template: The source template blueprint.
        id_generator: Optional callable producing unique string IDs (defaults to uuid4).

    Returns:
        List of generated Task objects with dependencies resolved and validated.
    """
    if id_generator is None:
        id_generator = lambda: str(uuid.uuid4())

    # Map template_task_id -> new generated task_id
    id_mapping = {
        tmpl_task.template_task_id: id_generator()
        for tmpl_task in template.default_tasks
    }

    # Normalize event date
    event_date = event.date
    if isinstance(event_date, datetime):
        event_base_date = event_date.date()
    else:
        event_base_date = event_date

    tasks: List[Task] = []
    for tmpl_task in template.default_tasks:
        task_id = id_mapping[tmpl_task.template_task_id]
        due_date = event_base_date + timedelta(days=tmpl_task.relative_days)

        # Map dependencies
        resolved_deps = [
            id_mapping[dep_tmpl_id]
            for dep_tmpl_id in tmpl_task.depends_on
            if dep_tmpl_id in id_mapping
        ]

        task = Task(
            id=task_id,
            event_id=event.id,
            title=tmpl_task.title,
            due_date=due_date,
            status=TaskStatus.TODO,
            depends_on=resolved_deps,
            vendor_category=tmpl_task.vendor_category,
        )
        tasks.append(task)

    # Validate generated tasks dependencies
    validate_task_dependencies(tasks)

    return tasks
