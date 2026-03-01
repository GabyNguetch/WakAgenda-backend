"""
app/repositories/task_repository.py
Couche d'accès aux données pour les tâches.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.task import Task, EventCategory, EventDomain, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate, TaskStats


class TaskRepository:
    """Toutes les opérations DB relatives aux tâches."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, task_id: uuid.UUID) -> Optional[Task]:
        return self.db.get(Task, task_id)

    def get_by_id_and_user(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Task]:
        return (
            self.db.query(Task)
            .filter(Task.id == task_id, Task.user_id == user_id)
            .first()
        )

    def get_all_for_user(
        self,
        user_id: uuid.UUID,
        category: Optional[EventCategory] = None,
        domain: Optional[EventDomain] = None,
        status: Optional[TaskStatus] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        query = self.db.query(Task).filter(Task.user_id == user_id)

        if category:
            query = query.filter(Task.category == category)
        if domain:
            query = query.filter(Task.domain == domain)
        if status:
            query = query.filter(Task.status == status)
        if date_from:
            query = query.filter(Task.task_date >= date_from)
        if date_to:
            query = query.filter(Task.task_date <= date_to)

        return query.order_by(Task.task_date.asc(), Task.start_time.asc()).offset(skip).limit(limit).all()

    def get_today_tasks(self, user_id: uuid.UUID) -> List[Task]:
        today = date.today()
        return (
            self.db.query(Task)
            .filter(Task.user_id == user_id, Task.task_date == today)
            .order_by(Task.start_time.asc())
            .all()
        )

    def get_upcoming_tasks(self, user_id: uuid.UUID, limit: int = 5) -> List[Task]:
        today = date.today()
        return (
            self.db.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.task_date >= today,
                Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
            )
            .order_by(Task.task_date.asc(), Task.start_time.asc())
            .limit(limit)
            .all()
        )

    def create(self, user_id: uuid.UUID, data: TaskCreate) -> Task:
        task = Task(user_id=user_id, **data.model_dump())
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update(self, task: Task, data: TaskUpdate) -> Task:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete(self, task: Task) -> None:
        self.db.delete(task)
        self.db.commit()

    def get_stats(self, user_id: uuid.UUID) -> TaskStats:
        today = date.today()
        all_tasks = self.db.query(Task).filter(Task.user_id == user_id).all()

        total = len(all_tasks)
        today_count = sum(1 for t in all_tasks if t.task_date == today)
        completed = sum(1 for t in all_tasks if t.status == TaskStatus.DONE)
        overdue = sum(
            1 for t in all_tasks
            if t.task_date < today and t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)
        )

        by_category = {}
        for cat in EventCategory:
            by_category[cat.value] = sum(1 for t in all_tasks if t.category == cat)

        by_status = {}
        for s in TaskStatus:
            by_status[s.value] = sum(1 for t in all_tasks if t.status == s)

        by_domain = {}
        for d in EventDomain:
            by_domain[d.value] = sum(1 for t in all_tasks if t.domain == d)

        return TaskStats(
            total=total,
            today=today_count,
            overdue=overdue,
            completed=completed,
            by_category=by_category,
            by_status=by_status,
            by_domain=by_domain,
        )
