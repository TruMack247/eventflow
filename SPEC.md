# Event Planner Engine - Specification (v1)

## Overview
A general-purpose, event-agnostic planning engine capable of orchestrating events, tasks, dependencies, contacts, and template lifecycles.

## Data Model

All entities use string identifiers (`id`) formatted as UUIDs or prefixed unique strings.

### 1. Event
Represents a single planned event instance.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `str` | Required, non-empty, unique | Primary identifier. |
| `name` | `str` | Required, non-empty | Name or title of the event. |
| `date` | `date` / `datetime` | Required | Planned event date. |
| `status` | `str` / `Enum` | Required, one of: `draft`, `confirmed`, `completed`, `cancelled` | Current lifecycle state. |
| `budget` | `Decimal` / `float` | Required, $\ge 0$ | Total allocated budget. |
| `partner_1_name` | `str` | Optional, default `"Alex"` | Name of primary partner / planner (e.g., `"Chris"`). |
| `partner_2_name` | `str` | Optional, default `"Jordan"` | Name of co-partner / fiancée (e.g., `"Taylor"`). |
| `template_id` | `Optional[str]` | Optional, references `Template.id` | Source template if generated from one. |

### 2. Task
A unit of work associated with an event.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `str` | Required, non-empty, unique | Primary identifier. |
| `event_id` | `str` | Required, references `Event.id` | Associated event. |
| `title` | `str` | Required, non-empty | Task description/headline. |
| `due_date` | `date` / `datetime` | Required | Due date for the task. |
| `status` | `str` / `Enum` | Required, one of: `todo`, `in_progress`, `done` | Task execution status. |
| `depends_on` | `List[str]` | Default: `[]`, elements reference `Task.id` | Pre-requisite task IDs. Must be acyclic and exist in same event. |
| `vendor_category` | `Optional[str]` | Optional | Category tag (e.g., `"venue"`, `"catering"`, `"photography"`). |
| `assignee` | `Optional[str]` | Optional, default `"Both"` | Owner of task (e.g., `"Alex"`, `"Jordan"`, or `"Both"`). |
| `notes` | `Optional[str]` | Optional, default `""` | Detailed notes, vendor URLs, contract links. |
| `estimated_cost` | `Decimal` / `float` | Default `0.0`, $\ge 0$ | Estimated budget allocation for this item. |
| `actual_cost` | `Decimal` / `float` | Default `0.0`, $\ge 0$ | Contracted / invoiced cost. |
| `paid_amount` | `Decimal` / `float` | Default `0.0`, $\ge 0$ | Deposits and payments made to date. |
| `checklist` | `List[ChecklistItem]` | Default: `[]` | Actionable sub-checklist items. |

#### ChecklistItem (Value Object / Sub-entity)
| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `str` | Required, non-empty | Sub-task item ID. |
| `text` | `str` | Required, non-empty | Sub-task description (e.g., `"Schedule cake tasting"`). |
| `completed` | `bool` | Default: `False` | Completion state. |

### 3. Contact
An individual or vendor involved in an event.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `str` | Required, non-empty, unique | Primary identifier. |
| `event_id` | `str` | Required, references `Event.id` | Associated event. |
| `name` | `str` | Required, non-empty | Contact person or organization name. |
| `email` | `str` | Required, valid email format | Primary email address. |
| `role` | `str` | Required, non-empty | Role descriptor (e.g., `"photographer"`, `"venue"`, `"officiant"`). |

### 4. Template
A blueprint for instantiating events with predefined task sets and relative schedules.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `str` | Required, non-empty, unique | Primary identifier (e.g., `"wedding_v1"`). |
| `name` | `str` | Required, non-empty | Display name of the template. |
| `default_tasks` | `List[TemplateTask]` | List of task blueprints | Default tasks with relative deadlines. |

#### TemplateTask (Value Object / Sub-entity)
| Field | Type | Constraints | Description |
|---|---|---|---|
| `template_task_id` | `str` | Required, unique within template | Identifier used for intra-template dependency mapping. |
| `title` | `str` | Required, non-empty | Default task title. |
| `relative_days` | `int` | Integer offset relative to event date | Relative deadline in days (e.g., `-365` means 365 days before event date). |
| `depends_on` | `List[str]` | Default: `[]`, references `template_task_id` | Intra-template prerequisites. |
| `vendor_category` | `Optional[str]` | Optional | Recommended vendor category. |


---

## Persistence (SQLite)

The persistence layer is storage-agnostic from the perspective of core models and engines. The repository interface defines abstract contracts, while `sqlite_repository.py` implements the concrete SQLite storage using standard Python `sqlite3`.

### Schema & Tables

All tables enforce foreign keys (`PRAGMA foreign_keys = ON` on every connection) and cascading deletes where appropriate.

```sql
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
    estimated_cost REAL DEFAULT 0.0 CHECK (estimated_cost >= 0),
    actual_cost REAL DEFAULT 0.0 CHECK (actual_cost >= 0),
    paid_amount REAL DEFAULT 0.0 CHECK (paid_amount >= 0),
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
```

### Table Definitions

1. **`templates`**:
   - `id` (TEXT, PK): Primary key identifier.
   - `name` (TEXT, NOT NULL): Display name.
   - `default_tasks_json` (TEXT, NOT NULL): JSON serialization of default template tasks and offsets.
2. **`events`**:
   - `id` (TEXT, PK): Primary key identifier.
   - `name` (TEXT, NOT NULL): Event name.
   - `date` (TEXT, NOT NULL): ISO 8601 formatted date/datetime string.
   - `status` (TEXT, NOT NULL): Lifecycle state (`draft`, `confirmed`, `completed`, `cancelled`).
   - `budget` (REAL, NOT NULL): Budget amount ($\ge 0$).
   - `template_id` (TEXT, NULLABLE, FK -> `templates.id`): References source template.
3. **`tasks`**:
   - `id` (TEXT, PK): Primary key identifier.
   - `event_id` (TEXT, NOT NULL, FK -> `events.id` ON DELETE CASCADE): Parent event.
   - `title` (TEXT, NOT NULL): Title of the task.
   - `due_date` (TEXT, NOT NULL): ISO 8601 formatted due date string.
   - `status` (TEXT, NOT NULL): Task state (`todo`, `in_progress`, `done`).
   - `vendor_category` (TEXT, NULLABLE): Optional vendor tag.
4. **`task_dependencies`** (Join Table):
   - `task_id` (TEXT, NOT NULL, FK -> `tasks.id` ON DELETE CASCADE): The dependent task.
   - `depends_on_task_id` (TEXT, NOT NULL, FK -> `tasks.id` ON DELETE CASCADE): The prerequisite task that must be completed first.
   - `PRIMARY KEY (task_id, depends_on_task_id)`: Enforces unique dependency pairs.
5. **`contacts`**:
   - `id` (TEXT, PK): Primary key identifier.
   - `event_id` (TEXT, NOT NULL, FK -> `events.id` ON DELETE CASCADE): Parent event.
   - `name` (TEXT, NOT NULL): Contact name.
   - `email` (TEXT, NOT NULL): Contact email address.
   - `role` (TEXT, NOT NULL): Role description.

### Repository Operations Contract

The repository provides abstract storage operations for events, tasks, contacts, and templates:

- `save_template(template: Template) -> None`: Inserts or updates a template blueprint.
- `get_template(template_id: str) -> Optional[Template]`: Retrieves a template by ID.
- `save_event_bundle(event: Event, tasks: List[Task], contacts: Optional[List[Contact]] = None) -> None`:
  - Atomic, all-or-nothing transactional operation (`BEGIN IMMEDIATE` / `COMMIT`).
  - Persists the `Event`, each `Task`, all join rows in `task_dependencies`, and optional `contacts`.
  - If any constraint or write fails, the entire transaction rolls back.
- `get_event(event_id: str) -> Optional[Event]`: Fetches an event by ID.
- `get_tasks_for_event(event_id: str) -> List[Task]`: Fetches all tasks for an event, reconstructing their `depends_on` lists via join from `task_dependencies`.
- `get_contacts_for_event(event_id: str) -> List[Contact]`: Fetches all contacts associated with the event.
- `delete_event(event_id: str) -> bool`: Deletes an event and cascades to its tasks, dependencies, and contacts.
- `save_task(task: Task) -> None`: Inserts or updates an individual task and syncs its `task_dependencies` join table entries within a transaction.
- `get_task(task_id: str) -> Optional[Task]`: Fetches a single task by ID with its reconstructed `depends_on` list.

### Constraints & Invariants
- `PRAGMA foreign_keys = ON;` must be executed immediately on opening any connection.
- Transactions must guarantee atomicity for all bundled writes (Event + Tasks + Dependencies).
- Only `sqlite_repository.py` imports `sqlite3`.

---

## Workflow & Schedule Execution Engine

The workflow engine governs state transitions, dependency gating, and date recalculation rules across tasks in an event. It is storage-agnostic and operates on in-memory domain models.

### 1. Task State Transitions & Gating
Tasks follow strict lifecycle progression: `todo` $\to$ `in_progress` $\to$ `done`.

- **Prerequisite Completion Gate**:
  - A task cannot transition to `in_progress` or `done` unless **all** tasks listed in its `depends_on` have status `done`.
  - Attempting to transition a task whose dependencies are not all `done` raises a `BlockedTaskError`.
- **Reopening Propagation Gate**:
  - If a task marked `done` is transitioned back to `todo` or `in_progress`, any downstream dependent tasks currently in `in_progress` or `done` must either block the transition or be transitioned back according to policy (default: raise `DependentTasksBlockReopenError` unless `force=True` cascades reopening downstream tasks to `todo`).

### 2. Actionable / Ready Tasks Query
A query function to identify unblocked work:
- `get_actionable_tasks(tasks: List[Task]) -> List[Task]`:
  - Returns all tasks currently with `status == TaskStatus.TODO` whose prerequisites (`depends_on`) are **all** in `TaskStatus.DONE` (or tasks with no dependencies).

### 3. Schedule & Cascade Rescheduling
Supports moving dates while preserving chronological constraints:
- `reschedule_event(event: Event, tasks: List[Task], new_date: Union[date, datetime]) -> Tuple[Event, List[Task]]`:
  - Shifts the event date by $\Delta = \text{new\_date} - \text{old\_date}$.
  - Shifts all tasks' `due_date` by the identical delta $\Delta$, preserving all relative offsets.
- `shift_task_due_date(tasks: List[Task], task_id: str, new_due_date: Union[date, datetime], cascade: bool = True) -> List[Task]`:
  - If a prerequisite task is postponed past the due date of a downstream dependent task, downstream dependent tasks are shifted forward to ensure every dependent task's `due_date` $\ge$ all its prerequisites' `due_date`.
  - Validates that no task is pushed beyond the event date unless explicitly allowed.

---

## Cloud Deployment & Shared Access Specification

To allow partners / co-planners to access and edit the exact same event concurrently on any device (phones, tablets, laptops) 24/7 without hosting from a local personal computer:

### 1. Environment Configuration & Persistent Storage
- `PORT`: Configurable HTTP port (default: `8080`, standard cloud port: `8080` or `10000` on Render/Fly).
- `HOST`: Bind address (default `0.0.0.0` for container / cloud deployment, accessible from all network interfaces).
- `DATABASE_PATH`: Path to SQLite database file. Configurable via environment variable (e.g. `/data/event_planner.db` for persistent cloud disk volumes, or `event_planner.db` locally).
- `APP_PASSCODE`: Optional shared wedding passcode. When set, requests must supply the passcode (via session storage header `X-App-Passcode`) to view or mutate event data.

### 2. Partner Persona Context
- Planners can switch active persona context (e.g., "Alex" or "Jordan" or custom names) stored client-side in `localStorage`.
- Actions such as status transitions and date shifts carry the active persona tag in operation telemetry without requiring heavyweight enterprise identity providers.

### 3. Container & Deployment Specification
- Standard `Dockerfile` using lightweight official Python `3.11-slim` runtime.
- Standard `render.yaml` defining a web service with a persistent disk mount at `/data` ensuring SQLite survives service deploys and restarts.

---

## Out of Scope for v1
- **Email Sending & Notifications**: No SMTP, transactional email, or automated reminder triggers.
- **Payments & Financial Transactions**: No payment gateways, invoice processing, or escrow integrations.
- **Complex Enterprise RBAC**: Multi-tenant organizations and fine-grained permissions remain out of v1; shared couple access uses the shared wedding access gate and lightweight partner switching.
