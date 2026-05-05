"""Factory that resolves a GitProvider from a provider type string and credentials."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.git.providers.base import GitProvider
from app.services.git.providers.github import GitHubPatProvider


@runtime_checkable
class _ProviderConstructor(Protocol):
    def __call__(self, token: str, host: str | None = None) -> GitProvider: ...


_REGISTRY: dict[str, _ProviderConstructor] = {
    "github": GitHubPatProvider,  # type: ignore[dict-item]
}


class GitProviderFactory:
    """Maps provider type identifiers to their concrete provider implementations."""

    @staticmethod
    def build(provider_type: str, token: str, host: str | None = None) -> GitProvider:
        """Instantiate the correct provider for the given type.

        Raises ValueError for unknown provider types so callers get a clear
        message rather than an AttributeError deep in the stack.
        """
        constructor = _REGISTRY.get(provider_type)
        if constructor is None:
            supported = sorted(_REGISTRY.keys())
            raise ValueError(
                f"Unknown provider type '{provider_type}'. Supported: {supported}"
            )
        return constructor(token=token, host=host)

    @staticmethod
    def supported_types() -> list[str]:
        """Return the list of registered provider type identifiers."""
        return sorted(_REGISTRY.keys())
