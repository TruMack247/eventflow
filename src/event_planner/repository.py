"""Abstract repository interface defining storage operations."""
from abc import ABC, abstractmethod
from typing import List, Optional
from event_planner.models import Event, Task, Contact, Template


class EventRepository(ABC):
    """Storage-agnostic repository interface for event planning entities."""

    @abstractmethod
    def save_template(self, template: Template) -> None:
        """Persist or update a template blueprint."""
        pass

    @abstractmethod
    def get_template(self, template_id: str) -> Optional[Template]:
        """Fetch a template blueprint by identifier."""
        pass

    @abstractmethod
    def save_event_bundle(
        self,
        event: Event,
        tasks: List[Task],
        contacts: Optional[List[Contact]] = None,
    ) -> None:
        """
        Atomically persist an event with its tasks, dependencies, and optional contacts.
        Must be all-or-nothing (transactional).
        """
        pass

    @abstractmethod
    def get_event(self, event_id: str) -> Optional[Event]:
        """Fetch an event by identifier."""
        pass

    @abstractmethod
    def get_tasks_for_event(self, event_id: str) -> List[Task]:
        """Fetch all tasks for an event with reconstructed depends_on lists."""
        pass

    @abstractmethod
    def get_contacts_for_event(self, event_id: str) -> List[Contact]:
        """Fetch all contacts associated with the event."""
        pass

    @abstractmethod
    def delete_event(self, event_id: str) -> bool:
        """Delete an event and its cascading tasks, dependencies, and contacts."""
        pass

    @abstractmethod
    def save_task(self, task: Task) -> None:
        """Persist or update an individual task and synchronize its depends_on join entries."""
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Task]:
        """Fetch a single task by identifier with its reconstructed depends_on list."""
        pass
