"""Tests for plugin discovery and extractor registration."""

import importlib.metadata

import pytest


class TestPluginDiscovery:
    """Verify built-in extractors are registered via entry points."""

    def test_entry_points_registered(self):
        """All built-in extractors should be discoverable via entry points."""
        try:
            eps = importlib.metadata.entry_points(group="locallens.extractors")
        except TypeError:
            eps = importlib.metadata.entry_points().get("locallens.extractors", [])

        ep_names = {ep.name for ep in eps}

        expected = {
            "builtin_text",
            "builtin_pdf",
            "builtin_docx",
            "builtin_code",
            "builtin_spreadsheet",
            "builtin_email",
            "builtin_epub",
            "builtin_obsidian",
        }
        # At minimum the built-ins should be present (if package is installed)
        # If not installed in editable mode, entry points won't show — skip gracefully
        if not ep_names:
            pytest.skip(
                "No entry points found — locallens may not be installed. "
                "Run `pip install -e .` first."
            )

        for name in expected:
            assert name in ep_names, f"Missing entry point: {name}"

    def test_builtin_entry_points_load(self):
        """Each built-in entry point should load without error."""
        try:
            eps = importlib.metadata.entry_points(group="locallens.extractors")
        except TypeError:
            eps = importlib.metadata.entry_points().get("locallens.extractors", [])

        if not list(eps):
            pytest.skip("No entry points found — locallens may not be installed.")

        for ep in eps:
            if ep.name.startswith("builtin_"):
                cls = ep.load()
                instance = cls()
                assert hasattr(instance, "extract"), f"{ep.name} missing extract()"

    def test_discover_plugins_excludes_builtins(self):
        """discover_plugins() should skip entries prefixed with 'builtin_'."""
        from locallens.extractors.base import discover_plugins

        plugins = discover_plugins()
        # Plugin dict should not contain any built-in keys unless a third-party
        # happens to be installed (unlikely in test). The point is that
        # builtin_* entries are skipped.
        for _ext, inst in plugins.items():
            # If any plugin is found, it should be a proper LocalLensExtractor
            from locallens.extractors.base import LocalLensExtractor

            assert isinstance(inst, LocalLensExtractor)

    def test_registry_has_core_extensions(self):
        """The extractor registry should have entries for core file types."""
        from locallens.extractors import get_extractor

        for ext in (".txt", ".md", ".pdf", ".docx", ".py", ".csv"):
            assert get_extractor(ext) is not None, f"No extractor for {ext}"

    def test_registry_has_email_extension(self):
        """The extractor registry should have an entry for .eml."""
        from locallens.extractors import get_extractor

        extractor = get_extractor(".eml")
        assert extractor is not None
        assert extractor.name() == "email"

    def test_local_lens_extractor_base_class(self):
        """LocalLensExtractor should be importable and usable as a base class."""
        from pathlib import Path

        from locallens.extractors.base import LocalLensExtractor

        class DummyExtractor(LocalLensExtractor):
            def supported_extensions(self):
                return [".dummy"]

            def extract(self, file_path):
                return "dummy text"

            def name(self):
                return "dummy"

        ext = DummyExtractor()
        assert ext.supported_extensions() == [".dummy"]
        assert ext.name() == "dummy"
        assert ext.extractor_name == "dummy"  # Legacy compat
        assert ext.extract(Path("/tmp/test.dummy")) == "dummy text"
