"""SQLAlchemy ORM models for the app schema — jobs, tasks, and execution history."""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.services.database.base import Base


class Job(Base):
    """A named job containing one or more ordered tasks and an optional cron schedule."""

    __tablename__ = "jobs"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    schedule_cron: Mapped[str | None] = mapped_column(String(100))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    tasks: Mapped[list["JobTask"]] = relationship(
        "JobTask", back_populates="job", cascade="all, delete-orphan", order_by="JobTask.position"
    )
    executions: Mapped[list["JobExecution"]] = relationship(
        "JobExecution", back_populates="job", cascade="all, delete-orphan"
    )


class JobTask(Base):
    """A single unit of work within a job — SQL, Python, or other registered executor types."""

    __tablename__ = "job_tasks"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app.jobs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    executor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    job: Mapped["Job"] = relationship("Job", back_populates="tasks")
    executions: Mapped[list["TaskExecution"]] = relationship(
        "TaskExecution", back_populates="task", cascade="all, delete-orphan"
    )


class JobExecution(Base):
    """A single run of an entire job, tracking overall status and timing."""

    __tablename__ = "job_executions"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app.jobs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    job: Mapped["Job"] = relationship("Job", back_populates="executions")
    task_executions: Mapped[list["TaskExecution"]] = relationship(
        "TaskExecution", back_populates="job_execution", cascade="all, delete-orphan"
    )


class TaskExecution(Base):
    """Execution record for a single task within a job run."""

    __tablename__ = "task_executions"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_execution_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app.job_executions.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app.job_tasks.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    output: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    job_execution: Mapped["JobExecution"] = relationship(
        "JobExecution", back_populates="task_executions"
    )
    task: Mapped["JobTask"] = relationship("JobTask", back_populates="executions")
