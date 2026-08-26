"""Validation and ordering for editable DuckBricks job graphs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from app.services.jobs.models import JobTaskInput, JobTaskSnapshot


class JobGraphValidationError(ValueError):
    """Raised when a job definition cannot form an executable DAG."""


class JobGraphService:
    """Validates task graphs and produces deterministic topological orderings."""

    _EXECUTOR_BY_EXTENSION = {".sql": "sql", ".py": "python"}

    @classmethod
    def executor_for_path(cls, file_path: str) -> str:
        extension = Path(file_path).suffix.lower()
        executor_type = cls._EXECUTOR_BY_EXTENSION.get(extension)
        if not executor_type:
            supported = ", ".join(sorted(cls._EXECUTOR_BY_EXTENSION))
            raise JobGraphValidationError(
                f"Unsupported task file '{file_path}'. Supported extensions: {supported}."
            )
        return executor_type

    @classmethod
    def validate_inputs(cls, tasks: Sequence[JobTaskInput]) -> tuple[str, ...]:
        keys = [task.key for task in tasks]
        if len(set(keys)) != len(keys):
            raise JobGraphValidationError("Every task must have a unique editor key.")

        normalized_names = [task.name.strip().casefold() for task in tasks]
        if any(not name for name in normalized_names):
            raise JobGraphValidationError("Every task must have a name.")
        if len(set(normalized_names)) != len(normalized_names):
            raise JobGraphValidationError("Task names must be unique within a job.")

        key_set = set(keys)
        dependencies: dict[str, tuple[str, ...]] = {}
        for task in tasks:
            if not task.file_path and not task.legacy_content:
                raise JobGraphValidationError(f"Task '{task.name}' requires a workspace file.")
            if task.file_path:
                expected_executor = cls.executor_for_path(task.file_path)
                if task.executor_type != expected_executor:
                    raise JobGraphValidationError(
                        f"Task '{task.name}' must use the {expected_executor} executor."
                    )
            if task.key in task.depends_on:
                raise JobGraphValidationError(f"Task '{task.name}' cannot depend on itself.")
            missing = [key for key in task.depends_on if key not in key_set]
            if missing:
                raise JobGraphValidationError(
                    f"Task '{task.name}' references missing dependencies: {', '.join(missing)}."
                )
            dependencies[task.key] = tuple(dict.fromkeys(task.depends_on))

        return cls._topological_keys(keys, dependencies)

    @classmethod
    def order_snapshots(cls, tasks: Sequence[JobTaskSnapshot]) -> tuple[JobTaskSnapshot, ...]:
        task_by_key = {str(task.task_id): task for task in tasks}
        ordered_keys = cls._topological_keys(
            [str(task.task_id) for task in tasks],
            {
                str(task.task_id): tuple(
                    str(dependency_id) for dependency_id in task.dependency_ids
                )
                for task in tasks
            },
        )
        return tuple(task_by_key[key] for key in ordered_keys)

    @staticmethod
    def _topological_keys(
        keys: Sequence[str], dependencies: dict[str, tuple[str, ...]]
    ) -> tuple[str, ...]:
        position = {key: index for index, key in enumerate(keys)}
        indegree = {key: len(dependencies.get(key, ())) for key in keys}
        dependents: dict[str, list[str]] = defaultdict(list)
        for key, upstream_keys in dependencies.items():
            for upstream_key in upstream_keys:
                dependents[upstream_key].append(key)

        ready = sorted(
            (key for key, count in indegree.items() if count == 0),
            key=lambda value: position[value],
        )
        ordered: list[str] = []
        while ready:
            key = ready.pop(0)
            ordered.append(key)
            for dependent in sorted(dependents[key], key=lambda value: position[value]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort(key=lambda value: position[value])

        if len(ordered) != len(keys):
            raise JobGraphValidationError("Task dependencies contain a cycle.")
        return tuple(ordered)
