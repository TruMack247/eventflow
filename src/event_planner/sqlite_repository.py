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
        raise NotImplementedError

    def get_template(self, template_id: str) -> Optional[Template]:
        raise NotImplementedError

    def save_event_bundle(
        self,
        event: Event,
        tasks: List[Task],
        contacts: Optional[List[Contact]] = None,
    ) -> None:
        raise NotImplementedError

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
