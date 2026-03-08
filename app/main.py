"""DuckBricks — NiceGUI application entry point."""
import os

from nicegui import app, ui

from app.config import CATALOG_PATH, HOST, PORT
from app.pages.explorer import explorer_page
from app.pages.query import query_workspace
from app.services.ducklake import manager


def startup():
    """Auto-initialize metastore on startup if catalog already exists."""
    if os.path.exists(CATALOG_PATH):
        try:
            manager.initialize()
        except Exception as e:
            print(f"Warning: Could not auto-attach existing metastore: {e}")


app.on_startup(startup)


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


if __name__ == "__main__":
    ui.run(title="DuckBricks", host=HOST, port=int(PORT), reload=False)
