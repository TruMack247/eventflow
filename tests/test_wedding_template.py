"""Tests for wedding template and template instantiation engine."""
from datetime import date, timedelta
from decimal import Decimal
import pytest

from event_planner.models import Event, EventStatus
from event_planner.templates import get_wedding_template
from event_planner.engine import instantiate_event_from_template
from event_planner.dependencies import validate_task_dependencies


def test_wedding_template_structure():
    wedding_template = get_wedding_template()
    assert wedding_template.id == "wedding_standard_v1"
    assert len(wedding_template.default_tasks) == 7

    # Ensure all relative_days are negative (before wedding)
    for task in wedding_template.default_tasks:
        assert task.relative_days < 0


def test_wedding_instantiation_end_to_end():
    wedding_date = date(2027, 9, 18)
    event = Event(
        id="evt-wedding-42",
        name="Alex & Jordan Wedding",
        date=wedding_date,
        status=EventStatus.CONFIRMED,
        budget=Decimal("45000.00"),
        template_id="wedding_standard_v1",
    )

    wedding_template = get_wedding_template()
    counter = 0

    def mock_id_gen():
        nonlocal counter
        counter += 1
        return f"gen-task-{counter}"

    tasks = instantiate_event_from_template(event, wedding_template, id_generator=mock_id_gen)

    assert len(tasks) == 7
    for task in tasks:
        assert task.event_id == "evt-wedding-42"
        assert task.due_date < wedding_date

    # Validate that topological sort and cycle checks pass cleanly
    order = validate_task_dependencies(tasks)
    assert len(order) == 7

    # Find the budget task (should have no dependencies and be first in chain)
    budget_task = next(t for t in tasks if "budget" in t.title.lower())
    assert budget_task.depends_on == []
    assert budget_task.due_date == wedding_date + timedelta(days=-365)

    # Rehearsal task should be 1 day before wedding
    rehearsal_task = next(t for t in tasks if "rehearsal" in t.title.lower())
    assert rehearsal_task.due_date == wedding_date + timedelta(days=-1)
    assert len(rehearsal_task.depends_on) == 1
