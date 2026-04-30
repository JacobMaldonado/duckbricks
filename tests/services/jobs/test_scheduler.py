"""Scheduler tests — superseded by Prefect deployment schedules.

The PrefectJobScheduler (cron polling loop) has been removed. Cron scheduling
is now handled by Prefect deployment schedules managed through PrefectApiClient.
See tests/services/prefect/test_prefect_client.py for the new scheduler tests.
"""

import pytest


@pytest.mark.skip(reason="PrefectJobScheduler replaced by Prefect deployment schedules")
def test_placeholder() -> None:
    pass
