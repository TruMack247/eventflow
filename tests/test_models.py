"""Tests for domain models."""
from datetime import date, datetime
from decimal import Decimal
import pytest
from pydantic import ValidationError

from event_planner.models import (
    Event,
    EventStatus,
    Task,
    TaskStatus,
    Contact,
    Template,
    TemplateTask,
)


def test_create_valid_event():
    event = Event(
        id="evt-1",
        name="Annual Gala",
        date=date(2027, 6, 15),
        status=EventStatus.DRAFT,
        budget=Decimal("15000.00"),
    )
    assert event.id == "evt-1"
    assert event.name == "Annual Gala"
    assert event.budget == Decimal("15000.00")
    assert event.status == EventStatus.DRAFT
    assert event.template_id is None


def test_event_invalid_budget():
    with pytest.raises(ValidationError):
        Event(
            id="evt-2",
            name="Negative Budget Party",
            date=date(2027, 1, 1),
            budget=Decimal("-10.00"),
        )


def test_event_empty_name():
    with pytest.raises(ValidationError):
        Event(
            id="evt-3",
            name="   ",
            date=date(2027, 1, 1),
            budget=Decimal("100.00"),
        )


def test_create_valid_task():
    task = Task(
        id="tsk-1",
        event_id="evt-1",
        title="Book Catering",
        due_date=date(2027, 3, 1),
        status=TaskStatus.TODO,
        depends_on=["tsk-0"],
        vendor_category="catering",
    )
    assert task.title == "Book Catering"
    assert task.vendor_category == "catering"
    assert task.status == TaskStatus.TODO
    assert task.depends_on == ["tsk-0"]


def test_task_invalid_empty_title():
    with pytest.raises(ValidationError):
        Task(
            id="tsk-2",
            event_id="evt-1",
            title="",
            due_date=date(2027, 3, 1),
        )


def test_create_valid_contact():
    contact = Contact(
        id="cnt-1",
        event_id="evt-1",
        name="John Doe",
        email="john@example.com",
        role="photographer",
    )
    assert contact.name == "John Doe"
    assert contact.email == "john@example.com"
    assert contact.role == "photographer"


def test_contact_invalid_email():
    with pytest.raises(ValidationError):
        Contact(
            id="cnt-2",
            event_id="evt-1",
            name="Jane Doe",
            email="not-an-email",
            role="planner",
        )


def test_create_template_with_tasks():
    template = Template(
        id="tmpl-1",
        name="General Conference",
        default_tasks=[
            TemplateTask(
                template_task_id="t-1",
                title="Secure Venue",
                relative_days=-180,
                vendor_category="venue",
            ),
            TemplateTask(
                template_task_id="t-2",
                title="Send Invitations",
                relative_days=-90,
                depends_on=["t-1"],
            ),
        ],
    )
    assert len(template.default_tasks) == 2
    assert template.default_tasks[1].depends_on == ["t-1"]
