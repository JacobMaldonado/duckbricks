"""Job Execution Detail page — redirects to the Jobs page.

Run history is now served directly from Prefect via the Jobs page.
"""

from nicegui import ui

from app.ui.components.layout import layout_frame


def job_execution_page(execution_id: int) -> None:
    """Show a redirect notice for legacy execution URLs."""
    layout_frame("Jobs")
    with ui.column().classes("w-full h-full items-center justify-center p-8 gap-4"):
        ui.icon("info", size="xl", color="primary")
        ui.label("Run history has moved").classes("text-h5 text-weight-bold")
        ui.label(
            "Job execution details are now available directly in the Prefect UI. "
            "Use the 'Run history' button on any job to view its Prefect flow runs."
        ).classes("text-grey-7 text-center").style("max-width: 480px")
        ui.button("Go to Jobs", on_click=lambda: ui.navigate.to("/jobs")).props("color=primary")
