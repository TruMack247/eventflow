"""
EventFlow Web Server & API Handler.
Serves the Stitch UI layout with live engine persistence and workflow operations.
Uses Python standard library http.server (no external web framework required).
"""
import json
import mimetypes
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from event_planner.models import Event, EventStatus, Task, TaskStatus, Contact, ChecklistItem
from event_planner.templates import get_wedding_template
from event_planner.engine import instantiate_event_from_template
from event_planner.sqlite_repository import SQLiteEventRepository
from event_planner.workflow import (
    transition_task_status,
    get_actionable_tasks,
    reschedule_event,
    shift_task_due_date,
    BlockedTaskError,
    DependentTasksBlockReopenError,
    WorkflowError,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DB_PATH = Path(os.environ.get("DATABASE_PATH", "event_planner.db"))
APP_PASSCODE = os.environ.get("APP_PASSCODE", "").strip()


def decimal_and_date_serializer(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, TaskStatus):
        return obj.value
    if isinstance(obj, EventStatus):
        return obj.value
    raise TypeError(f"Type {type(obj)} not serializable")


class EventFlowAPIHandler(BaseHTTPRequestHandler):
    repo: SQLiteEventRepository = None

    @classmethod
    def set_repo(cls, repository: SQLiteEventRepository):
        cls.repo = repository

    def send_json(self, status_code: int, data: Any):
        body = json.dumps(data, default=decimal_and_date_serializer).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def check_auth(self) -> bool:
        """Validates optional shared wedding passcode when APP_PASSCODE is set."""
        if not APP_PASSCODE:
            return True
        header_passcode = self.headers.get("X-App-Passcode", "")
        return header_passcode == APP_PASSCODE

    def send_unauthorized(self):
        self.send_json(401, {"error": "Unauthorized. Please provide valid shared wedding passcode."})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/auth/status":
            return self.send_json(200, {
                "auth_required": bool(APP_PASSCODE),
                "authenticated": self.check_auth() if APP_PASSCODE else True,
            })

        if path.startswith("/api/"):
            if not self.check_auth():
                return self.send_unauthorized()

        # API Endpoints
        if path == "/api/events":
            cursor = self.repo.conn.execute("SELECT id FROM events ORDER BY date ASC;")
            event_ids = [row["id"] for row in cursor.fetchall()]
            events = [self.repo.get_event(eid) for eid in event_ids if self.repo.get_event(eid)]
            return self.send_json(200, [e.model_dump() for e in events])

        elif path.startswith("/api/events/") and path.endswith("/overview"):
            event_id = path.split("/")[3]
            event = self.repo.get_event(event_id)
            if not event:
                return self.send_json(404, {"error": "Event not found"})

            tasks = self.repo.get_tasks_for_event(event_id)
            contacts = self.repo.get_contacts_for_event(event_id)
            actionable = get_actionable_tasks(tasks)

            # Categorize tasks into ready, in_progress, blocked, done
            task_map = {t.id: t for t in tasks}
            ready_ids = {t.id for t in actionable}

            categorized_tasks = []
            for t in tasks:
                t_dict = t.model_dump()
                if t.status == TaskStatus.DONE:
                    state_label = "done"
                elif t.status == TaskStatus.IN_PROGRESS:
                    state_label = "in_progress"
                elif t.id in ready_ids:
                    state_label = "ready"
                else:
                    state_label = "blocked"

                unmet_deps = [
                    dep_id for dep_id in t.depends_on
                    if not task_map.get(dep_id) or task_map[dep_id].status != TaskStatus.DONE
                ]
                t_dict["workflow_state"] = state_label
                t_dict["unmet_dependencies"] = unmet_deps
                categorized_tasks.append(t_dict)

            # Quick stats calculation
            now_date = date.today()
            ev_date = event.date if isinstance(event.date, date) else event.date.date()
            days_remain = (ev_date - now_date).days

            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.DONE)
            progress_pct = round((completed_tasks / total_tasks * 100), 1) if total_tasks else 0.0

            total_estimated = sum(t.estimated_cost for t in tasks)
            total_actual = sum(t.actual_cost for t in tasks)
            total_paid = sum(t.paid_amount for t in tasks)
            remaining_balance = total_actual - total_paid

            p1 = getattr(event, "partner_1_name", "Alex") or "Alex"
            p2 = getattr(event, "partner_2_name", "Jordan") or "Jordan"
            assignee_counts = {
                p1: sum(1 for t in tasks if t.assignee == p1),
                p2: sum(1 for t in tasks if t.assignee == p2),
                "Both": sum(1 for t in tasks if t.assignee not in (p1, p2) or t.assignee in ("Both", "")),
            }

            overview_data = {
                "event": event.model_dump(),
                "partner_names": [p1, p2],
                "days_remaining": days_remain,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "progress_percentage": progress_pct,
                "budget_metrics": {
                    "total_budget": float(event.budget),
                    "total_estimated": float(total_estimated),
                    "total_actual": float(total_actual),
                    "total_paid": float(total_paid),
                    "remaining_balance": float(remaining_balance),
                    "budget_variance": float(event.budget - total_actual),
                },
                "assignee_counts": assignee_counts,
                "tasks": categorized_tasks,
                "actionable_tasks": [t.model_dump() for t in actionable],
                "contacts": [c.model_dump() for c in contacts],
            }
            return self.send_json(200, overview_data)

        elif path == "/api/templates":
            cursor = self.repo.conn.execute("SELECT id FROM templates;")
            tmpl_ids = [row["id"] for row in cursor.fetchall()]
            tmpls = [self.repo.get_template(tid) for tid in tmpl_ids]
            return self.send_json(200, [t.model_dump() for t in tmpls if t])

        # Serve static files from Stitch layouts
        self.serve_static_file(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        post_data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

        if path == "/api/auth/verify":
            candidate = post_data.get("passcode", "").strip()
            if not APP_PASSCODE or candidate == APP_PASSCODE:
                return self.send_json(200, {"success": True, "authenticated": True})
            return self.send_json(401, {"success": False, "error": "Invalid passcode"})

        if path.startswith("/api/"):
            if not self.check_auth():
                return self.send_unauthorized()

        if path == "/api/tasks/transition":
            task_id = post_data.get("task_id")
            new_status_str = post_data.get("status")
            force = bool(post_data.get("force", False))

            task = self.repo.get_task(task_id)
            if not task:
                return self.send_json(404, {"error": f"Task '{task_id}' not found"})

            all_tasks = self.repo.get_tasks_for_event(task.event_id)
            # Find the exact task instance inside all_tasks to mutate in-place
            target_task_in_list = next((t for t in all_tasks if t.id == task_id), None)
            if not target_task_in_list:
                target_task_in_list = task
                all_tasks.append(target_task_in_list)

            try:
                new_status = TaskStatus(new_status_str)
                updated_task = transition_task_status(target_task_in_list, new_status, all_tasks, force=force)
                # Persist target task and all affected tasks
                for t in all_tasks:
                    self.repo.save_task(t)

                return self.send_json(200, {
                    "success": True,
                    "task": updated_task.model_dump(),
                    "all_tasks": [t.model_dump() for t in all_tasks],
                })
            except (BlockedTaskError, DependentTasksBlockReopenError, ValueError) as err:
                return self.send_json(400, {"error": str(err)})

        elif path == "/api/tasks/shift_due_date":
            task_id = post_data.get("task_id")
            new_due_date_str = post_data.get("new_due_date")
            cascade = bool(post_data.get("cascade", True))

            task = self.repo.get_task(task_id)
            if not task:
                return self.send_json(404, {"error": f"Task '{task_id}' not found"})

            all_tasks = self.repo.get_tasks_for_event(task.event_id)
            event = self.repo.get_event(task.event_id)
            new_due_date = date.fromisoformat(new_due_date_str)

            try:
                updated_tasks = shift_task_due_date(
                    all_tasks,
                    task_id=task_id,
                    new_due_date=new_due_date,
                    cascade=cascade,
                    max_boundary_date=event.date if event else None,
                )
                for t in updated_tasks:
                    self.repo.save_task(t)

                return self.send_json(200, {
                    "success": True,
                    "tasks": [t.model_dump() for t in updated_tasks],
                })
            except WorkflowError as err:
                return self.send_json(400, {"error": str(err)})

        elif path == "/api/events" and length:
            name = post_data.get("name", "New Event")
            target_date_str = post_data.get("date")
            budget_val = post_data.get("budget", 25000.0)
            p1_name = (post_data.get("partner_1_name") or "Alex").strip()
            p2_name = (post_data.get("partner_2_name") or "Jordan").strip()
            template_id = post_data.get("template_id", "wedding_standard_v1")

            new_id = f"EVT-{int(datetime.now().timestamp()) % 100000:04d}"
            target_date = date.fromisoformat(target_date_str) if target_date_str else (date.today() + timedelta(days=180))

            template = self.repo.get_template(template_id)
            new_event = Event(
                id=new_id,
                name=name,
                date=target_date,
                status=EventStatus.CONFIRMED,
                budget=Decimal(str(budget_val)),
                partner_1_name=p1_name,
                partner_2_name=p2_name,
                template_id=template_id,
            )

            if template:
                tasks = instantiate_event_from_template(new_event, template)
                # Populate clean actionable steps without dummy financial amounts or fake links
                create_clean_wedding_checklists(tasks, p1_name, p2_name)
            else:
                tasks = []

            # Add default lead planner contact
            contacts = [
                Contact(
                    id=f"cnt-{new_id}-1",
                    event_id=new_id,
                    name=f"{p1_name} & {p2_name}",
                    email=f"wedding@{p1_name.lower()}{p2_name.lower()}.internal",
                    role="Host Couple",
                )
            ]

            self.repo.save_event_bundle(new_event, tasks, contacts)
            return self.send_json(201, {
                "success": True,
                "event": new_event.model_dump(),
                "tasks_count": len(tasks),
            })

        elif path.startswith("/api/events/") and path.endswith("/settings"):
            event_id = path.split("/")[3]
            event = self.repo.get_event(event_id)
            if not event:
                return self.send_json(404, {"error": "Event not found"})

            old_p1 = event.partner_1_name
            old_p2 = event.partner_2_name

            if "name" in post_data and post_data["name"].strip():
                event.name = post_data["name"].strip()
            if "budget" in post_data:
                event.budget = Decimal(str(post_data["budget"]))
            if "date" in post_data and post_data["date"].strip():
                event.date = date.fromisoformat(post_data["date"].strip())
            if "partner_1_name" in post_data and post_data["partner_1_name"].strip():
                event.partner_1_name = post_data["partner_1_name"].strip()
            if "partner_2_name" in post_data and post_data["partner_2_name"].strip():
                event.partner_2_name = post_data["partner_2_name"].strip()

            tasks = self.repo.get_tasks_for_event(event_id)
            # Reassign tasks from old names to new names if changed
            for t in tasks:
                if t.assignee == old_p1:
                    t.assignee = event.partner_1_name
                    self.repo.save_task(t)
                elif t.assignee == old_p2:
                    t.assignee = event.partner_2_name
                    self.repo.save_task(t)

            contacts = self.repo.get_contacts_for_event(event_id)
            self.repo.save_event_bundle(event, tasks, contacts)
            return self.send_json(200, {"success": True, "event": event.model_dump()})

        elif path.startswith("/api/events/") and path.endswith("/delete"):
            event_id = path.split("/")[3]
            deleted = self.repo.delete_event(event_id)
            return self.send_json(200, {"success": deleted})

        elif path.startswith("/api/events/") and path.endswith("/reschedule"):
            event_id = path.split("/")[3]
            new_date_str = post_data.get("new_date")
            event = self.repo.get_event(event_id)
            if not event:
                return self.send_json(404, {"error": "Event not found"})

            tasks = self.repo.get_tasks_for_event(event_id)
            new_date = date.fromisoformat(new_date_str)
            updated_event, updated_tasks = reschedule_event(event, tasks, new_date)

            # Persist bundle
            contacts = self.repo.get_contacts_for_event(event_id)
            self.repo.save_event_bundle(updated_event, updated_tasks, contacts)
            return self.send_json(200, {
                "success": True,
                "event": updated_event.model_dump(),
                "tasks": [t.model_dump() for t in updated_tasks],
            })

        elif path == "/api/tasks/checklist/toggle":
            task_id = post_data.get("task_id")
            item_id = post_data.get("item_id")
            forced_state = post_data.get("completed")

            task = self.repo.get_task(task_id)
            if not task:
                return self.send_json(404, {"error": f"Task '{task_id}' not found"})

            found = False
            for item in task.checklist:
                if item.id == item_id:
                    item.completed = (not item.completed) if forced_state is None else bool(forced_state)
                    found = True
                    break

            if not found:
                return self.send_json(404, {"error": f"Checklist item '{item_id}' not found"})

            self.repo.save_task(task)
            return self.send_json(200, {"success": True, "task": task.model_dump()})

        elif path == "/api/tasks/checklist/add":
            task_id = post_data.get("task_id")
            text = (post_data.get("text") or "").strip()
            if not text:
                return self.send_json(400, {"error": "Checklist item text cannot be empty"})

            task = self.repo.get_task(task_id)
            if not task:
                return self.send_json(404, {"error": f"Task '{task_id}' not found"})

            new_item_id = f"chk-{uuid.uuid4().hex[:8]}"
            new_item = ChecklistItem(id=new_item_id, text=text, completed=False)
            task.checklist.append(new_item)

            self.repo.save_task(task)
            return self.send_json(200, {"success": True, "task": task.model_dump(), "item": new_item.model_dump()})

        elif path == "/api/tasks/update_details":
            task_id = post_data.get("task_id")
            task = self.repo.get_task(task_id)
            if not task:
                return self.send_json(404, {"error": f"Task '{task_id}' not found"})

            if "assignee" in post_data:
                task.assignee = str(post_data["assignee"])
            if "notes" in post_data:
                task.notes = str(post_data["notes"])
            if "estimated_cost" in post_data:
                task.estimated_cost = Decimal(str(post_data["estimated_cost"] or 0.0))
            if "actual_cost" in post_data:
                task.actual_cost = Decimal(str(post_data["actual_cost"] or 0.0))
            if "paid_amount" in post_data:
                task.paid_amount = Decimal(str(post_data["paid_amount"] or 0.0))
            if "title" in post_data and post_data["title"].strip():
                task.title = post_data["title"].strip()

            self.repo.save_task(task)
            return self.send_json(200, {"success": True, "task": task.model_dump()})

        return self.send_json(404, {"error": "Endpoint not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            if not self.check_auth():
                return self.send_unauthorized()
        if path.startswith("/api/events/"):
            event_id = path.split("/")[3]
            deleted = self.repo.delete_event(event_id)
            return self.send_json(200, {"success": deleted})
        return self.send_json(404, {"error": "Endpoint not found"})

    def serve_static_file(self, req_path: str):
        if req_path in ("", "/"):
            req_path = "/index.html"

        # Sanitize path
        rel_path = req_path.lstrip("/").replace("/", os.sep)
        full_path = (STATIC_DIR / rel_path).resolve()

        if not str(full_path).startswith(str(STATIC_DIR.resolve())):
            self.send_error(403, "Access denied")
            return

        if not full_path.exists() or full_path.is_dir():
            # Fallback to index.html if it exists
            index_path = STATIC_DIR / "index.html"
            if index_path.exists():
                full_path = index_path
            else:
                self.send_error(404, "File not found")
                return

        mime_type, _ = mimetypes.guess_type(str(full_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {str(e)}")


def create_clean_wedding_checklists(tasks: List[Task], p1: str, p2: str) -> None:
    for t in tasks:
        low = t.title.lower()
        t.estimated_cost = Decimal("0.00")
        t.actual_cost = Decimal("0.00")
        t.paid_amount = Decimal("0.00")
        t.notes = ""
        if "budget" in low:
            t.assignee = "Both"
            t.checklist = [
                ChecklistItem(id="chk-b1", text="Draft initial guest count", completed=False),
                ChecklistItem(id="chk-b2", text="Agree on total budget ceiling", completed=False),
            ]
        elif "venue" in low:
            t.assignee = p1
            t.checklist = [
                ChecklistItem(id="chk-v1", text="Tour top 3 potential venues", completed=False),
                ChecklistItem(id="chk-v2", text="Review catering & noise policies", completed=False),
                ChecklistItem(id="chk-v3", text="Sign contract & submit deposit", completed=False),
            ]
        elif "photo" in low:
            t.assignee = p2
            t.checklist = [
                ChecklistItem(id="chk-p1", text="Review photographer portfolios", completed=False),
                ChecklistItem(id="chk-p2", text="Schedule video interview", completed=False),
                ChecklistItem(id="chk-p3", text="Confirm shot list & family photos", completed=False),
            ]
        elif "catering" in low:
            t.assignee = p1
            t.checklist = [
                ChecklistItem(id="chk-c1", text="Attend menu tasting", completed=False),
                ChecklistItem(id="chk-c2", text="Finalize bar package & drinks", completed=False),
            ]
        elif "invitation" in low:
            t.assignee = p2
            t.checklist = [
                ChecklistItem(id="chk-i1", text="Collect mailing addresses", completed=False),
                ChecklistItem(id="chk-i2", text="Order invitation suite", completed=False),
                ChecklistItem(id="chk-i3", text="Mail invites & track RSVPs", completed=False),
            ]
        elif "seating" in low:
            t.assignee = "Both"
            t.checklist = [
                ChecklistItem(id="chk-s1", text="Confirm final RSVP count", completed=False),
                ChecklistItem(id="chk-s2", text="Draft table seating arrangement", completed=False),
            ]
        elif "rehearsal" in low:
            t.assignee = "Both"
            t.checklist = [
                ChecklistItem(id="chk-r1", text="Confirm officiant & wedding party", completed=False),
                ChecklistItem(id="chk-r2", text="Schedule rehearsal dinner", completed=False),
            ]


def populate_demo_task_details(tasks: List[Task]) -> None:
    for t in tasks:
        low = t.title.lower()
        if "budget" in low:
            t.assignee = "Both"
            t.estimated_cost = Decimal("0.00")
            t.actual_cost = Decimal("0.00")
            t.paid_amount = Decimal("0.00")
            t.notes = "Shared wedding budget spreadsheet: https://docs.google.com/spreadsheets/d/wedding-budget"
            if not t.checklist:
                t.checklist = [
                    ChecklistItem(id="chk-b1", text="Draft initial guest count", completed=True),
                    ChecklistItem(id="chk-b2", text="Set $50,000 maximum budget ceiling", completed=True),
                ]
        elif "venue" in low:
            t.assignee = "Alex"
            t.estimated_cost = Decimal("18000.00")
            t.actual_cost = Decimal("17500.00")
            t.paid_amount = Decimal("5000.00")
            t.notes = "Grand Palace Ballroom booked. Contact: Marcus Sterling (marcus@grandpalacevenue.com). Portal: https://grandpalacevenue.com/client-hub"
            if not t.checklist:
                t.checklist = [
                    ChecklistItem(id="chk-v1", text="Tour top 3 downtown venues", completed=True),
                    ChecklistItem(id="chk-v2", text="Review insurance & sound ordinances", completed=True),
                    ChecklistItem(id="chk-v3", text="Sign contract & send deposit", completed=True),
                    ChecklistItem(id="chk-v4", text="Final walkthrough & layout approval", completed=False),
                ]
        elif "photo" in low:
            t.assignee = "Jordan"
            t.estimated_cost = Decimal("4500.00")
            t.actual_cost = Decimal("4200.00")
            t.paid_amount = Decimal("1500.00")
            t.notes = "Lumiere Studios portfolio: https://lumierestudios.co/weddings. 8-hour photography package + drone coverage."
            if not t.checklist:
                t.checklist = [
                    ChecklistItem(id="chk-p1", text="Review photographer portfolios", completed=True),
                    ChecklistItem(id="chk-p2", text="Introductory video call with studio", completed=True),
                    ChecklistItem(id="chk-p3", text="Confirm shot list & family combinations", completed=False),
                ]
        elif "catering" in low:
            t.assignee = "Alex"
            t.estimated_cost = Decimal("12000.00")
            t.actual_cost = Decimal("11500.00")
            t.paid_amount = Decimal("3000.00")
            t.notes = "Artisan Food SF contract signed. Contact: Jules Reed (jules@artisanfoodsf.com). Menu PDF: https://artisanfoodsf.com/proposals/evt-9284.pdf"
            if not t.checklist:
                t.checklist = [
                    ChecklistItem(id="chk-c1", text="Collect guest dietary restrictions", completed=True),
                    ChecklistItem(id="chk-c2", text="Chef tasting session (3 courses)", completed=False),
                    ChecklistItem(id="chk-c3", text="Finalize bar package & champagne toast", completed=False),
                ]
        elif "invitation" in low:
            t.assignee = "Jordan"
            t.estimated_cost = Decimal("1200.00")
            t.actual_cost = Decimal("1100.00")
            t.paid_amount = Decimal("500.00")
            t.notes = "Minted suite design: https://minted.com/design/782391. Proofs approved."
            if not t.checklist:
                t.checklist = [
                    ChecklistItem(id="chk-i1", text="Gather physical mailing addresses", completed=True),
                    ChecklistItem(id="chk-i2", text="Proofread text and RSVP deadlines", completed=True),
                    ChecklistItem(id="chk-i3", text="Post and mail invitations", completed=False),
                ]
        elif "seating" in low:
            t.assignee = "Both"
            t.estimated_cost = Decimal("300.00")
            t.actual_cost = Decimal("250.00")
            t.paid_amount = Decimal("0.00")
            t.notes = "Floorplan editor: https://allseated.com/floorplans/evt-9284"
            if not t.checklist:
                t.checklist = [
                    ChecklistItem(id="chk-s1", text="Confirm total table count with venue", completed=False),
                    ChecklistItem(id="chk-s2", text="Assign VIP tables & wedding party", completed=False),
                ]
        elif "rehearsal" in low:
            t.assignee = "Both"
            t.estimated_cost = Decimal("800.00")
            t.actual_cost = Decimal("750.00")
            t.paid_amount = Decimal("0.00")
            t.notes = "Rehearsal 4:30 PM Friday before wedding. Rehearsal dinner at Luigi's Trattoria."
            if not t.checklist:
                t.checklist = [
                    ChecklistItem(id="chk-r1", text="Confirm officiant schedule", completed=False),
                    ChecklistItem(id="chk-r2", text="Share rehearsal dinner timeline with party", completed=False),
                ]


def init_demo_database(repo: SQLiteEventRepository) -> str:
    """Initializes standard wedding template and demo event if empty."""
    wedding_tmpl = get_wedding_template()
    repo.save_template(wedding_tmpl)

    cursor = repo.conn.execute("SELECT COUNT(*) FROM events;")
    if cursor.fetchone()[0] == 0:
        event = Event(
            id="EVT-9284",
            name="Sarah & Michael's Wedding",
            date=date(2027, 5, 24),
            status=EventStatus.CONFIRMED,
            budget=Decimal("50000.00"),
            template_id=wedding_tmpl.id,
        )
        tasks = instantiate_event_from_template(event, wedding_tmpl)

        # Set budget task to DONE to have realistic initial actionable state
        budget_task = next(t for t in tasks if "budget" in t.title.lower())
        budget_task.status = TaskStatus.DONE

        populate_demo_task_details(tasks)

        contacts = [
            Contact(
                id="cnt-1",
                event_id="EVT-9284",
                name="Elena Vance",
                email="elena.vance@eventflow.internal",
                role="Lead Coordinator",
            ),
            Contact(
                id="cnt-2",
                event_id="EVT-9284",
                name="Marcus Sterling",
                email="marcus@grandpalacevenue.com",
                role="Venue Director",
            ),
            Contact(
                id="cnt-3",
                event_id="EVT-9284",
                name="Julianne Reed",
                email="jules@artisanfoodsf.com",
                role="Executive Caterer",
            ),
        ]
        repo.save_event_bundle(event, tasks, contacts)
        return event.id
    else:
        cursor.execute("SELECT id FROM events LIMIT 1;")
        first_event_id = cursor.fetchone()["id"]
        # Upgrade any existing tasks without checklist or assignee
        existing_tasks = repo.get_tasks_for_event(first_event_id)
        if any(not t.checklist for t in existing_tasks):
            populate_demo_task_details(existing_tasks)
            for t in existing_tasks:
                repo.save_task(t)
        return first_event_id


def run_server():
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")

    # Ensure parent directory for database exists (especially on cloud volumes like /data)
    if DB_PATH.parent:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    repo = SQLiteEventRepository(str(DB_PATH))
    init_demo_database(repo)
    EventFlowAPIHandler.set_repo(repo)
    server = HTTPServer((host, port), EventFlowAPIHandler)
    print(f"EventFlow UI server running at http://{host}:{port} (DB: {DB_PATH}, Auth: {'Required' if APP_PASSCODE else 'Open'})")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
