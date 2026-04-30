"""Prefect API client singleton for use across DuckBricks."""

from app.services.prefect.client import PrefectApiClient

prefect_client = PrefectApiClient()
