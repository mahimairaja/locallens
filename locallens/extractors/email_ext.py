"""Email extractor for .eml and .msg files."""

import email
import email.policy
from pathlib import Path

from rich.console import Console

from locallens.extractors.base import LocalLensExtractor

console = Console()

try:
    from oletools import oleobj  # noqa: F401 — probe import
    _oletools_available = True
except ImportError:
    _oletools_available = False


class EmailExtractor(LocalLensExtractor):
    """Extract subject, from, to, date, and body text from email files."""

    def supported_extensions(self) -> list[str]:
        exts = [".eml"]
        if _oletools_available:
            exts.append(".msg")
        return exts

    def name(self) -> str:
        return "email"

    def extract(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        if ext == ".eml":
            return self._extract_eml(file_path)
        elif ext == ".msg":
            return self._extract_msg(file_path)
        return ""

    def _extract_eml(self, file_path: Path) -> str:
        """Parse a .eml file using the stdlib email module."""
        try:
            with open(file_path, "rb") as f:
                msg = email.message_from_binary_file(f, policy=email.policy.default)

            subject = msg.get("Subject", "")
            sender = msg.get("From", "")
            to = msg.get("To", "")
            date = msg.get("Date", "")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain":
                        payload = part.get_content()
                        if isinstance(payload, str):
                            body = payload
                            break
                # Fallback: try text/html if no plain text found
                if not body:
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct == "text/html":
                            payload = part.get_content()
                            if isinstance(payload, str):
                                body = payload
                                break
            else:
                payload = msg.get_content()
                if isinstance(payload, str):
                    body = payload

            header = f"Subject: {subject} / From: {sender} / To: {to} / Date: {date}"
            return f"{header}\n\n{body}".strip()
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not extract .eml {file_path}: {exc}[/yellow]")
            return ""

    def _extract_msg(self, file_path: Path) -> str:
        """Parse a .msg file using python-oletools / extract_msg."""
        if not _oletools_available:
            console.print(
                f"[yellow]Warning: python-oletools not installed, cannot extract {file_path}[/yellow]"
            )
            return ""
        try:
            # extract_msg is the most common .msg parser that uses oletools
            import extract_msg  # type: ignore[import-untyped]

            msg = extract_msg.Message(str(file_path))
            subject = msg.subject or ""
            sender = msg.sender or ""
            to = msg.to or ""
            date = msg.date or ""
            body = msg.body or ""
            msg.close()

            header = f"Subject: {subject} / From: {sender} / To: {to} / Date: {date}"
            return f"{header}\n\n{body}".strip()
        except ImportError:
            # Fallback: try olefile-based manual extraction
            try:
                import olefile  # type: ignore[import-untyped]

                ole = olefile.OleFileIO(str(file_path))
                subject = ""
                sender = ""
                body = ""
                if ole.exists("__substg1.0_0037001F"):
                    subject = ole.openstream("__substg1.0_0037001F").read().decode("utf-16-le", errors="replace")
                if ole.exists("__substg1.0_0C1A001F"):
                    sender = ole.openstream("__substg1.0_0C1A001F").read().decode("utf-16-le", errors="replace")
                if ole.exists("__substg1.0_1000001F"):
                    body = ole.openstream("__substg1.0_1000001F").read().decode("utf-16-le", errors="replace")
                ole.close()

                header = f"Subject: {subject} / From: {sender}"
                return f"{header}\n\n{body}".strip()
            except Exception as exc:
                console.print(f"[yellow]Warning: Could not extract .msg {file_path}: {exc}[/yellow]")
                return ""
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not extract .msg {file_path}: {exc}[/yellow]")
            return ""
