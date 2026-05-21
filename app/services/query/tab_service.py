"""CRUD service for persistent SQL editor tabs."""

from __future__ import annotations

from app.services.database.models.app import QueryTab
from app.services.database.session import get_session


class QueryTabService:
    """Manages the lifecycle of named, persisted query editor tabs."""

    _DEFAULT_TAB_NAME = "Query 1"

    def ensure_default(self) -> QueryTab:
        """Return the first tab if any exist, or seed a default one."""
        tabs = self.list_tabs()
        if tabs:
            return tabs[0]
        return self.create_tab(self._DEFAULT_TAB_NAME)

    def list_tabs(self) -> list[QueryTab]:
        """Return all tabs ordered by position."""
        with get_session() as session:
            tabs: list[QueryTab] = (
                session.query(QueryTab).order_by(QueryTab.position, QueryTab.id).all()
            )
            for tab in tabs:
                session.expunge(tab)
            return tabs

    def create_tab(self, name: str, sql_content: str = "") -> QueryTab:
        """Append a new tab at the end of the list."""
        with get_session() as session:
            next_position = session.query(QueryTab).count()
            tab = QueryTab(name=name, sql_content=sql_content, position=next_position)
            session.add(tab)
            session.flush()
            session.refresh(tab)
            session.expunge(tab)
            return tab

    def update_content(self, tab_id: int, sql_content: str) -> None:
        """Persist the SQL content for a tab."""
        with get_session() as session:
            tab = session.query(QueryTab).filter_by(id=tab_id).first()
            if tab is None:
                raise ValueError(f"Tab {tab_id} not found")
            tab.sql_content = sql_content

    def rename_tab(self, tab_id: int, name: str) -> None:
        """Update the display name of a tab."""
        name = name.strip()
        if not name:
            raise ValueError("Tab name cannot be empty")
        with get_session() as session:
            tab = session.query(QueryTab).filter_by(id=tab_id).first()
            if tab is None:
                raise ValueError(f"Tab {tab_id} not found")
            tab.name = name

    def delete_tab(self, tab_id: int) -> None:
        """Remove a tab. Raises if it is the last remaining tab."""
        with get_session() as session:
            total = session.query(QueryTab).count()
            if total <= 1:
                raise ValueError("Cannot close the last query tab")
            tab = session.query(QueryTab).filter_by(id=tab_id).first()
            if tab is None:
                raise ValueError(f"Tab {tab_id} not found")
            session.delete(tab)
