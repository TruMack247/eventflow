"""Round-trip persistence test proving data survives across closed and reopened connections."""
from datetime import date
from decimal import Decimal
import tempfile
from pathlib import Path
import pytest

from event_planner.models import Event, EventStatus, Task, TaskStatus, Contact
from event_planner.templates import get_wedding_template
from event_planner.engine import instantiate_event_from_template
from event_planner.sqlite_repository import SQLiteEventRepository


def test_round_trip_disk_persistence():
    """
    Ensures that saving an event bundle, template, and tasks to an on-disk SQLite DB file,
    closing the connection, and reopening with a completely fresh repository instance
    faithfully restores all entities, decimal precisions, and reconstructed dependencies.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "test_planner.db")

        # Session 1: Create repository, save wedding template & instantiated event bundle
        repo1 = SQLiteEventRepository(db_path)

        wedding_tmpl = get_wedding_template()
        repo1.save_template(wedding_tmpl)

        wedding_event = Event(
            id="evt-roundtrip-wedding",
            name="Sarah & Michael Wedding",
            date=date(2028, 6, 20),
            status=EventStatus.CONFIRMED,
            budget=Decimal("55000.50"),
            template_id=wedding_tmpl.id,
        )

        tasks = instantiate_event_from_template(wedding_event, wedding_tmpl)

        contact = Contact(
            id="cnt-planner-1",
            event_id="evt-roundtrip-wedding",
            name="Elena Rostova",
            email="elena@luxeweddings.com",
            role="lead_planner",
        )

        repo1.save_event_bundle(wedding_event, tasks, [contact])

        # Explicitly close Session 1
        repo1.close()

        # Session 2: Fresh connection opened to the same DB file
        repo2 = SQLiteEventRepository(db_path)

        # 1. Verify template survival
        restored_tmpl = repo2.get_template(wedding_tmpl.id)
        assert restored_tmpl is not None
        assert restored_tmpl.id == wedding_tmpl.id
        assert restored_tmpl.name == wedding_tmpl.name
        assert len(restored_tmpl.default_tasks) == len(wedding_tmpl.default_tasks)

        # 2. Verify event survival
        restored_event = repo2.get_event("evt-roundtrip-wedding")
        assert restored_event is not None
        assert restored_event.id == "evt-roundtrip-wedding"
        assert restored_event.name == "Sarah & Michael Wedding"
        assert restored_event.status == EventStatus.CONFIRMED
        assert restored_event.budget == Decimal("55000.50")
        assert restored_event.template_id == wedding_tmpl.id

        # 3. Verify tasks and reconstructed dependencies survival
        restored_tasks = repo2.get_tasks_for_event("evt-roundtrip-wedding")
        assert len(restored_tasks) == len(tasks)

        original_tasks_by_id = {t.id: t for t in tasks}
        for rt in restored_tasks:
            orig = original_tasks_by_id[rt.id]
            assert rt.title == orig.title
            assert rt.due_date == orig.due_date
            assert rt.status == orig.status
            assert set(rt.depends_on) == set(orig.depends_on)
            assert rt.vendor_category == orig.vendor_category

        # 4. Verify contact survival
        restored_contacts = repo2.get_contacts_for_event("evt-roundtrip-wedding")
        assert len(restored_contacts) == 1
        assert restored_contacts[0].id == "cnt-planner-1"
        assert restored_contacts[0].name == "Elena Rostova"
        assert restored_contacts[0].email == "elena@luxeweddings.com"

        repo2.close()
