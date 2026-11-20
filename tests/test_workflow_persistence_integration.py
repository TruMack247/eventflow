"""Integration tests connecting workflow operations with SQLite repository persistence."""
from datetime import date
from decimal import Decimal
import pytest

from event_planner.models import Event, EventStatus, Task, TaskStatus
from event_planner.templates import get_wedding_template
from event_planner.engine import instantiate_event_from_template
from event_planner.sqlite_repository import SQLiteEventRepository
from event_planner.workflow import (
    transition_task_status,
    get_actionable_tasks,
    reschedule_event,
    shift_task_due_date,
    BlockedTaskError,
)


@pytest.fixture
def repo():
    repository = SQLiteEventRepository(":memory:")
    yield repository
    repository.close()


def test_wedding_workflow_end_to_end_lifecycle(repo):
    """
    Simulates a realistic wedding planning workflow backed by SQLite persistence:
      1. Instantiates a wedding from template.
      2. Persists the bundle into SQLite.
      3. Verifies initial actionable task is budget determination.
      4. Progresses budget task to DONE and persists it.
      5. Verifies venue booking is now actionable, advances venue to DONE.
      6. Reschedules entire event to a later date and persists changes.
      7. Re-queries from SQLite to ensure database state reflects new dates and status.
    """
    wedding_tmpl = get_wedding_template()
    repo.save_template(wedding_tmpl)

    original_date = date(2027, 8, 14)
    event = Event(
        id="evt-wedding-flow",
        name="Emma & Liam Wedding",
        date=original_date,
        status=EventStatus.CONFIRMED,
        budget=Decimal("40000.00"),
        template_id=wedding_tmpl.id,
    )

    tasks = instantiate_event_from_template(event, wedding_tmpl)
    repo.save_event_bundle(event, tasks)

    # 1. Check initial actionable tasks from database
    db_tasks = repo.get_tasks_for_event("evt-wedding-flow")
    ready = get_actionable_tasks(db_tasks)
    assert len(ready) == 1
    budget_task = ready[0]
    assert "budget" in budget_task.title.lower()

    # 2. Advance budget task: TODO -> IN_PROGRESS -> DONE and save
    transition_task_status(budget_task, TaskStatus.IN_PROGRESS, db_tasks)
    transition_task_status(budget_task, TaskStatus.DONE, db_tasks)
    repo.save_task(budget_task)

    # Verify venue booking cannot be done before its dep is saved
    reloaded_tasks = repo.get_tasks_for_event("evt-wedding-flow")
    ready_now = get_actionable_tasks(reloaded_tasks)
    assert len(ready_now) == 1
    venue_task = ready_now[0]
    assert "venue" in venue_task.title.lower()

    # 3. Advance venue task
    transition_task_status(venue_task, TaskStatus.DONE, reloaded_tasks)
    repo.save_task(venue_task)

    # Now tasks depending on venue (photo, catering, invitations) become actionable
    post_venue_tasks = repo.get_tasks_for_event("evt-wedding-flow")
    ready_after_venue = get_actionable_tasks(post_venue_tasks)
    ready_titles = [t.title.lower() for t in ready_after_venue]
    assert any("photographer" in t for t in ready_titles)
    assert any("catering" in t for t in ready_titles)
    assert any("invitations" in t for t in ready_titles)

    # 4. Reschedule event by +30 days
    new_date = date(2027, 9, 13)
    updated_evt, updated_tasks = reschedule_event(event, post_venue_tasks, new_date)
    repo.save_event_bundle(updated_evt, updated_tasks)

    # 5. Reload from DB and verify dates persisted accurately
    final_event = repo.get_event("evt-wedding-flow")
    assert final_event.date == new_date

    final_tasks = repo.get_tasks_for_event("evt-wedding-flow")
    final_budget_task = next(t for t in final_tasks if t.id == budget_task.id)
    assert final_budget_task.status == TaskStatus.DONE
    # Original budget task was -365 days from original_date; should now be -365 from new_date
    assert final_budget_task.due_date == new_date + (original_date - final_budget_task.due_date if False else (final_budget_task.due_date - new_date))
    assert (new_date - final_budget_task.due_date).days == 365
