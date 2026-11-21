"""SQLite implementation of the EventRepository interface."""
import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Union

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
from event_planner.repository import EventRepository


class SQLiteEventRepository(EventRepository):
    """
    SQLite-backed repository implementing the EventRepository interface.
    Guarantees:
      - PRAGMA foreign_keys = ON on all connections.
      - Atomic transaction handling for multi-table writes.
      - Normalization of dependencies into the task_dependencies join table.
    """

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        default_tasks_json TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('draft', 'confirmed', 'completed', 'cancelled')),
        budget REAL NOT NULL CHECK (budget >= 0),
        partner_1_name TEXT DEFAULT 'Alex',
        partner_2_name TEXT DEFAULT 'Jordan',
        template_id TEXT,
        FOREIGN KEY (template_id) REFERENCES templates (id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        title TEXT NOT NULL,
        due_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('todo', 'in_progress', 'done')),
        vendor_category TEXT,
        assignee TEXT DEFAULT 'Both',
        notes TEXT DEFAULT '',
        estimated_cost REAL DEFAULT 0.0,
        actual_cost REAL DEFAULT 0.0,
        paid_amount REAL DEFAULT 0.0,
        checklist_json TEXT DEFAULT '[]',
        FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS task_dependencies (
        task_id TEXT NOT NULL,
        depends_on_task_id TEXT NOT NULL,
        PRIMARY KEY (task_id, depends_on_task_id),
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
        FOREIGN KEY (depends_on_task_id) REFERENCES tasks (id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
    );
    """

    def __init__(self, connection_or_path: Union[sqlite3.Connection, str] = ":memory:"):
        """
        Initialize SQLite repository with either a file path or an existing connection.
        Enforces foreign key constraints immediately.
        """
        if isinstance(connection_or_path, sqlite3.Connection):
            self.conn = connection_or_path
            self._should_close = False
        else:
            self.conn = sqlite3.connect(connection_or_path, check_same_thread=False)
            self._should_close = True

        self.conn.row_factory = sqlite3.Row
        self._enable_foreign_keys()
        self._init_schema()

    def _enable_foreign_keys(self) -> None:
        """Enforces SQLite foreign keys on the active connection."""
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def _init_schema(self) -> None:
        """Executes table creation DDL and applies incremental column migrations."""
        with self.conn:
            self.conn.executescript(self.SCHEMA_SQL)
            # Automatic schema migration for existing databases: tasks table
            cursor = self.conn.execute("PRAGMA table_info(tasks);")
            columns = {row["name"] for row in cursor.fetchall()}
            migrations = [
                ("assignee", "ALTER TABLE tasks ADD COLUMN assignee TEXT DEFAULT 'Both';"),
                ("notes", "ALTER TABLE tasks ADD COLUMN notes TEXT DEFAULT '';"),
                ("estimated_cost", "ALTER TABLE tasks ADD COLUMN estimated_cost REAL DEFAULT 0.0;"),
                ("actual_cost", "ALTER TABLE tasks ADD COLUMN actual_cost REAL DEFAULT 0.0;"),
                ("paid_amount", "ALTER TABLE tasks ADD COLUMN paid_amount REAL DEFAULT 0.0;"),
                ("checklist_json", "ALTER TABLE tasks ADD COLUMN checklist_json TEXT DEFAULT '[]';"),
            ]
            for col_name, alter_stmt in migrations:
                if col_name not in columns:
                    self.conn.execute(alter_stmt)

            # Automatic schema migration: events table
            ev_cursor = self.conn.execute("PRAGMA table_info(events);")
            ev_columns = {row["name"] for row in ev_cursor.fetchall()}
            if "partner_1_name" not in ev_columns:
                self.conn.execute("ALTER TABLE events ADD COLUMN partner_1_name TEXT DEFAULT 'Alex';")
            if "partner_2_name" not in ev_columns:
                self.conn.execute("ALTER TABLE events ADD COLUMN partner_2_name TEXT DEFAULT 'Jordan';")

    def close(self) -> None:
        """Closes the underlying SQLite connection if owned."""
        if self._should_close and self.conn:
            self.conn.close()

    def save_template(self, template: Template) -> None:
        """Persist or update a template blueprint with JSON-serialized tasks."""
        tasks_data = [t.model_dump() for t in template.default_tasks]
        tasks_json = json.dumps(tasks_data)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO templates (id, name, default_tasks_json)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    default_tasks_json = excluded.default_tasks_json;
                """,
                (template.id, template.name, tasks_json),
            )

    def get_template(self, template_id: str) -> Optional[Template]:
        """Fetch a template blueprint by identifier."""
        cursor = self.conn.execute(
            "SELECT id, name, default_tasks_json FROM templates WHERE id = ?;",
            (template_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        raw_tasks = json.loads(row["default_tasks_json"])
        default_tasks = [TemplateTask(**t) for t in raw_tasks]
        return Template(
            id=row["id"],
            name=row["name"],
            default_tasks=default_tasks,
        )

    def save_event_bundle(
        self,
        event: Event,
        tasks: List[Task],
        contacts: Optional[List[Contact]] = None,
    ) -> None:
        """
        Atomically persist an event with its tasks, dependencies, and optional contacts.
        All operations run inside a single transaction; if any fail, all are rolled back.
        """
        contacts_list = contacts or []

        # Validate task consistency: all tasks must belong to this event
        for task in tasks:
            if task.event_id != event.id:
                raise ValueError(
                    f"Task '{task.id}' has event_id '{task.event_id}', expected '{event.id}'"
                )

        # Validate contacts consistency
        for contact in contacts_list:
            if contact.event_id != event.id:
                raise ValueError(
                    f"Contact '{contact.id}' has event_id '{contact.event_id}', expected '{event.id}'"
                )

        event_date_str = (
            event.date.isoformat()
            if isinstance(event.date, (date, datetime))
            else str(event.date)
        )

        with self.conn:
            # 1. Upsert event
            self.conn.execute(
                """
                INSERT INTO events (id, name, date, status, budget, partner_1_name, partner_2_name, template_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    date = excluded.date,
                    status = excluded.status,
                    budget = excluded.budget,
                    partner_1_name = excluded.partner_1_name,
                    partner_2_name = excluded.partner_2_name,
                    template_id = excluded.template_id;
                """,
                (
                    event.id,
                    event.name,
                    event_date_str,
                    event.status.value,
                    float(event.budget),
                    getattr(event, "partner_1_name", "Alex") or "Alex",
                    getattr(event, "partner_2_name", "Jordan") or "Jordan",
                    event.template_id,
                ),
            )

            # 2. Upsert tasks
            for task in tasks:
                task_due_str = (
                    task.due_date.isoformat()
                    if isinstance(task.due_date, (date, datetime))
                    else str(task.due_date)
                )
                checklist_json = json.dumps([c.model_dump() for c in task.checklist])
                self.conn.execute(
                    """
                    INSERT INTO tasks (
                        id, event_id, title, due_date, status, vendor_category,
                        assignee, notes, estimated_cost, actual_cost, paid_amount, checklist_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        event_id = excluded.event_id,
                        title = excluded.title,
                        due_date = excluded.due_date,
                        status = excluded.status,
                        vendor_category = excluded.vendor_category,
                        assignee = excluded.assignee,
                        notes = excluded.notes,
                        estimated_cost = excluded.estimated_cost,
                        actual_cost = excluded.actual_cost,
                        paid_amount = excluded.paid_amount,
                        checklist_json = excluded.checklist_json;
                    """,
                    (
                        task.id,
                        task.event_id,
                        task.title,
                        task_due_str,
                        task.status.value,
                        task.vendor_category,
                        task.assignee,
                        task.notes,
                        float(task.estimated_cost),
                        float(task.actual_cost),
                        float(task.paid_amount),
                        checklist_json,
                    ),
                )

                # Sync task dependencies: delete existing and reinsert
                self.conn.execute(
                    "DELETE FROM task_dependencies WHERE task_id = ?;",
                    (task.id,),
                )
                for dep_id in task.depends_on:
                    self.conn.execute(
                        """
                        INSERT INTO task_dependencies (task_id, depends_on_task_id)
                        VALUES (?, ?);
                        """,
                        (task.id, dep_id),
                    )

            # 3. Upsert contacts
            for contact in contacts_list:
                self.conn.execute(
                    """
                    INSERT INTO contacts (id, event_id, name, email, role)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        event_id = excluded.event_id,
                        name = excluded.name,
                        email = excluded.email,
                        role = excluded.role;
                    """,
                    (
                        contact.id,
                        contact.event_id,
                        contact.name,
                        contact.email,
                        contact.role,
                    ),
                )

    def get_event(self, event_id: str) -> Optional[Event]:
        """Fetch an event by identifier."""
        cursor = self.conn.execute(
            """
            SELECT id, name, date, status, budget, partner_1_name, partner_2_name, template_id
            FROM events
            WHERE id = ?;
            """,
            (event_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        event_date = (
            datetime.fromisoformat(row["date"]).date()
            if "T" not in row["date"] and len(row["date"]) == 10
            else datetime.fromisoformat(row["date"])
        )

        p1 = row["partner_1_name"] if "partner_1_name" in row.keys() and row["partner_1_name"] else "Alex"
        p2 = row["partner_2_name"] if "partner_2_name" in row.keys() and row["partner_2_name"] else "Jordan"

        return Event(
            id=row["id"],
            name=row["name"],
            date=event_date,
            status=EventStatus(row["status"]),
            budget=Decimal(str(row["budget"])),
            partner_1_name=p1,
            partner_2_name=p2,
            template_id=row["template_id"],
        )

    def get_tasks_for_event(self, event_id: str) -> List[Task]:
        """Fetch all tasks for an event with reconstructed depends_on lists."""
        cursor = self.conn.execute(
            """
            SELECT id, event_id, title, due_date, status, vendor_category,
                   assignee, notes, estimated_cost, actual_cost, paid_amount, checklist_json
            FROM tasks
            WHERE event_id = ?
            ORDER BY due_date ASC;
            """,
            (event_id,),
        )
        task_rows = cursor.fetchall()
        if not task_rows:
            return []

        # Fetch all dependencies for tasks belonging to this event
        dep_cursor = self.conn.execute(
            """
            SELECT td.task_id, td.depends_on_task_id
            FROM task_dependencies td
            JOIN tasks t ON td.task_id = t.id
            WHERE t.event_id = ?;
            """,
            (event_id,),
        )
        deps_by_task: dict[str, list[str]] = {}
        for dep_row in dep_cursor.fetchall():
            deps_by_task.setdefault(dep_row["task_id"], []).append(
                dep_row["depends_on_task_id"]
            )

        tasks: List[Task] = []
        for row in task_rows:
            task_due_date = (
                datetime.fromisoformat(row["due_date"]).date()
                if "T" not in row["due_date"] and len(row["due_date"]) == 10
                else datetime.fromisoformat(row["due_date"])
            )
            raw_checklist = json.loads(row["checklist_json"] or "[]")
            checklist = [ChecklistItem(**c) for c in raw_checklist]

            tasks.append(
                Task(
                    id=row["id"],
                    event_id=row["event_id"],
                    title=row["title"],
                    due_date=task_due_date,
                    status=TaskStatus(row["status"]),
                    depends_on=deps_by_task.get(row["id"], []),
                    vendor_category=row["vendor_category"],
                    assignee=row["assignee"] or "Both",
                    notes=row["notes"] or "",
                    estimated_cost=Decimal(str(row["estimated_cost"] or 0.0)),
                    actual_cost=Decimal(str(row["actual_cost"] or 0.0)),
                    paid_amount=Decimal(str(row["paid_amount"] or 0.0)),
                    checklist=checklist,
                )
            )
        return tasks

    def get_contacts_for_event(self, event_id: str) -> List[Contact]:
        """Fetch all contacts associated with the event."""
        cursor = self.conn.execute(
            """
            SELECT id, event_id, name, email, role
            FROM contacts
            WHERE event_id = ?;
            """,
            (event_id,),
        )
        return [
            Contact(
                id=row["id"],
                event_id=row["event_id"],
                name=row["name"],
                email=row["email"],
                role=row["role"],
            )
            for row in cursor.fetchall()
        ]

    def delete_event(self, event_id: str) -> bool:
        """Delete an event and its cascading tasks, dependencies, and contacts."""
        with self.conn:
            cursor = self.conn.execute("DELETE FROM events WHERE id = ?;", (event_id,))
            return cursor.rowcount > 0

    def save_task(self, task: Task) -> None:
        """Persist or update an individual task and synchronize its depends_on join entries."""
        task_due_str = (
            task.due_date.isoformat()
            if isinstance(task.due_date, (date, datetime))
            else str(task.due_date)
        )
        checklist_json = json.dumps([c.model_dump() for c in task.checklist])
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO tasks (
                    id, event_id, title, due_date, status, vendor_category,
                    assignee, notes, estimated_cost, actual_cost, paid_amount, checklist_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    event_id = excluded.event_id,
                    title = excluded.title,
                    due_date = excluded.due_date,
                    status = excluded.status,
                    vendor_category = excluded.vendor_category,
                    assignee = excluded.assignee,
                    notes = excluded.notes,
                    estimated_cost = excluded.estimated_cost,
                    actual_cost = excluded.actual_cost,
                    paid_amount = excluded.paid_amount,
                    checklist_json = excluded.checklist_json;
                """,
                (
                    task.id,
                    task.event_id,
                    task.title,
                    task_due_str,
                    task.status.value,
                    task.vendor_category,
                    task.assignee,
                    task.notes,
                    float(task.estimated_cost),
                    float(task.actual_cost),
                    float(task.paid_amount),
                    checklist_json,
                ),
            )
            self.conn.execute(
                "DELETE FROM task_dependencies WHERE task_id = ?;",
                (task.id,),
            )
            for dep_id in task.depends_on:
                self.conn.execute(
                    """
                    INSERT INTO task_dependencies (task_id, depends_on_task_id)
                    VALUES (?, ?);
                    """,
                    (task.id, dep_id),
                )

    def get_task(self, task_id: str) -> Optional[Task]:
        """Fetch a single task by identifier with its reconstructed depends_on list."""
        cursor = self.conn.execute(
            """
            SELECT id, event_id, title, due_date, status, vendor_category,
                   assignee, notes, estimated_cost, actual_cost, paid_amount, checklist_json
            FROM tasks
            WHERE id = ?;
            """,
            (task_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        dep_cursor = self.conn.execute(
            """
            SELECT depends_on_task_id
            FROM task_dependencies
            WHERE task_id = ?;
            """,
            (task_id,),
        )
        depends_on = [dep_row["depends_on_task_id"] for dep_row in dep_cursor.fetchall()]

        task_due_date = (
            datetime.fromisoformat(row["due_date"]).date()
            if "T" not in row["due_date"] and len(row["due_date"]) == 10
            else datetime.fromisoformat(row["due_date"])
        )
        raw_checklist = json.loads(row["checklist_json"] or "[]")
        checklist = [ChecklistItem(**c) for c in raw_checklist]

        return Task(
            id=row["id"],
            event_id=row["event_id"],
            title=row["title"],
            due_date=task_due_date,
            status=TaskStatus(row["status"]),
            depends_on=depends_on,
            vendor_category=row["vendor_category"],
            assignee=row["assignee"] or "Both",
            notes=row["notes"] or "",
            estimated_cost=Decimal(str(row["estimated_cost"] or 0.0)),
            actual_cost=Decimal(str(row["actual_cost"] or 0.0)),
            paid_amount=Decimal(str(row["paid_amount"] or 0.0)),
            checklist=checklist,
        )
