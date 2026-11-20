# Tasks

## Phase 1: Core Engine & Scaffolding
- [x] Project setup & initial scaffolding (AGENTS.md, SPEC.md, TASKS.md, HANDOFF.md)
- [x] Draft v1 data model in SPEC.md
- [x] Task 1: Initialize Python project packaging (`pyproject.toml`, directory structure `src/event_planner`, and pytest config)
- [x] Task 2: Implement core domain data models (`Event`, `Task`, `Contact`, `Template`)
- [x] Task 3: Implement validation rules for Event and Task entities (fields, types, bounds, status enums)
- [x] Task 4: Implement task dependency validation (cycle detection & referential integrity checks)
- [x] Task 5: Build comprehensive test suite for models and dependency validator using pytest
- [x] Task 6: Implement Template Loader & Event instantiation engine (resolving relative offsets and mapping dependency IDs)
- [x] Task 7: Define wedding template blueprint and test end-to-end wedding event generation

## Phase 2: Persistence Layer
- [x] Task P0: Draft Persistence section in SPEC.md with schema, foreign keys, join table, and repository contract
- [x] Task P1: Define abstract repository protocol/interface in `src/event_planner/repository.py`
- [x] Task P2: Implement schema initialization and foreign key enforcement in `src/event_planner/sqlite_repository.py`
- [x] Task P3: Implement template persistence (`save_template`, `get_template`) in SQLite repository
- [x] Task P4: Implement atomic bundle persistence (`save_event_bundle`, transactions, join table `task_dependencies`)
- [x] Task P5: Implement query & deletion operations (`get_event`, `get_tasks_for_event`, `get_contacts_for_event`, `delete_event`, `save_task`, `get_task`)
- [x] Task P6: Add in-memory SQLite unit tests for all repository operations and edge cases in `tests/test_sqlite_repository.py`
- [x] Task P7: Add disk-based round-trip persistence tests verifying survival across closed/reopened connections

## Phase 3: Workflow & Schedule Execution Engine
- [x] Task W0: Draft Workflow & Execution Engine specification in SPEC.md
- [x] Task W1: Implement transition validation and dependency gating (`transition_task_status`, `BlockedTaskError`, reopen checks) in `src/event_planner/workflow.py`
- [x] Task W2: Implement actionable / ready tasks query (`get_actionable_tasks`) in `src/event_planner/workflow.py`
- [x] Task W3: Implement event date shift and cascade task rescheduling (`reschedule_event`, `shift_task_due_date`) in `src/event_planner/workflow.py`
- [x] Task W4: Add comprehensive unit tests in `tests/test_workflow.py` for gating, ready tasks, and cascading reschedules
- [x] Task W5: Add integration tests connecting workflow engine with SQLite repository in `tests/test_workflow_persistence_integration.py`

## Phase 4: Stitch UI Integration
- [x] Task U1: Import Stitch export layout and assets from `stitch_eventflow_planning_engine`
- [x] Task U2: Build storage-agnostic live web server and API layer in `src/event_planner/web/server.py`
- [x] Task U3: Connect Stitch Dashboard, Actionable Hero, Kanban board, and Templates views to SQLite persistence and workflow engine
- [x] Task U4: Live browser verification of rendered UI and interactive state transitions at `http://127.0.0.1:8080`
