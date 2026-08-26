"""Live Mermaid preview for DuckBricks job definitions."""

from __future__ import annotations

import html
from collections.abc import Sequence
from pathlib import Path

from nicegui import ui

from app.services.jobs.models import JobTaskInput


class JobFlowDiagram:
    """Builds and renders a read-only flowchart from editor task dependencies."""

    @classmethod
    def render(cls, tasks: Sequence[JobTaskInput]) -> None:
        if not tasks:
            with ui.column().classes("w-full items-center justify-center q-pa-xl gap-2"):
                ui.icon("account_tree", color="grey-5", size="42px")
                ui.label("Add a task to begin the flow").classes("text-grey-7")
            return
        ui.mermaid(
            cls.build_mermaid(tasks),
            config={
                "theme": "base",
                "flowchart": {"curve": "basis", "htmlLabels": True},
                "themeVariables": {
                    "primaryColor": "#E3F2FD",
                    "primaryBorderColor": "#1976D2",
                    "lineColor": "#78909C",
                    "fontFamily": "Roboto, sans-serif",
                },
            },
        ).classes("w-full")

    @classmethod
    def build_mermaid(cls, tasks: Sequence[JobTaskInput]) -> str:
        node_id_by_key = {task.key: f"task_{index}" for index, task in enumerate(tasks)}
        lines = ["flowchart LR"]
        for task in tasks:
            node_id = node_id_by_key[task.key]
            label = cls._escape_label(task.name or "Unnamed task")
            source = cls._escape_label(Path(task.file_path).name) if task.file_path else "No file"
            lines.append(f'    {node_id}["<b>{label}</b><br/><small>{source}</small>"]')
        for task in tasks:
            for dependency_key in task.depends_on:
                if dependency_key in node_id_by_key:
                    lines.append(
                        f"    {node_id_by_key[dependency_key]} --> {node_id_by_key[task.key]}"
                    )
        lines.append("    classDef default fill:#E3F2FD,stroke:#1976D2,color:#212121")
        return "\n".join(lines)

    @staticmethod
    def _escape_label(value: str) -> str:
        return html.escape(value, quote=True).replace("\n", " ")
