"""Configuration loading and validation.

The agent is intentionally configured through environment variables (or an
optional .env file), because that is the most portable way to run it as an
MCP stdio server under systemd, Docker, or an AI agent sandbox.

All secrets stay in environment variables; this module never prints passwords.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is a dependency
    _load_dotenv = None

ENV_PREFIX = "MAIL_"
DEFAULT_ATTACHMENT_DIR = Path(
    os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
) / "linux-mail-agent" / "attachments"


def _env_bool(value: Optional[str], default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


@dataclass(slots=True)
class MailConfig:
    """Connection settings for one IMAP/SMTP account."""

    imap_host: str
    imap_user: str
    imap_password: str
    imap_port: int = 993
    imap_ssl: bool = True

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_ssl: bool = False
    smtp_starttls: bool = True

    from_addr: Optional[str] = None
    from_name: Optional[str] = None

    timeout: float = 30.0
    attachment_dir: Path = DEFAULT_ATTACHMENT_DIR
    read_only: bool = False
    allowed_to: Optional[tuple[str, ...]] = None

    # The MCP server connects lazily per tool call, so configuration changes
    # in the environment take effect without restarting the agent process.
    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "MailConfig":
        env = dict(os.environ if env is None else env)

        def get(name: str, default: Optional[str] = None) -> Optional[str]:
            return env.get(f"{ENV_PREFIX}{name}", default)

        smtp_host = get("SMTP_HOST") or None
        imap_host = get("IMAP_HOST")
        imap_user = get("IMAP_USER")
        imap_password = get("IMAP_PASSWORD")

        if not imap_host or not imap_user or not imap_password:
            raise ValueError(
                "MAIL_IMAP_HOST, MAIL_IMAP_USER and MAIL_IMAP_PASSWORD are required. "
                "See README.md for configuration."
            )

        return cls(
            imap_host=imap_host,
            imap_user=imap_user,
            imap_password=imap_password,
            imap_port=int(get("IMAP_PORT", "993")),
            imap_ssl=_env_bool(get("IMAP_SSL"), True),
            smtp_host=smtp_host,
            smtp_port=int(get("SMTP_PORT", "465" if _env_bool(get("SMTP_SSL"), False) else "587")),
            smtp_ssl=_env_bool(get("SMTP_SSL"), False),
            smtp_starttls=_env_bool(get("SMTP_STARTTLS"), True),
            from_addr=get("FROM") or imap_user,
            from_name=get("FROM_NAME") or "",
            timeout=float(get("TIMEOUT", "30")),
            attachment_dir=Path(get("ATTACHMENT_DIR", str(DEFAULT_ATTACHMENT_DIR))),
            read_only=_env_bool(get("READ_ONLY"), False),
            allowed_to=(
                tuple(a.strip() for a in get("ALLOWED_TO", "").split(",") if a.strip())
                if get("ALLOWED_TO")
                else None
            ),
        )

    @property
    def effective_smtp_host(self) -> str:
        return self.smtp_host or self.imap_host

    @property
    def effective_from(self) -> str:
        return self.from_addr or self.imap_user

    def require_smtp(self) -> None:
        # SMTP may explicitly use MAIL_SMTP_HOST, otherwise it defaults to the
        # IMAP host (effective_smtp_host). A no-op here keeps send operations
        # possible with a single host; use MAIL_READ_ONLY=true to forbid them.
        return None

    def public_status(self) -> dict:
        """Non-secret status useful to an AI agent."""
        return {
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "imap_ssl": self.imap_ssl,
            "smtp_host": self.effective_smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_ssl": self.smtp_ssl,
            "smtp_starttls": self.smtp_starttls,
            "from": self.effective_from,
            "from_name": self.from_name,
            "timeout": self.timeout,
            "attachment_dir": str(self.attachment_dir),
            "read_only": self.read_only,
            "allowed_to": list(self.allowed_to) if self.allowed_to else None,
            "configured": True,
        }


def load_dotenv(path: Optional[str] = None) -> None:
    """Load .env if present; missing file is not an error."""
    if _load_dotenv is None:
        return
    if path is not None:
        _load_dotenv(path, override=False)
        return
    # Prefer ./.env, fall back to the user config path.
    for candidate in (Path(".env"), Path.home() / ".config" / "linux-mail-agent" / ".env"):
        if candidate.exists():
            _load_dotenv(candidate, override=False)
            break


def load_config(env_file: Optional[str] = None) -> MailConfig:
    load_dotenv(env_file)
    return MailConfig.from_env()
