"""Prefect scheduler — singleton for use across the application."""

from app.services.jobs.scheduler import PrefectJobScheduler

prefect_scheduler = PrefectJobScheduler()
