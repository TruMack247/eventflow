"""Tests for server HTTP API endpoints."""
import json
import threading
from datetime import date
from decimal import Decimal
from http.client import HTTPConnection
from http.server import HTTPServer

import pytest
from event_planner.models import Event, EventStatus, Task, TaskStatus, ChecklistItem
from event_planner.sqlite_repository import SQLiteEventRepository
from event_planner.web.server import EventFlowAPIHandler


@pytest.fixture
def test_server():
    repo = SQLiteEventRepository(":memory:")
    # Seed test event and task
    event = Event(
        id="EVT-TEST",
        name="Test Wedding",
        date=date(2027, 8, 1),
        status=EventStatus.CONFIRMED,
        budget=Decimal("30000.00"),
    )
    task = Task(
        id="TSK-TEST-1",
        event_id="EVT-TEST",
        title="Test Task",
        due_date=date(2027, 6, 1),
        status=TaskStatus.TODO,
        assignee="Alex",
        notes="Important notes",
        estimated_cost=Decimal("2000.00"),
        actual_cost=Decimal("1800.00"),
        paid_amount=Decimal("600.00"),
        checklist=[
            ChecklistItem(id="chk-1", text="Step 1", completed=False),
            ChecklistItem(id="chk-2", text="Step 2", completed=True),
        ],
    )
    repo.save_event_bundle(event, [task])

    EventFlowAPIHandler.set_repo(repo)
    server = HTTPServer(("127.0.0.1", 0), EventFlowAPIHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield port, repo

    server.shutdown()
    server.server_close()
    repo.close()


def test_overview_budget_metrics_and_assignees(test_server):
    port, _ = test_server
    conn = HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/events/EVT-TEST/overview")
    resp = conn.getresponse()
    assert resp.status == 200
    data = json.loads(resp.read().decode("utf-8"))

    assert "budget_metrics" in data
    bm = data["budget_metrics"]
    assert bm["total_budget"] == 30000.0
    assert bm["total_estimated"] == 2000.0
    assert bm["total_actual"] == 1800.0
    assert bm["total_paid"] == 600.0
    assert bm["remaining_balance"] == 1200.0
    assert bm["budget_variance"] == 28200.0

    assert data["assignee_counts"]["Alex"] == 1
    assert data["assignee_counts"]["Jordan"] == 0
    conn.close()


def test_toggle_checklist_item(test_server):
    port, repo = test_server
    conn = HTTPConnection("127.0.0.1", port)
    payload = json.dumps({"task_id": "TSK-TEST-1", "item_id": "chk-1"}).encode("utf-8")
    conn.request("POST", "/api/tasks/checklist/toggle", body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    assert resp.status == 200
    data = json.loads(resp.read().decode("utf-8"))
    assert data["success"] is True

    # Verify toggled in memory and database
    t = repo.get_task("TSK-TEST-1")
    assert t.checklist[0].completed is True
    conn.close()


def test_add_checklist_item(test_server):
    port, repo = test_server
    conn = HTTPConnection("127.0.0.1", port)
    payload = json.dumps({"task_id": "TSK-TEST-1", "text": "Step 3"}).encode("utf-8")
    conn.request("POST", "/api/tasks/checklist/add", body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    assert resp.status == 200
    data = json.loads(resp.read().decode("utf-8"))
    assert data["success"] is True
    assert data["item"]["text"] == "Step 3"

    t = repo.get_task("TSK-TEST-1")
    assert len(t.checklist) == 3
    assert t.checklist[2].text == "Step 3"
    conn.close()


def test_update_task_details(test_server):
    port, repo = test_server
    conn = HTTPConnection("127.0.0.1", port)
    payload = json.dumps({
        "task_id": "TSK-TEST-1",
        "assignee": "Jordan",
        "notes": "Updated link: https://example.com/contract",
        "estimated_cost": 2500.0,
        "actual_cost": 2400.0,
        "paid_amount": 1000.0,
    }).encode("utf-8")
    conn.request("POST", "/api/tasks/update_details", body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    assert resp.status == 200
    data = json.loads(resp.read().decode("utf-8"))
    assert data["success"] is True
    assert data["task"]["assignee"] == "Jordan"

    t = repo.get_task("TSK-TEST-1")
    assert t.assignee == "Jordan"
    assert "https://example.com/contract" in t.notes
    assert t.actual_cost == Decimal("2400.00")
    assert t.paid_amount == Decimal("1000.00")
    conn.close()
