"""
EventFlow Web Server & API Handler.
Serves the Stitch UI layout with live engine persistence and workflow operations.
Uses Python standard library http.server (no external web framework required).
"""
import json
import mimetypes
import os
from datetime import date, datetime
from decimal import Decimal
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from event_planner.models import Event, EventStatus, Task, TaskStatus, Contact
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
DB_PATH = Path("event_planner.db")


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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

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

            overview_data = {
                "event": event.model_dump(),
                "days_remaining": days_remain,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "progress_percentage": progress_pct,
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
                template_id=template_id,
            )

            if template:
                tasks = instantiate_event_from_template(new_event, template)
            else:
                tasks = []

            # Add default lead planner contact
            contacts = [
                Contact(
                    id=f"cnt-{new_id}-1",
                    event_id=new_id,
                    name="Elena Vance",
                    email="elena.vance@eventflow.internal",
                    role="Lead Coordinator",
                )
            ]

            self.repo.save_event_bundle(new_event, tasks, contacts)
            return self.send_json(201, {
                "success": True,
                "event": new_event.model_dump(),
                "tasks_count": len(tasks),
            })

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
        return cursor.fetchone()["id"]


def run_server(port: int = 8080):
    repo = SQLiteEventRepository(str(DB_PATH))
    init_demo_database(repo)
    EventFlowAPIHandler.set_repo(repo)
    server = HTTPServer(("127.0.0.1", port), EventFlowAPIHandler)
    print(f"EventFlow UI server running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
