"""Tests for translating DuckBricks dependency edges into Prefect wait_for inputs."""

from unittest.mock import MagicMock, patch

from app.services.jobs.models import JobTaskSnapshot
from app.services.jobs.prefect_flows import _resolve_task_graph, _submit_task_graph


class _FakeFuture:
    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        self.wait: MagicMock = MagicMock()
        self.result: MagicMock = MagicMock()


class _FakeConfiguredTask:
    def __init__(self, calls: list[dict]) -> None:
        self._calls = calls

    def submit(self, snapshot, *, wait_for, return_state):
        future = _FakeFuture(snapshot.task_id)
        self._calls.append(
            {
                "snapshot": snapshot,
                "wait_for": wait_for,
                "return_state": return_state,
                "future": future,
            }
        )
        return future


def test_submits_independent_roots_and_a_join_with_all_upstream_futures() -> None:
    snapshots = [
        JobTaskSnapshot(1, "Root A", "sql", "a.sql", "", 0),
        JobTaskSnapshot(2, "Root B", "sql", "b.sql", "", 1),
        JobTaskSnapshot(3, "Join", "sql", "join.sql", "", 2, (1, 2)),
    ]
    calls: list[dict] = []
    fake_task = MagicMock()
    fake_task.with_options.side_effect = lambda **_: _FakeConfiguredTask(calls)

    with patch("app.services.jobs.prefect_flows.execute_task", fake_task):
        futures = _submit_task_graph(snapshots, 7)

    assert calls[0]["wait_for"] == []
    assert calls[1]["wait_for"] == []
    assert [future.task_id for future in calls[2]["wait_for"]] == [1, 2]
    assert set(futures) == {1, 2, 3}

    _resolve_task_graph(futures)
    for future in futures.values():
        assert isinstance(future, _FakeFuture)
        future.wait.assert_called_once()
        future.result.assert_called_once()
