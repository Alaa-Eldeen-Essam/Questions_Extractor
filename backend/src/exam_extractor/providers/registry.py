"""Small explicit provider registry.

Dynamic packaging entry points can be added later if third-party plugins are
needed. An explicit registry keeps Phase 0 easy to understand and test.
"""

from typing import Any


class ProviderRegistry:
    """Register and resolve providers by capability and name."""

    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Any]] = {}

    def register(self, category: str, name: str, provider: Any) -> None:
        """Register one provider under a category and stable name."""
        self._providers.setdefault(category, {})[name] = provider

    def get(self, category: str, name: str) -> Any:
        """Return a provider or raise a clear lookup error."""
        try:
            return self._providers[category][name]
        except KeyError as exc:
            available = sorted(self._providers.get(category, {}))
            raise KeyError(
                f"Unknown {category} provider {name!r}; available: {available}"
            ) from exc

    def names(self, category: str) -> tuple[str, ...]:
        """Return registered provider names for a category."""
        return tuple(sorted(self._providers.get(category, {})))
