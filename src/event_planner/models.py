"""Domain models for the event planning engine."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field, EmailStr, field_validator


class EventStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


DateOrDatetime = Union[date, datetime]


class Event(BaseModel):
    id: str = Field(..., min_length=1, description="Primary identifier")
    name: str = Field(..., min_length=1, description="Event name")
    date: DateOrDatetime = Field(..., description="Event date")
    status: EventStatus = Field(default=EventStatus.DRAFT, description="Event lifecycle state")
    budget: Decimal = Field(..., ge=0, description="Total allocated budget")
    template_id: Optional[str] = Field(default=None, description="Optional template reference")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Event name cannot be blank")
        return v.strip()


class ChecklistItem(BaseModel):
    id: str = Field(..., min_length=1, description="Sub-checklist item identifier")
    text: str = Field(..., min_length=1, description="Actionable item text")
    completed: bool = Field(default=False, description="Completion status")


class Task(BaseModel):
    id: str = Field(..., min_length=1, description="Primary identifier")
    event_id: str = Field(..., min_length=1, description="Associated event identifier")
    title: str = Field(..., min_length=1, description="Task title")
    due_date: DateOrDatetime = Field(..., description="Task due date")
    status: TaskStatus = Field(default=TaskStatus.TODO, description="Task status")
    depends_on: List[str] = Field(default_factory=list, description="IDs of prerequisite tasks")
    vendor_category: Optional[str] = Field(default=None, description="Optional vendor category tag")
    assignee: str = Field(default="Both", description="Task owner: Alex, Jordan, or Both")
    notes: str = Field(default="", description="Detailed notes, contract links, portfolio URLs")
    estimated_cost: Decimal = Field(default=Decimal("0.00"), ge=0, description="Estimated budget allocation")
    actual_cost: Decimal = Field(default=Decimal("0.00"), ge=0, description="Contracted or invoiced amount")
    paid_amount: Decimal = Field(default=Decimal("0.00"), ge=0, description="Amount paid to date")
    checklist: List[ChecklistItem] = Field(default_factory=list, description="Actionable sub-checklist items")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Task title cannot be blank")
        return v.strip()


class Contact(BaseModel):
    id: str = Field(..., min_length=1, description="Primary identifier")
    event_id: str = Field(..., min_length=1, description="Associated event identifier")
    name: str = Field(..., min_length=1, description="Contact name")
    email: EmailStr = Field(..., description="Contact email address")
    role: str = Field(..., min_length=1, description="Role descriptor")

    @field_validator("name", "role")
    @classmethod
    def field_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be blank")
        return v.strip()


class TemplateTask(BaseModel):
    template_task_id: str = Field(..., min_length=1, description="Identifier for intra-template dependency mapping")
    title: str = Field(..., min_length=1, description="Default task title")
    relative_days: int = Field(..., description="Days offset from event date (e.g. -365)")
    depends_on: List[str] = Field(default_factory=list, description="Prerequisite template_task_ids")
    vendor_category: Optional[str] = Field(default=None, description="Optional vendor category")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be blank")
        return v.strip()


class Template(BaseModel):
    id: str = Field(..., min_length=1, description="Primary identifier")
    name: str = Field(..., min_length=1, description="Template name")
    default_tasks: List[TemplateTask] = Field(default_factory=list, description="List of template tasks")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Template name cannot be blank")
        return v.strip()
