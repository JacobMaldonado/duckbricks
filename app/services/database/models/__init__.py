"""ORM model registry — import all models here so Alembic can detect them."""

from app.services.database.models.app import Job, JobExecution, JobTask, TaskExecution
from app.services.database.models.metastore import (
    CatalogModel,
    ColumnModel,
    PartitionModel,
    SchemaModel,
    TableModel,
)

__all__ = [
    "CatalogModel",
    "SchemaModel",
    "TableModel",
    "ColumnModel",
    "PartitionModel",
    "Job",
    "JobTask",
    "JobExecution",
    "TaskExecution",
]
