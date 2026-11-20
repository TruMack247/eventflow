"""SQLite implementation of the EventRepository interface."""
import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Union

from event_planner.models import (
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
            self.conn = sqlite3.connect(connection_or_path)
            self._should_close = True

        self.conn.row_factory = sqlite3.Row
        self._enable_foreign_keys()
        self._init_schema()

    def _enable_foreign_keys(self) -> None:
        """Enforces SQLite foreign keys on the active connection."""
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def _init_schema(self) -> None:
        """Executes table creation DDL."""
        with self.conn:
            self.conn.executescript(self.SCHEMA_SQL)

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
                INSERT INTO events (id, name, date, status, budget, template_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    date = excluded.date,
                    status = excluded.status,
                    budget = excluded.budget,
                    template_id = excluded.template_id;
                """,
                (
                    event.id,
                    event.name,
                    event_date_str,
                    event.status.value,
                    float(event.budget),
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
                self.conn.execute(
                    """
                    INSERT INTO tasks (id, event_id, title, due_date, status, vendor_category)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        event_id = excluded.event_id,
                        title = excluded.title,
                        due_date = excluded.due_date,
                        status = excluded.status,
                        vendor_category = excluded.vendor_category;
                    """,
                    (
                        task.id,
                        task.event_id,
                        task.title,
                        task_due_str,
                        task.status.value,
                        task.vendor_category,
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
        raise NotImplementedError

    def get_tasks_for_event(self, event_id: str) -> List[Task]:
        raise NotImplementedError

    def get_contacts_for_event(self, event_id: str) -> List[Contact]:
        raise NotImplementedError

    def delete_event(self, event_id: str) -> bool:
        raise NotImplementedError

    def save_task(self, task: Task) -> None:
        raise NotImplementedError

    def get_task(self, task_id: str) -> Optional[Task]:
        raise NotImplementedError
