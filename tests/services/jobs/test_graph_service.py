"""Unit tests for job DAG validation and ordering."""

import pytest

from app.services.jobs.graph_service import JobGraphService, JobGraphValidationError
from app.services.jobs.models import JobTaskInput, JobTaskSnapshot


def _task(key: str, *depends_on: str) -> JobTaskInput:
    return JobTaskInput(
        key=key,
        name=key.title(),
        file_path=f"{key}.sql",
        executor_type="sql",
        depends_on=depends_on,
    )


def test_validates_a_branched_graph_in_stable_topological_order() -> None:
    tasks = (
        _task("extract"),
        _task("customers", "extract"),
        _task("orders", "extract"),
        _task("publish", "customers", "orders"),
    )

    assert JobGraphService.validate_inputs(tasks) == (
        "extract",
        "customers",
        "orders",
        "publish",
    )


def test_rejects_cycles() -> None:
    tasks = (_task("first", "second"), _task("second", "first"))

    with pytest.raises(JobGraphValidationError, match="cycle"):
        JobGraphService.validate_inputs(tasks)


def test_rejects_duplicate_names_and_missing_dependencies() -> None:
    duplicate = (
        _task("first"),
        JobTaskInput("second", "First", "second.sql", "sql"),
    )
    with pytest.raises(JobGraphValidationError, match="unique"):
        JobGraphService.validate_inputs(duplicate)

    with pytest.raises(JobGraphValidationError, match="missing"):
        JobGraphService.validate_inputs((_task("first", "unknown"),))


def test_executor_is_inferred_only_for_supported_workspace_files() -> None:
    assert JobGraphService.executor_for_path("queries/model.sql") == "sql"
    assert JobGraphService.executor_for_path("pipelines/load.py") == "python"
    with pytest.raises(JobGraphValidationError, match="Unsupported"):
        JobGraphService.executor_for_path("notebooks/model.ipynb")


def test_orders_persisted_snapshots_from_dependency_ids() -> None:
    downstream = JobTaskSnapshot(2, "Load", "sql", "load.sql", "", 0, (1,))
    upstream = JobTaskSnapshot(1, "Extract", "sql", "extract.sql", "", 1)

    ordered = JobGraphService.order_snapshots((downstream, upstream))

    assert [task.task_id for task in ordered] == [1, 2]
