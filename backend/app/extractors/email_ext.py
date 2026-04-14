"""Email extractor for .eml and .msg files."""

import email
import email.policy
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from oletools import oleobj  # noqa: F401 — probe import
    _oletools_available = True
except ImportError:
    _oletools_available = False


class EmailExtractor:
    """Extract subject, from, to, date, and body text from email files."""

    extractor_name = "email"

    def extract(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        if ext == ".eml":
            return self._extract_eml(file_path)
        elif ext == ".msg":
            return self._extract_msg(file_path)
        return ""

    def _extract_eml(self, file_path: Path) -> str:
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
            logger.warning("Could not extract .eml %s: %s", file_path, exc)
            return ""

    def _extract_msg(self, file_path: Path) -> str:
        if not _oletools_available:
            logger.warning("python-oletools not installed, cannot extract %s", file_path)
            return ""
        try:
            import extract_msg

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
            try:
                import olefile

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
                logger.warning("Could not extract .msg %s: %s", file_path, exc)
                return ""
        except Exception as exc:
            logger.warning("Could not extract .msg %s: %s", file_path, exc)
            return ""
