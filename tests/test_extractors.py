"""Unit tests for individual extractors (email, epub, obsidian)."""

import tempfile
from pathlib import Path

import pytest


class TestEmailExtractor:
    """Test the EmailExtractor on .eml files."""

    def test_extract_eml(self):
        from locallens.extractors.email_ext import EmailExtractor

        ext = EmailExtractor()
        assert ".eml" in ext.supported_extensions()

        # Write a test .eml
        with tempfile.NamedTemporaryFile(suffix=".eml", mode="w", delete=False, encoding="utf-8") as f:
            f.write(
                "From: sender@test.com\r\n"
                "To: receiver@test.com\r\n"
                "Subject: Test Subject\r\n"
                "Date: Tue, 15 Apr 2026 12:00:00 +0000\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n"
                "\r\n"
                "This is the email body.\r\n"
            )
            tmp_path = Path(f.name)

        try:
            text = ext.extract(tmp_path)
            assert "Test Subject" in text
            assert "sender@test.com" in text
            assert "receiver@test.com" in text
            assert "email body" in text
        finally:
            tmp_path.unlink(missing_ok=True)


class TestObsidianExtractor:
    """Test the ObsidianExtractor for frontmatter stripping and wikilink resolution."""

    def test_strip_frontmatter(self):
        from locallens.extractors.obsidian_ext import _strip_frontmatter

        text = "---\ntitle: Test\ntags: [a, b]\n---\n# Heading\nBody text"
        result = _strip_frontmatter(text)
        assert "---" not in result
        assert "# Heading" in result
        assert "Body text" in result

    def test_resolve_wikilinks(self):
        from locallens.extractors.obsidian_ext import _resolve_wikilinks

        text = "See [[My Page]] and [[Other|display text]] for details."
        result = _resolve_wikilinks(text)
        assert "[[" not in result
        assert "My Page" in result
        assert "display text" in result
        assert "Other" not in result  # replaced by display text

    def test_obsidian_vault_detection(self, tmp_path):
        """Files under a directory with .obsidian should be detected as vault files."""
        from locallens.extractors.obsidian_ext import _is_obsidian_vault

        # Create a fake vault structure
        vault_dir = tmp_path / "my_vault"
        vault_dir.mkdir()
        (vault_dir / ".obsidian").mkdir()
        note = vault_dir / "note.md"
        note.write_text("# Test note\n\nHello world")

        assert _is_obsidian_vault(note) is True

        # File outside vault
        outside = tmp_path / "outside.md"
        outside.write_text("# Not a vault note")
        assert _is_obsidian_vault(outside) is False

    def test_obsidian_extractor_full(self, tmp_path):
        """Full extraction pipeline for an Obsidian vault file."""
        from locallens.extractors.obsidian_ext import ObsidianExtractor

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        (vault_dir / ".obsidian").mkdir()
        note = vault_dir / "note.md"
        note.write_text(
            "---\ntitle: Test\n---\n"
            "# Heading\n\n"
            "This links to [[Another Page]] and [[Page|alias]].\n"
        )

        ext = ObsidianExtractor()
        assert ext.can_handle(note) is True

        text = ext.extract(note)
        assert "title:" not in text  # Frontmatter stripped
        assert "---" not in text
        assert "Another Page" in text  # Wikilink resolved
        assert "alias" in text  # Display text used
        assert "[[" not in text  # No raw wikilinks remain


class TestEpubExtractor:
    """Test the EpubExtractor availability check."""

    def test_epub_extractor_import(self):
        """EpubExtractor should be importable regardless of ebooklib availability."""
        from locallens.extractors.epub_ext import EpubExtractor

        ext = EpubExtractor()
        assert ext.name() == "epub"
        # If ebooklib is not installed, supported_extensions returns empty
        exts = ext.supported_extensions()
        assert isinstance(exts, list)
