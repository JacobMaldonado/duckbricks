"""DuckBricks — NiceGUI application entry point."""

import logging

from fastapi import Request, WebSocket
from nicegui import app, ui

from app.api.health import create_health_router
from app.api.marimo_proxy import proxy_http_request, proxy_websocket
from app.api.prefect_proxy import proxy_prefect_http
from app.config import HOST, PORT, RELOAD
from app.services.completion.schema_provider import CompletionSchemaProvider
from app.services.health import health_service
from app.services.metastore import manager
from app.services.startup import ApplicationStartup
from app.ui.pages.explorer import explorer_page
from app.ui.pages.job_execution import job_execution_page
from app.ui.pages.jobs import jobs_page
from app.ui.pages.query import query_workspace
from app.ui.pages.settings import settings_page
from app.ui.pages.workspace import workspace_page

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


_application_startup = ApplicationStartup()


async def startup() -> None:
    """Initialize required application dependencies or fail startup."""
    await _application_startup.run()


app.on_startup(startup)
app.include_router(create_health_router(health_service))
app.add_static_files("/static", "app/ui/static")


@app.api_route("/prefect-ui/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])
async def prefect_http_proxy(path: str, request: Request):
    """Reverse-proxy HTTP requests to the internal Prefect server UI and API."""
    return await proxy_prefect_http(path, request)


@app.api_route("/marimo/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])
async def marimo_http_proxy(path: str, request: Request):
    """Reverse-proxy HTTP requests to the internal Marimo service."""
    return await proxy_http_request(path, request)


@app.websocket("/marimo/{path:path}")
async def marimo_ws_proxy(path: str, client_ws: WebSocket) -> None:
    """Reverse-proxy WebSocket connections to the internal Marimo service."""
    await proxy_websocket(client_ws, path)


@app.get("/api/completion/schema")
async def completion_schema() -> dict:
    """Return catalog/schema/table/column structure for SQL autocompletion."""
    return CompletionSchemaProvider(manager).build()


@ui.page("/")
def index():
    """Root redirects to explorer."""
    ui.navigate.to("/explorer")


@ui.page("/explorer")
def explorer():
    """Metastore Explorer view."""
    explorer_page()


@ui.page("/query")
def query(table: str | None = None):
    """SQL Query Workspace."""
    query_workspace(table)


@ui.page("/jobs")
def jobs():
    """Jobs management page."""
    jobs_page()


@ui.page("/jobs/execution/{execution_id}")
def job_execution(execution_id: int):
    """Job execution detail page."""
    job_execution_page(execution_id)


@ui.page("/workspace")
def workspace():
    """Workspace file manager."""
    workspace_page()


@ui.page("/settings")
def settings():
    """Application settings and configuration."""
    settings_page()


if __name__ in {"__main__", "__mp_main__"}:
    print(f"Starting DuckBricks with reload={RELOAD}...")
    ui.run(title="DuckBricks", host=HOST, port=int(PORT), reload=RELOAD, reconnect_timeout=300)
