# Guide for AI coding agents

This project is a Linux email gateway that is itself meant to be controlled by
AI agents. The main entry points are:

- `src/linux_mail_agent/config.py` – environment-based configuration.
- `src/linux_mail_agent/mail.py` – IMAP/SMTP operations (no MCP dependency).
- `src/linux_mail_agent/server.py` – MCP tool definitions.
- `src/linux_mail_agent/cli.py` – CLI for humans and shell agents.

## Rules for agents editing this project

1. Never log, echo, or return email passwords/tokens. `public_status()` exists
   specifically to expose configuration without secrets.
2. Keep the core `mail.py` independent of MCP so it can be reused by other
   frontends (CLI, HTTP, future SDKs).
3. Tool names in `server.py` start with `mail_` and return JSON-serializable
   Python values.
4. Mail UIDs are strings from IMAP `UID SEARCH`; always use UID-based commands,
   never sequence numbers.
5. When adding a new tool, add a matching CLI subcommand only if it is useful
   for humans/scripts too.
6. Preserve read-only safety: any operation that modifies mailbox state or
   sends email must call `_ensure_writable()`.

Run tests with `make test` or `python3 -m pytest -q`.
