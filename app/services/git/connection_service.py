"""CRUD and validation service for git provider connections."""

from __future__ import annotations

import logging

from app.services.database.models.app import GitConnection
from app.services.database.session import get_session
from app.services.git.encryption import TokenEncryptor
from app.services.git.providers.base import GitProvider, Repository
from app.services.git.providers.factory import GitProviderFactory

_log = logging.getLogger(__name__)


class GitConnectionService:
    """Manages stored git connections, including encrypted token storage."""

    def create(
        self, name: str, provider_type: str, token: str, host: str | None = None
    ) -> GitConnection:
        """Persist a new git connection with the token encrypted at rest."""
        with get_session() as session:
            connection = GitConnection(
                name=name,
                provider_type=provider_type,
                host=host,
                token_encrypted=TokenEncryptor.encrypt(token),
            )
            session.add(connection)
            session.flush()
            session.refresh(connection)
            session.expunge(connection)
            return connection

    def list_all(self) -> list[GitConnection]:
        """Return all stored connections, detached from the session."""
        with get_session() as session:
            connections: list[GitConnection] = (
                session.query(GitConnection).order_by(GitConnection.name).all()
            )
            for c in connections:
                session.expunge(c)
            return connections

    def get(self, connection_id: int) -> GitConnection:
        """Return a single connection by ID."""
        with get_session() as session:
            connection: GitConnection | None = (
                session.query(GitConnection).filter_by(id=connection_id).first()
            )
            if connection is None:
                raise ValueError(f"GitConnection {connection_id} not found.")
            session.expunge(connection)
            return connection

    def delete(self, connection_id: int) -> None:
        """Delete a connection and all its associated git folders (cascade)."""
        with get_session() as session:
            connection = session.query(GitConnection).filter_by(id=connection_id).first()
            if connection is None:
                raise ValueError(f"GitConnection {connection_id} not found.")
            session.delete(connection)

    def build_provider(self, connection: GitConnection) -> GitProvider:
        """Decrypt the token and instantiate the appropriate provider."""
        token = TokenEncryptor.decrypt(connection.token_encrypted)
        return GitProviderFactory.build(connection.provider_type, token, connection.host)

    def test_connection(self, connection_id: int) -> bool:
        """Return True if the stored credentials are still valid."""
        connection = self.get(connection_id)
        provider = self.build_provider(connection)
        return provider.validate()

    def list_repositories(self, connection_id: int) -> list[Repository]:
        """Return repositories available through the given connection."""
        connection = self.get(connection_id)
        provider = self.build_provider(connection)
        return provider.list_repositories()
