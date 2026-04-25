"""DuckBricks — NiceGUI application entry point."""

import logging
import shutil
from pathlib import Path

from nicegui import app, ui

from app.config import HELPERS_PATH, HOST, PORT, RELOAD, WORKSPACE_PATH
from app.services.completion.schema_provider import CompletionSchemaProvider
from app.services.database.session import init_database
from app.services.metastore import manager
from app.ui.pages.explorer import explorer_page
from app.ui.pages.job_execution import job_execution_page
from app.ui.pages.jobs import jobs_page
from app.ui.pages.query import query_workspace
from app.ui.pages.workspace import workspace_page

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

_HELPERS_DIR = Path(__file__).parent / "helpers"


def _deploy_workspace_helpers() -> None:
    """Copy all helper modules to the shared helpers directory on the data volume."""
    dest = Path(HELPERS_PATH)
    dest.mkdir(parents=True, exist_ok=True)
    for source_file in _HELPERS_DIR.glob("*.py"):
        if source_file.name != "__init__.py":
            shutil.copy(source_file, dest / source_file.name)


def startup():
    """Auto-initialize metastore and application database on startup."""
    Path(WORKSPACE_PATH).mkdir(parents=True, exist_ok=True)
    _deploy_workspace_helpers()
    try:
        manager.initialize()
    except Exception as e:
        print(f"Warning: Could not auto-initialize metastore: {e}")
    try:
        init_database()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")


app.on_startup(startup)
app.add_static_files("/static", "app/ui/static")


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
def query():
    """SQL Query Workspace."""
    query_workspace()


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


if __name__ in {"__main__", "__mp_main__"}:
    print(f"Starting DuckBricks with reload={RELOAD}...")
    ui.run(title="DuckBricks", host=HOST, port=int(PORT), reload=RELOAD)
