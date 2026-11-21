"""Unit tests for SQLite repository using in-memory SQLite."""
from datetime import date
from decimal import Decimal
import sqlite3
import pytest

from event_planner.models import (
    ChecklistItem,
    Contact,
    Event,
    EventStatus,
    Task,
    TaskStatus,
    Template,
    TemplateTask,
)
from event_planner.sqlite_repository import SQLiteEventRepository


@pytest.fixture
def repo():
    """Provides an in-memory SQLite repository with foreign keys enabled."""
    repository = SQLiteEventRepository(":memory:")
    yield repository
    repository.close()


def test_foreign_keys_pramga_is_enabled(repo):
    cursor = repo.conn.cursor()
    cursor.execute("PRAGMA foreign_keys;")
    row = cursor.fetchone()
    assert row[0] == 1


def test_save_and_get_template(repo):
    template = Template(
        id="tmpl-corp-1",
        name="Corporate Summit",
        default_tasks=[
            TemplateTask(
                template_task_id="tt-1",
                title="Secure Keynote Speaker",
                relative_days=-120,
                vendor_category="speaker",
            ),
            TemplateTask(
                template_task_id="tt-2",
                title="Publish Agenda",
                relative_days=-60,
                depends_on=["tt-1"],
            ),
        ],
    )
    repo.save_template(template)

    fetched = repo.get_template("tmpl-corp-1")
    assert fetched is not None
    assert fetched.id == "tmpl-corp-1"
    assert fetched.name == "Corporate Summit"
    assert len(fetched.default_tasks) == 2
    assert fetched.default_tasks[1].depends_on == ["tt-1"]


def test_get_nonexistent_template(repo):
    assert repo.get_template("does-not-exist") is None


def test_save_event_bundle_atomic_commit(repo):
    event = Event(
        id="evt-summit-2027",
        name="Global AI Summit",
        date=date(2027, 10, 15),
        status=EventStatus.CONFIRMED,
        budget=Decimal("75000.00"),
    )
    t1 = Task(
        id="task-1",
        event_id="evt-summit-2027",
        title="Reserve Convention Center",
        due_date=date(2027, 4, 1),
        status=TaskStatus.DONE,
        vendor_category="venue",
    )
    t2 = Task(
        id="task-2",
        event_id="evt-summit-2027",
        title="Order Badges",
        due_date=date(2027, 9, 1),
        status=TaskStatus.TODO,
        depends_on=["task-1"],
        vendor_category="printing",
    )
    contact = Contact(
        id="cnt-1",
        event_id="evt-summit-2027",
        name="Alice Smith",
        email="alice@summit.org",
        role="Lead Organizer",
    )

    repo.save_event_bundle(event, [t1, t2], [contact])

    fetched_event = repo.get_event("evt-summit-2027")
    assert fetched_event is not None
    assert fetched_event.name == "Global AI Summit"
    assert fetched_event.budget == Decimal("75000.00")

    tasks = repo.get_tasks_for_event("evt-summit-2027")
    assert len(tasks) == 2
    fetched_t1 = next(t for t in tasks if t.id == "task-1")
    fetched_t2 = next(t for t in tasks if t.id == "task-2")
    assert fetched_t1.status == TaskStatus.DONE
    assert fetched_t2.depends_on == ["task-1"]

    contacts = repo.get_contacts_for_event("evt-summit-2027")
    assert len(contacts) == 1
    assert contacts[0].name == "Alice Smith"


def test_save_event_bundle_rollback_on_failure(repo):
    event = Event(
        id="evt-fail-1",
        name="Rollback Event",
        date=date(2027, 5, 1),
        budget=Decimal("1000.00"),
    )
    # t2 has mismatched event_id
    t1 = Task(id="t-ok", event_id="evt-fail-1", title="OK Task", due_date=date(2027, 4, 1))
    t2 = Task(id="t-bad", event_id="different-evt-id", title="Bad Task", due_date=date(2027, 4, 2))

    with pytest.raises(ValueError, match="expected 'evt-fail-1'"):
        repo.save_event_bundle(event, [t1, t2])

    # Assert nothing was written (atomic rollback)
    assert repo.get_event("evt-fail-1") is None
    assert repo.get_tasks_for_event("evt-fail-1") == []


def test_cascade_delete_event(repo):
    event = Event(
        id="evt-del",
        name="Deletable Event",
        date=date(2027, 8, 1),
        budget=Decimal("500.00"),
    )
    t1 = Task(id="t-del-1", event_id="evt-del", title="T1", due_date=date(2027, 7, 1))
    t2 = Task(id="t-del-2", event_id="evt-del", title="T2", due_date=date(2027, 7, 15), depends_on=["t-del-1"])
    contact = Contact(id="c-del", event_id="evt-del", name="Bob", email="bob@test.com", role="helper")

    repo.save_event_bundle(event, [t1, t2], [contact])
    assert repo.get_event("evt-del") is not None

    deleted = repo.delete_event("evt-del")
    assert deleted is True

    # Check cascading deletes across all tables
    assert repo.get_event("evt-del") is None
    assert repo.get_tasks_for_event("evt-del") == []
    assert repo.get_contacts_for_event("evt-del") == []
    assert repo.get_task("t-del-1") is None
    assert repo.get_task("t-del-2") is None

    # Check join table cleaned up
    cur = repo.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM task_dependencies WHERE task_id = 't-del-2';")
    assert cur.fetchone()[0] == 0


def test_save_and_update_single_task(repo):
    event = Event(
        id="evt-task-edit",
        name="Task Edit Test",
        date=date(2027, 1, 1),
        budget=Decimal("100.00"),
    )
    t1 = Task(id="t-edit-1", event_id="evt-task-edit", title="Initial Title", due_date=date(2026, 12, 1))
    t2 = Task(id="t-edit-2", event_id="evt-task-edit", title="Second Task", due_date=date(2026, 12, 15))
    repo.save_event_bundle(event, [t1, t2])

    # Update t2 to depend on t1 and change status
    updated_t2 = Task(
        id="t-edit-2",
        event_id="evt-task-edit",
        title="Second Task (Updated)",
        due_date=date(2026, 12, 20),
        status=TaskStatus.IN_PROGRESS,
        depends_on=["t-edit-1"],
    )
    repo.save_task(updated_t2)

    fetched = repo.get_task("t-edit-2")
    assert fetched is not None
    assert fetched.title == "Second Task (Updated)"
    assert fetched.status == TaskStatus.IN_PROGRESS
    assert fetched.depends_on == ["t-edit-1"]


def test_task_extended_fields_persistence(repo):
    event = Event(
        id="evt-ext",
        name="Extended Fields Event",
        date=date(2027, 9, 20),
        budget=Decimal("25000.00"),
    )
    t = Task(
        id="t-ext-1",
        event_id="evt-ext",
        title="Florist Consultation",
        due_date=date(2027, 5, 10),
        status=TaskStatus.IN_PROGRESS,
        assignee="Jordan",
        notes="Mood board: https://pinterest.com/wedding-florals",
        estimated_cost=Decimal("2200.00"),
        actual_cost=Decimal("2050.00"),
        paid_amount=Decimal("1000.00"),
        checklist=[
            ChecklistItem(id="chk-1", text="Select centerpiece flowers", completed=True),
            ChecklistItem(id="chk-2", text="Confirm delivery time", completed=False),
        ],
    )
    repo.save_event_bundle(event, [t])

    # Test get_task
    fetched = repo.get_task("t-ext-1")
    assert fetched is not None
    assert fetched.assignee == "Jordan"
    assert "https://pinterest.com" in fetched.notes
    assert fetched.estimated_cost == Decimal("2200.00")
    assert fetched.actual_cost == Decimal("2050.00")
    assert fetched.paid_amount == Decimal("1000.00")
    assert len(fetched.checklist) == 2
    assert fetched.checklist[0].text == "Select centerpiece flowers"
    assert fetched.checklist[0].completed is True
    assert fetched.checklist[1].completed is False

    # Test get_tasks_for_event
    all_tasks = repo.get_tasks_for_event("evt-ext")
    assert len(all_tasks) == 1
    assert all_tasks[0].assignee == "Jordan"
    assert len(all_tasks[0].checklist) == 2

    # Test update via save_task
    fetched.checklist[1].completed = True
    fetched.paid_amount = Decimal("2050.00")
    fetched.status = TaskStatus.DONE
    repo.save_task(fetched)

    updated = repo.get_task("t-ext-1")
    assert updated.status == TaskStatus.DONE
    assert updated.paid_amount == Decimal("2050.00")
    assert updated.checklist[1].completed is True


def test_sqlite_schema_auto_migration(tmp_path):
    db_file = str(tmp_path / "legacy.db")
    # Simulate legacy table without new columns
    conn = sqlite3.connect(db_file)
    conn.execute("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL,
            vendor_category TEXT
        );
    """)
    conn.execute("""
        INSERT INTO tasks (id, event_id, title, due_date, status, vendor_category)
        VALUES ('t-legacy', 'evt-1', 'Legacy Task', '2027-01-01', 'todo', 'catering');
    """)
    conn.commit()
    conn.close()

    # Now open with SQLiteEventRepository, which should run migrations safely
    repo = SQLiteEventRepository(db_file)
    t = repo.get_task("t-legacy")
    assert t is not None
    assert t.title == "Legacy Task"
    assert t.assignee == "Both"
    assert t.notes == ""
    assert t.estimated_cost == Decimal("0.00")
    assert t.checklist == []
    repo.close()

