# linux-mail-agent

**Linux email gateway for AI agents** — read, search, send, reply, forward,
move and delete email over IMAP/SMTP from the command line or through
[Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

`linux-mail-agent` is designed to be **controlled by an AI agent** as easily as
by a human. It exposes the same operations as:

- an **MCP server** (stdio / SSE / HTTP) that LLM tools can call natively, and
- a **JSON-first CLI** that shell agents, cron jobs, and humans can use.

It is built with only the Python standard library plus `mcp` and
`python-dotenv`, and runs on any modern Linux distribution.

---

## Why this project?

AI agents increasingly need to interact with email: notify someone, read a
confirmation code, summarize an inbox, find an attachment, or reply to a
thread. Most email protocols (IMAP/SMTP) are low-level and not agent-friendly.

`linux-mail-agent` turns a mailbox into **a small set of high-level, typed
tools**:

```
mail_check_config   mail_list_folders  mail_list      mail_search
mail_read           mail_send          mail_reply     mail_forward
mail_mark_seen      mail_mark_unseen   mail_move      mail_delete
mail_save_attachment
```

An agent does not need to know IMAP sequence numbers, MIME parsing, TLS setup,
or SMTP envelope details. It calls `mail_list("INBOX", limit=10)`, sees UIDs,
then `mail_read("INBOX", "42")`.

---

## Features

- **MCP native**: every operation is an MCP tool with typed arguments and
  JSON results.
- **CLI + JSON**: human-friendly subcommands output JSON for scripting.
- **IMAP reading**: list folders, list/search messages, read full messages,
  save attachments, mark read/unread, move, delete.
- **SMTP sending**: plain text and HTML email, CC/BCC, local attachments,
  reply and forward with correct `In-Reply-To` / `References` headers.
- **Secure defaults**: IMAPS by default, SMTP STARTTLS or implicit SSL,
  configurable timeouts, no secrets in tool output.
- **Read-only mode**: `MAIL_READ_ONLY=true` blocks every mutating operation,
  useful when you let an agent read a real mailbox but not change it.
- **No vendor lock-in**: plain IMAP/SMTP works with Gmail, Outlook/Office 365,
  QQ Mail, 163, Fastmail, self-hosted Dovecot/Postfix, etc. (app passwords may
  be required by providers).

---

## Project layout

```text
linux-mail-agent/
├── pyproject.toml          # Python package metadata + entry point
├── Dockerfile              # container image (SSE/HTTP or isolated stdio)
├── Makefile
├── README.md
├── AGENTS.md               # guide for AI coding agents
├── .env.example
├── src/linux_mail_agent/
│   ├── config.py           # environment-based configuration
│   ├── mail.py             # IMAP/SMTP core, independent of MCP
│   ├── server.py           # MCP server/tool definitions
│   ├── cli.py              # CLI subcommands
│   └── text.py             # email body/preview utilities
└── tests/
```

The core (`mail.py`) has no MCP dependency, so it can be reused by other
frontends (HTTP API, SDKs, custom agents).

---

## Requirements

- Linux (or any POSIX system; Windows is not a target)
- Python **3.10+**
- An email account with IMAP enabled and (for sending) SMTP enabled
- For AI-agent use: an MCP client (Claude Desktop, Cursor, VS Code, custom
  agent harness, etc.)

---

## Installation

### From source

```bash
git clone https://github.com/ASAKAFENG/linux-mail-agent.git
cd linux-mail-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"     # installs CLI + dev dependencies
```

### From PyPI (once published)

```bash
pip install linux-mail-agent
```

### Verify

```bash
mailagent --help
```

---

## Configuration

Configuration is intentionally environment-based: portable across systemd,
Docker, and MCP clients.

Copy the example file and edit it:

```bash
cp .env.example .env
```

Then either `source .env` or run commands from the directory so the `.env`
file is auto-loaded. A global config path is also supported:
`~/.config/linux-mail-agent/.env`.

### Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MAIL_IMAP_HOST` | ✅ | – | IMAP server, e.g. `imap.gmail.com` |
| `MAIL_IMAP_USER` | ✅ | – | Full email address / login name |
| `MAIL_IMAP_PASSWORD` | ✅ | – | Password or app-specific password |
| `MAIL_IMAP_PORT` | | `993` | IMAP port |
| `MAIL_IMAP_SSL` | | `true` | Use implicit TLS for IMAP |
| `MAIL_SMTP_HOST` | | IMAP host | SMTP server, e.g. `smtp.gmail.com` |
| `MAIL_SMTP_PORT` | | `587` (or `465` if SSL) | SMTP port |
| `MAIL_SMTP_SSL` | | `false` | Use implicit TLS for SMTP (`465`) |
| `MAIL_SMTP_STARTTLS` | | `true` | Use STARTTLS for SMTP (`587`) |
| `MAIL_FROM` | | IMAP user | From address if different from login |
| `MAIL_FROM_NAME` | | empty | Display name in From header |
| `MAIL_TIMEOUT` | | `30` | Network timeout in seconds |
| `MAIL_ATTACHMENT_DIR` | | `~/.local/share/linux-mail-agent/attachments` | Where saved attachments go |
| `MAIL_READ_ONLY` | | `false` | Block all mutating operations |
| `MAIL_ALLOWED_TO` | | unset | Comma-separated recipient allowlist; when set, `send`/`reply`/`forward` refuse any recipient not listed |

> **Never commit `.env`.** The `.gitignore` already excludes it.

### Example `.env`

```dotenv
MAIL_IMAP_HOST=imap.gmail.com
MAIL_IMAP_PORT=993
MAIL_IMAP_SSL=true
MAIL_IMAP_USER=you@gmail.com
MAIL_IMAP_PASSWORD=your-app-password

MAIL_SMTP_HOST=smtp.gmail.com
MAIL_SMTP_PORT=587
MAIL_SMTP_SSL=false
MAIL_SMTP_STARTTLS=true

MAIL_FROM=you@gmail.com
MAIL_FROM_NAME="ASAKAFENG"
```

### Provider notes

- **Gmail / Google Workspace**: enable 2-Step Verification and create an
  [App Password](https://support.google.com/accounts/answer/185833).
- **Outlook / Office 365**: enable IMAP/SMTP and use an app password if MFA is
  enabled.
- **QQ Mail / 163 Mail**: enable IMAP/SMTP in account settings and use the
  authorization code as the password.
- **Self-hosted**: works with Dovecot + Postfix; adjust ports/TLS flags.

---

## Quick start

```bash
# 1. Configure
cp .env.example .env
# edit .env

# 2. Check configuration (no secrets are printed)
mailagent check

# 3. List mailboxes
mailagent folders

# 4. List the 10 most recent emails in INBOX
mailagent list --mailbox INBOX --limit 10

# 5. Read an email (use the uid from list output)
mailagent show INBOX 12345

# 6. Search
mailagent search "invoice" --limit 5

# 7. Send
mailagent send --to "alice@example.com" --subject "Hello" --body "Hi Alice"
```

All commands output JSON, so you can pipe them:

```bash
mailagent list --unseen-only --limit 5 | jq '.[] | {uid, subject, from}'
```

---

## CLI reference

Global option: `--env-file PATH` loads a specific `.env` file.

| Command | Description | Example |
| --- | --- | --- |
| `serve` | Run MCP server (`--transport stdio|sse|streamable-http`) | `mailagent serve` |
| `check` | Print non-secret config status | `mailagent check` |
| `folders` | List mailboxes | `mailagent folders` |
| `list` | List emails | `mailagent list --mailbox INBOX --limit 10 --unseen-only` |
| `search` | Free-text search subject/body | `mailagent search "invoice"` |
| `show` | Read full email | `mailagent show INBOX 12345` |
| `send` | Send email | `mailagent send --to a@x.com --subject Hi --body Hello` |
| `reply` | Reply to a UID | `mailagent reply INBOX 12345 --body "Thanks!"` |
| `forward` | Forward a UID | `mailagent forward INBOX 12345 --to b@x.com --body FYI` |
| `mark-seen` | Mark read | `mailagent mark-seen INBOX 12345` |
| `mark-unseen` | Mark unread | `mailagent mark-unseen INBOX 12345` |
| `move` | Move to another mailbox | `mailagent move INBOX 12345 Archive` |
| `delete` | Delete/expunge | `mailagent delete INBOX 12345` |
| `attachment` | Save attachment to disk | `mailagent attachment INBOX 12345 --index 0` |

Send supports `--cc`, `--bcc`, `--html`, `--attachment` (repeatable), and
`--reply-to`.

```bash
mailagent send \
  --to "alice@example.com,bob@example.com" \
  --cc "team@example.com" \
  --subject "Report" \
  --body "See attached." \
  --html "<p>See attached.</p>" \
  --attachment ./report.pdf
```

---

## Using it with AI agents (MCP)

### 1. Start the MCP server

For most MCP clients, use **stdio**:

```bash
mailagent serve
```

The server stays alive on stdin/stdout and speaks MCP JSON-RPC. For remote or
web-based agents you can also use SSE or streamable HTTP:

```bash
mailagent serve --transport sse
# or
mailagent serve --transport streamable-http
```

### 2. Register in an MCP client

**Claude Desktop / Claude Code / Cursor / similar** — add a local MCP server:

```json
{
  "mcpServers": {
    "linux-mail-agent": {
      "command": "/absolute/path/to/.venv/bin/mailagent",
      "args": ["serve"],
      "env": {
        "MAIL_IMAP_HOST": "imap.gmail.com",
        "MAIL_IMAP_USER": "you@gmail.com",
        "MAIL_IMAP_PASSWORD": "your-app-password",
        "MAIL_SMTP_HOST": "smtp.gmail.com",
        "MAIL_SMTP_PORT": "587"
      }
    }
  }
}
```

> The `env` block is only for clients that support passing environment
> variables to local MCP servers. Otherwise export the variables in the shell
> that launches the client, or use a wrapper script that loads `.env`.

**Wrapper script** (`mailagent-mcp.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/you/linux-mail-agent
set -a; source .env; set +a
exec /home/you/linux-mail-agent/.venv/bin/mailagent serve
```

### 3. Tools exposed to the agent

| Tool | What the agent can do |
| --- | --- |
| `mail_check_config` | Verify the account is configured; see read-only status |
| `mail_list_folders` | List all IMAP folders |
| `mail_list` | List recent messages with UID, subject, from, date, flags, preview |
| `mail_search` | Free-text search subject/body |
| `mail_read` | Read full text/HTML body and attachment metadata |
| `mail_send` | Send a new email with optional HTML and local attachments |
| `mail_reply` | Reply to an email, preserving threading headers |
| `mail_forward` | Forward an email |
| `mail_mark_seen` / `mail_mark_unseen` | Change read state |
| `mail_move` | Move an email to another folder |
| `mail_delete` | Delete an email |
| `mail_save_attachment` | Save an attachment to disk and return its path |

Example agent flow:

1. `mail_list("INBOX", limit=10, unseen_only=True)`
2. `mail_read("INBOX", "12345")`
3. `mail_reply("INBOX", "12345", body="Thanks, I will review it today.")`

All UIDs returned by `mail_list` / `mail_search` are IMAP UIDs and stable for
the lifetime of the message. Always pass them back to `mail_read`,
`mail_move`, etc.

### 4. Read-only mode for untrusted agents

If you want an agent to **read but never modify/send**, set:

```dotenv
MAIL_READ_ONLY=true
```

Then `mail_send`, `mail_reply`, `mail_forward`, `mail_mark_*`, `mail_move`,
and `mail_delete` fail with a clear error.

---

## Security and safety

- **Use app-specific passwords.** Avoid your main account password. Many
  providers support app passwords; use them.
- **Do not print secrets.** The server and CLI never return the password.
  `mail_check_config` only reports non-secret status.
- **Least privilege.** For a dedicated agent mailbox, create a separate email
  account with restricted access if your provider supports it.
- **Start read-only.** Use `MAIL_READ_ONLY=true` while testing, then grant
  write access only after you trust the agent.
- **Recipient allowlist.** Set `MAIL_ALLOWED_TO` to a comma-separated list of
  addresses when you want an agent to be able to write only to specific people.
  `mail_send`, `mail_reply` and `mail_forward` then refuse any recipient
  outside the list (including CC/BCC), even if the agent is instructed
  otherwise. Leave unset for unrestricted sending.
- **Sandbox the process.** Run under a dedicated Unix user, container, or
  systemd service with `NoNewPrivileges=true`, `PrivateTmp=true`, etc.
- **Network egress is real.** Deleting and sending are irreversible from the
  agent's perspective. Build your own confirmation/approval layer around MCP if
  you connect an autonomous agent to a production mailbox.
- **Attachments are files.** `mail_save_attachment` writes to
  `MAIL_ATTACHMENT_DIR`; keep that directory private if emails contain
  sensitive data.

---

## Running as a systemd service (MCP over SSE/HTTP)

For a persistent remote MCP endpoint:

```ini
# /etc/systemd/system/linux-mail-agent.service
[Unit]
Description=linux-mail-agent MCP server
After=network-online.target

[Service]
User=mailagent
WorkingDirectory=/opt/linux-mail-agent
EnvironmentFile=/opt/linux-mail-agent/.env
ExecStart=/opt/linux-mail-agent/.venv/bin/mailagent serve --transport streamable-http
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now linux-mail-agent
```

---

## Running with Docker

```bash
docker build -t linux-mail-agent .
docker run --rm \
  --env-file .env \
  -p 8000:8000 \
  linux-mail-agent serve --transport streamable-http
```

> The stdio transport is usually better run on the host; the container image
> is mainly useful for SSE/HTTP or sandboxing.

---

## Development

```bash
make dev        # editable install with dev dependencies
make test       # run pytest
make build      # build a wheel
```

Run the full test suite:

```bash
python3 -m pytest -q
```

Current tests cover configuration parsing, date/search criteria, HTML-to-text
conversion, MIME body extraction, MCP tool registration, and read-only safety.

### Adding a new email operation

1. Add the operation to `mail.py` (keep it MCP-free).
2. Add an `@mcp.tool()` wrapper in `server.py`.
3. If useful for humans, add a CLI subcommand in `cli.py`.
4. Add tests and run `make test`.

See `AGENTS.md` for the full agent-editing guide.

---

## Troubleshooting

| Problem | Likely fix |
| --- | --- |
| `MAIL_IMAP_HOST ... required` | `.env` not loaded; `cd` to project dir or use `--env-file` |
| `IMAP connection failed` | Check host/port, TLS flag, network, firewall |
| `Could not select mailbox` | Mailbox name is case-sensitive; run `mailagent folders` |
| `SMTP send failed` | Check SMTP host/port, STARTTLS vs SSL, app password |
| `BODY[TEXT]` partial fetch empty | Some servers need `BODY.PEEK[]`; use `mail_read` for full body |
| Agent sees no tools | Verify the MCP client points to the correct `mailagent` binary and has env vars |
| `Mail account is in read-only mode` | Remove `MAIL_READ_ONLY=true` to allow mutating operations |

---

## Roadmap

- [ ] OAuth2 support (Gmail/Outlook token flow)
- [ ] IMAP IDLE / live inbox notifications
- [ ] HTTP REST API in addition to MCP
- [ ] Folder creation/rename/delete
- [ ] Draft support
- [ ] S/MIME and PGP
- [ ] Prebuilt packages (APT, AUR, PyPI)

---

## License

[MIT](LICENSE) © 2026 ASAKAFENG. Contributions are welcome.
