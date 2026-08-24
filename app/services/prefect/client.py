"""Async wrapper around the Prefect REST API for DuckBricks job orchestration."""

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import (
    DeploymentScheduleCreate,
    DeploymentUpdate,
    WorkPoolCreate,
)
from prefect.client.schemas.filters import (
    DeploymentFilter,
    DeploymentFilterId,
    FlowRunFilter,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import FlowRun
from prefect.client.schemas.schedules import CronSchedule
from prefect.client.schemas.sorting import FlowRunSort
from prefect.exceptions import ObjectNotFound
from prefect.states import StateType

from app.config import PREFECT_EXTERNAL_URL

if TYPE_CHECKING:
    from app.services.database.models.app import Job

_log = logging.getLogger(__name__)

_FLOW_NAME = "duckbricks-job"
_WORK_POOL_NAME = "duckbricks-pool"
_ENTRYPOINT = "app/services/jobs/prefect_flows.py:run_job_flow"
_FLOW_PATH = "/app"


class PrefectApiClient:
    """Manages Prefect deployments and flow runs on behalf of DuckBricks jobs.

    All methods are async and must be awaited. They communicate with the Prefect
    server whose URL is configured via the PREFECT_API_URL environment variable.
    """

    async def ensure_work_pool(self) -> None:
        """Create the DuckBricks work pool if it does not already exist."""
        async with get_client() as client:
            try:
                await client.read_work_pool(_WORK_POOL_NAME)
                _log.debug("Prefect work pool '%s' already exists.", _WORK_POOL_NAME)
            except ObjectNotFound:
                await client.create_work_pool(WorkPoolCreate(name=_WORK_POOL_NAME, type="process"))
                _log.info("Created Prefect work pool '%s'.", _WORK_POOL_NAME)

    async def register_flow(self) -> UUID:
        """Register the DuckBricks job flow with Prefect and return its flow ID."""
        async with get_client() as client:
            flow_id: UUID = await client.create_flow_from_name(_FLOW_NAME)
            return flow_id

    async def create_deployment(self, job: "Job") -> UUID:
        """Create a Prefect deployment for the given job and return its deployment ID."""
        async with get_client() as client:
            flow_id: UUID = await client.create_flow_from_name(_FLOW_NAME)
            schedules = self._build_schedules(job.schedule_cron if job.is_enabled else None)
            deployment_id: UUID = await client.create_deployment(
                flow_id=flow_id,
                name=self._deployment_name(job.id, job.name),
                entrypoint=_ENTRYPOINT,
                path=_FLOW_PATH,
                work_pool_name=_WORK_POOL_NAME,
                parameters={"job_id": job.id},
                schedules=schedules,
                description=job.description,
                tags=[f"job-id:{job.id}"],
            )
            _log.info("Created Prefect deployment %s for job %d.", deployment_id, job.id)
            return deployment_id

    async def update_deployment(self, deployment_id: UUID, job: "Job") -> None:
        """Update an existing Prefect deployment to reflect job changes.

        Also patches `path` so deployments created before this fix self-heal
        the next time the job is saved.
        """
        async with get_client() as client:
            schedules = self._build_schedules(job.schedule_cron if job.is_enabled else None)
            await client.update_deployment(
                deployment_id,
                DeploymentUpdate(description=job.description, path=_FLOW_PATH),
            )
            existing = await client.read_deployment_schedules(deployment_id)
            for existing_sched in existing:
                await client.delete_deployment_schedule(deployment_id, existing_sched.id)
            for new_sched in schedules:
                await client.create_deployment_schedules(deployment_id, [new_sched])
            _log.info("Updated Prefect deployment %s for job %d.", deployment_id, job.id)

    async def set_deployment_paused(self, deployment_id: UUID, *, paused: bool) -> None:
        """Pause or resume a Prefect deployment's scheduled runs."""
        async with get_client() as client:
            await client.update_deployment(  # type: ignore[misc]
                deployment_id, DeploymentUpdate(paused=paused)
            )
            state = "paused" if paused else "resumed"
            _log.info("Deployment %s %s.", deployment_id, state)

    async def delete_deployment(self, deployment_id: UUID) -> None:
        """Delete a Prefect deployment and all associated scheduled runs."""
        async with get_client() as client:
            await client.delete_deployment(deployment_id)
            _log.info("Deleted Prefect deployment %s.", deployment_id)

    async def trigger_run(self, deployment_id: UUID) -> FlowRun:
        """Trigger an immediate Prefect flow run for the given deployment."""
        async with get_client() as client:
            run = await client.create_flow_run_from_deployment(deployment_id)
            _log.info("Triggered flow run %s for deployment %s.", run.id, deployment_id)
            return run

    async def list_runs(self, deployment_id: UUID, limit: int = 200) -> list[FlowRun]:
        """Return flow runs for a deployment, newest first, excluding scheduled runs."""
        async with get_client() as client:
            runs: list[FlowRun] = await client.read_flow_runs(
                deployment_filter=DeploymentFilter(id=DeploymentFilterId(any_=[deployment_id])),
                flow_run_filter=FlowRunFilter(
                    state=FlowRunFilterState(
                        type=FlowRunFilterStateType(
                            any_=[
                                StateType.PENDING,
                                StateType.RUNNING,
                                StateType.COMPLETED,
                                StateType.FAILED,
                                StateType.CANCELLED,
                                StateType.CRASHED,
                                StateType.PAUSED,
                                StateType.CANCELLING,
                            ]
                        )
                    )
                ),
                sort=FlowRunSort.START_TIME_DESC,
                limit=limit,
            )
            return runs

    async def get_run(self, run_id: UUID) -> FlowRun:
        """Return a single flow run by its ID."""
        async with get_client() as client:
            return await client.read_flow_run(run_id)

    def deployment_ui_url(self, deployment_id: UUID) -> str:
        """Return the full browser-accessible URL for the Prefect UI deployment page."""
        return f"{PREFECT_EXTERNAL_URL}/prefect-ui/deployments/deployment/{deployment_id}"

    def run_ui_url(self, run_id: UUID) -> str:
        """Return the full browser-accessible URL for the Prefect UI flow run page."""
        return f"{PREFECT_EXTERNAL_URL}/prefect-ui/flow-runs/flow-run/{run_id}"

    def deployment_proxy_path(self, deployment_id: UUID) -> str:
        """Return the same-origin proxy path for embedding a deployment page in an iframe."""
        return f"/prefect-ui/deployments/deployment/{deployment_id}"

    def run_proxy_path(self, run_id: UUID) -> str:
        """Return the same-origin proxy path for embedding a flow run page in an iframe."""
        return f"/prefect-ui/flow-runs/flow-run/{run_id}"

    @staticmethod
    def _deployment_name(job_id: int, job_name: str) -> str:
        sanitized = job_name.lower().replace(" ", "-")[:50]
        return f"job-{job_id}-{sanitized}"

    @staticmethod
    def _build_schedules(cron_expression: str | None) -> list[DeploymentScheduleCreate]:
        if not cron_expression:
            return []
        return [DeploymentScheduleCreate(schedule=CronSchedule(cron=cron_expression), active=True)]
