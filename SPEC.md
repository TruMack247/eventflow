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

## Out of Scope for v1
The following capabilities are deliberately excluded from the v1 scope:
- **Email Sending & Notifications**: No SMTP, transactional email, or automated reminder triggers.
- **Payments & Financial Transactions**: No payment gateways, invoice processing, or escrow integrations.
- **Multi-user Collaboration**: No user authentication, concurrent session resolution, role-based access control (RBAC), or real-time presence.
