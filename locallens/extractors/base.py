"""Base extractor class and plugin discovery for LocalLens."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalLensExtractor(ABC):
    """Base class that all file extractors must implement.

    Built-in and third-party extractors inherit from this class.
    Third-party packages register via the ``locallens.extractors`` entry-point
    group in their ``pyproject.toml``.
    """

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return the file extensions this extractor handles (e.g. ['.txt', '.md'])."""
        ...

    @abstractmethod
    def extract(self, file_path: Path) -> str:
        """Extract text content from the given file. Return empty string on failure."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Return a human-readable name for this extractor."""
        ...

    # Legacy compat: existing code reads ``extractor.extractor_name``
    @property
    def extractor_name(self) -> str:
        return self.name()


# Keep the old Protocol around so existing duck-typed extractors still satisfy
# type checks until they are migrated.
class BaseExtractor:
    """Legacy protocol-style base kept for backward compat.

    New extractors should inherit from ``LocalLensExtractor`` instead.
    """

    extractor_name: str = "unknown"

    def extract(self, file_path: Path) -> str:  # pragma: no cover
        ...


def discover_plugins() -> dict[str, LocalLensExtractor]:
    """Scan ``locallens.extractors`` entry-point group and return a mapping
    of extension -> extractor instance for every discovered plugin.

    Built-in extractors are **not** returned here; they are registered
    separately with higher priority.
    """
    import importlib.metadata

    plugins: dict[str, LocalLensExtractor] = {}
    try:
        eps = importlib.metadata.entry_points(group="locallens.extractors")
    except TypeError:
        # Python < 3.12 compat
        eps = importlib.metadata.entry_points().get("locallens.extractors", [])

    for ep in eps:
        # Skip built-in entry points (they are handled by the registry itself)
        if ep.name.startswith("builtin_"):
            continue
        try:
            cls = ep.load()
            instance = cls()
            if not isinstance(instance, LocalLensExtractor):
                logger.warning(
                    "Plugin %s (%s) does not inherit LocalLensExtractor — skipped",
                    ep.name,
                    ep.value,
                )
                continue
            for ext in instance.supported_extensions():
                plugins[ext] = instance
            logger.info(
                "Discovered extractor plugin %r covering %s",
                instance.name(),
                ", ".join(instance.supported_extensions()),
            )
        except Exception as exc:
            logger.warning("Failed to load extractor plugin %s: %s", ep.name, exc)

    return plugins
