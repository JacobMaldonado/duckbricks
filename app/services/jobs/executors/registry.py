"""Registry mapping executor type names to their implementation classes."""

from app.services.jobs.executors.base import TaskExecutor


class ExecutorRegistry:
    """Central registry for all task executor implementations."""

    _registry: dict[str, type[TaskExecutor]] = {}

    @classmethod
    def register(cls, name: str, executor_class: type[TaskExecutor]) -> None:
        """Register an executor class under the given type name."""
        cls._registry[name] = executor_class

    @classmethod
    def resolve(cls, name: str) -> TaskExecutor:
        """Instantiate and return the executor for the given type name."""
        if name not in cls._registry:
            raise ValueError(
                f"Unknown executor type '{name}'. Registered types: {list(cls._registry)}"
            )
        return cls._registry[name]()

    @classmethod
    def available_types(cls) -> list[str]:
        """Return a sorted list of all registered executor type names."""
        return sorted(cls._registry.keys())
