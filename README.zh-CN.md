# linux-mail-agent

**面向 AI 智能体的 Linux 邮箱网关** —— 通过命令行或
[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 使用
IMAP/SMTP 读取、搜索、发送、回复、转发、移动和删除邮件。

`linux-mail-agent` 的设计目标是：**AI 智能体可以像人一样方便地控制邮箱**。
它把同一套操作同时暴露为：

- **MCP 服务器**（stdio / SSE / HTTP），LLM 工具可以直接调用；
- **JSON 优先的 CLI**，Shell 智能体、cron 任务和人类都能使用。

项目只依赖 Python 标准库 + `mcp` + `python-dotenv`，可运行在任何现代 Linux 发行版上。

---

## 为什么需要这个项目？

AI 智能体越来越多地需要和邮件交互：通知某人、读取验证码、总结收件箱、
查找附件、回复邮件等。而 IMAP/SMTP 本身是底层协议，对智能体不友好。

`linux-mail-agent` 把邮箱变成**一组高层、带类型的工具**：

```
mail_check_config   mail_list_folders  mail_list      mail_search
mail_read           mail_send          mail_reply     mail_forward
mail_mark_seen      mail_mark_unseen   mail_move      mail_delete
mail_save_attachment
```

智能体不需要了解 IMAP 序号、MIME 解析、TLS 配置或 SMTP 信封细节。
它只需要调用 `mail_list("INBOX", limit=10)` 拿到 UID，再调用
`mail_read("INBOX", "42")` 读取完整邮件。

---

## 功能特性

- **原生 MCP**：每个操作都是带类型参数的 MCP 工具，返回 JSON 结果。
- **CLI + JSON**：适合人类使用的子命令，同时输出 JSON 方便脚本处理。
- **IMAP 读取**：列出文件夹、列出/搜索邮件、读取完整邮件、保存附件、
  标记已读/未读、移动、删除。
- **SMTP 发送**：纯文本和 HTML 邮件、CC/BCC、本地附件、回复和转发，
  自动处理 `In-Reply-To` / `References` 邮件头。
- **安全默认值**：默认 IMAPS，SMTP 支持 STARTTLS 或隐式 SSL，可配置超时，
  工具输出不会泄露密码。
- **只读模式**：`MAIL_READ_ONLY=true` 会阻止所有修改类操作，
  适合让智能体读取真实邮箱但禁止改动。
- **收件人白名单**：`MAIL_ALLOWED_TO` 可限制只能发给指定地址，
  防止智能体乱发邮件。
- **无厂商锁定**：标准 IMAP/SMTP 可对接 Gmail、Outlook/Office 365、
  QQ 邮箱、163 邮箱、Fastmail、自建 Dovecot/Postfix 等
  （部分服务商可能需要应用专用密码）。

---

## 项目结构

```text
linux-mail-agent/
├── pyproject.toml          # Python 包元数据 + 入口命令
├── Dockerfile              # 容器镜像（SSE/HTTP 或隔离 stdio）
├── Makefile
├── README.md               # English README
├── README.zh-CN.md         # 中文 README
├── AGENTS.md               # 给 AI 编码智能体的开发指南
├── .env.example
├── src/linux_mail_agent/
│   ├── config.py           # 基于环境变量的配置
│   ├── mail.py             # IMAP/SMTP 核心，不依赖 MCP
│   ├── server.py           # MCP 服务/工具定义
│   ├── cli.py              # CLI 子命令
│   └── text.py             # 邮件正文/摘要工具
└── tests/
```

核心 `mail.py` 不依赖 MCP，因此可以复用到其他前端（HTTP API、SDK、自定义 Agent）。

---

## 环境要求

- Linux（或其他 POSIX 系统；Windows 不是目标）
- Python **3.10+**
- 一个启用了 IMAP 的邮箱账号，如需发送还要启用 SMTP
- 如果给 AI 智能体使用，需要一个 MCP 客户端
  （Claude Desktop、Cursor、VS Code、自研 Agent 等）

---

## 安装

### 从源码安装

```bash
git clone https://github.com/ASAKAFENG/linux-mail-agent.git
cd linux-mail-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"     # 安装 CLI + 开发依赖
```

### 从 PyPI 安装（发布后）

```bash
pip install linux-mail-agent
```

### 验证

```bash
mailagent --help
```

---

## 配置

配置刻意使用环境变量：这样可以方便地用于 systemd、Docker 和 MCP 客户端。

复制示例文件并编辑：

```bash
cp .env.example .env
```

然后可以 `source .env`，或者在项目目录下运行命令让它自动加载 `.env`。
也支持全局配置路径：`~/.config/linux-mail-agent/.env`。

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `MAIL_IMAP_HOST` | ✅ | – | IMAP 服务器，如 `imap.gmail.com` |
| `MAIL_IMAP_USER` | ✅ | – | 完整邮箱地址 / 登录名 |
| `MAIL_IMAP_PASSWORD` | ✅ | – | 密码或应用专用密码 |
| `MAIL_IMAP_PORT` | | `993` | IMAP 端口 |
| `MAIL_IMAP_SSL` | | `true` | IMAP 使用隐式 TLS |
| `MAIL_SMTP_HOST` | | IMAP 主机 | SMTP 服务器，如 `smtp.gmail.com` |
| `MAIL_SMTP_PORT` | | `587`（SSL 时 `465`） | SMTP 端口 |
| `MAIL_SMTP_SSL` | | `false` | SMTP 使用隐式 TLS（`465`） |
| `MAIL_SMTP_STARTTLS` | | `true` | SMTP 使用 STARTTLS（`587`） |
| `MAIL_FROM` | | IMAP 用户 | 发件人地址，如果和登录名不同 |
| `MAIL_FROM_NAME` | | 空 | 发件人显示名称 |
| `MAIL_TIMEOUT` | | `30` | 网络超时（秒） |
| `MAIL_ATTACHMENT_DIR` | | `~/.local/share/linux-mail-agent/attachments` | 附件保存目录 |
| `MAIL_READ_ONLY` | | `false` | 禁止所有修改/发送操作 |
| `MAIL_ALLOWED_TO` | | 未设置 | 收件人白名单，逗号分隔；设置后只能发给名单内地址 |

> **永远不要提交 `.env`。** `.gitignore` 已默认排除。

### 示例 `.env`

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
MAIL_FROM_NAME="Your Name"
```

### 服务商注意事项

- **Gmail / Google Workspace**：开启两步验证后创建
  [应用专用密码](https://support.google.com/accounts/answer/185833)。
- **Outlook / Office 365**：开启 IMAP/SMTP，如开启 MFA 请使用应用密码。
- **QQ 邮箱 / 163 邮箱**：在设置里开启 IMAP/SMTP，并使用授权码作为密码。
- **自建邮箱**：支持 Dovecot + Postfix，按实际情况调整端口和 TLS 配置。

---

## 快速开始

```bash
# 1. 配置
cp .env.example .env
# 编辑 .env

# 2. 检查配置（不会打印密码）
mailagent check

# 3. 列出邮箱文件夹
mailagent folders

# 4. 列出 INBOX 最近 10 封邮件
mailagent list --mailbox INBOX --limit 10

# 5. 读取一封邮件（uid 来自 list 输出）
mailagent show INBOX 12345

# 6. 搜索
mailagent search "发票" --limit 5

# 7. 发送
mailagent send --to "alice@example.com" --subject "你好" --body "正文"
```

所有命令都输出 JSON，方便管道处理：

```bash
mailagent list --unseen-only --limit 5 | jq '.[] | {uid, subject, from}'
```

---

## CLI 命令参考

全局参数：`--env-file PATH` 指定加载某个 `.env` 文件。

| 命令 | 说明 | 示例 |
| --- | --- | --- |
| `serve` | 运行 MCP 服务（`--transport stdio|sse|streamable-http`） | `mailagent serve` |
| `check` | 打印不含密钥的配置状态 | `mailagent check` |
| `folders` | 列出邮箱文件夹 | `mailagent folders` |
| `list` | 列出邮件 | `mailagent list --mailbox INBOX --limit 10 --unseen-only` |
| `search` | 按正文/主题搜索 | `mailagent search "发票"` |
| `show` | 读取完整邮件 | `mailagent show INBOX 12345` |
| `send` | 发送邮件 | `mailagent send --to a@x.com --subject Hi --body Hello` |
| `reply` | 回复某封邮件 | `mailagent reply INBOX 12345 --body "谢谢！"` |
| `forward` | 转发某封邮件 | `mailagent forward INBOX 12345 --to b@x.com --body FYI` |
| `mark-seen` | 标记已读 | `mailagent mark-seen INBOX 12345` |
| `mark-unseen` | 标记未读 | `mailagent mark-unseen INBOX 12345` |
| `move` | 移动到其他文件夹 | `mailagent move INBOX 12345 Archive` |
| `delete` | 删除/彻底清除 | `mailagent delete INBOX 12345` |
| `attachment` | 保存附件到本地 | `mailagent attachment INBOX 12345 --index 0` |

`send` 支持 `--cc`、`--bcc`、`--html`、`--attachment`（可重复）和 `--reply-to`。

```bash
mailagent send \
  --to "alice@example.com,bob@example.com" \
  --cc "team@example.com" \
  --subject "报告" \
  --body "见附件。" \
  --html "<p>见附件。</p>" \
  --attachment ./report.pdf
```

---

## 给 AI 智能体使用（MCP）

### 1. 启动 MCP 服务器

大多数 MCP 客户端使用 **stdio**：

```bash
mailagent serve
```

服务器会在 stdin/stdout 上保持运行，使用 MCP JSON-RPC 通信。
如果需要远程或 Web 场景，也可以使用 SSE 或 Streamable HTTP：

```bash
mailagent serve --transport sse
# 或
mailagent serve --transport streamable-http
```

### 2. 在 MCP 客户端中注册

**Claude Desktop / Claude Code / Cursor 等**，添加本地 MCP 服务器：

```json
{
  "mcpServers": {
    "linux-mail-agent": {
      "command": "/绝对路径/.venv/bin/mailagent",
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

> `env` 块仅适用于支持向本地 MCP 服务器传递环境变量的客户端。
> 否则请在启动客户端的 Shell 中导出变量，或使用 wrapper 脚本加载 `.env`。

**Wrapper 脚本**（`mailagent-mcp.sh`）：

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/you/linux-mail-agent
set -a; source .env; set +a
exec /home/you/linux-mail-agent/.venv/bin/mailagent serve
```

### 3. 暴露给智能体的工具

| 工具 | 智能体可以做什么 |
| --- | --- |
| `mail_check_config` | 检查账号是否已配置；查看只读状态 |
| `mail_list_folders` | 列出所有 IMAP 文件夹 |
| `mail_list` | 列出最近邮件，含 UID、主题、发件人、日期、标记、摘要 |
| `mail_search` | 按主题/正文搜索 |
| `mail_read` | 读取完整纯文本/HTML 正文和附件元信息 |
| `mail_send` | 发送新邮件，支持 HTML 和本地附件 |
| `mail_reply` | 回复邮件，保留线程头 |
| `mail_forward` | 转发邮件 |
| `mail_mark_seen` / `mail_mark_unseen` | 修改已读状态 |
| `mail_move` | 移动到其他文件夹 |
| `mail_delete` | 删除邮件 |
| `mail_save_attachment` | 保存附件到磁盘并返回路径 |

智能体典型流程：

1. `mail_list("INBOX", limit=10, unseen_only=True)`
2. `mail_read("INBOX", "12345")`
3. `mail_reply("INBOX", "12345", body="谢谢，我今天会处理。")`

`mail_list` / `mail_search` 返回的 UID 是 IMAP UID，在邮件生命周期内稳定；
请把它原样传回 `mail_read`、`mail_move` 等工具。

### 4. 给不可信智能体开启只读模式

如果只希望智能体**读取但不修改/发送**，设置：

```dotenv
MAIL_READ_ONLY=true
```

这样 `mail_send`、`mail_reply`、`mail_forward`、`mail_mark_*`、`mail_move`
和 `mail_delete` 都会直接报错。

### 5. 限制可发送对象

如果只允许发给指定地址，设置：

```dotenv
MAIL_ALLOWED_TO=you@example.com,other@example.com
```

设置后，发送/回复/转发时只要有任何收件人（含 CC/BCC）不在白名单内就会拒绝。

---

## 安全建议

- **使用应用专用密码。** 尽量避免使用主密码；多数服务商支持应用密码。
- **不要打印密钥。** 服务端和 CLI 永远不会返回密码，
  `mail_check_config` 只输出不含密钥的状态。
- **最小权限。** 如果是专用智能体邮箱，建议创建独立账号并限制权限。
- **先只读再写。** 测试时使用 `MAIL_READ_ONLY=true`，确认可信后再开放写权限。
- **沙箱运行。** 使用独立 Unix 用户、容器或 systemd 服务，
  可开启 `NoNewPrivileges=true`、`PrivateTmp=true` 等加固选项。
- **网络操作是真实的。** 删除和发送对智能体来说不可逆；如果把自主 Agent
  接到生产邮箱，请在上层增加确认/审批机制。
- **附件是文件。** `mail_save_attachment` 会写入 `MAIL_ATTACHMENT_DIR`；
  如果邮件包含敏感内容，请保持该目录私密。

---

## 作为 systemd 服务运行（MCP over SSE/HTTP）

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

然后：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now linux-mail-agent
```

---

## 使用 Docker

```bash
docker build -t linux-mail-agent .
docker run --rm \
  --env-file .env \
  -p 8000:8000 \
  linux-mail-agent serve --transport streamable-http
```

> stdio 模式通常直接在宿主机运行更简单；容器镜像主要用于 SSE/HTTP 或沙箱隔离。

---

## 开发

```bash
make dev        # 可编辑安装 + 开发依赖
make test       # 运行 pytest
make build      # 构建 wheel
```

运行完整测试：

```bash
python3 -m pytest -q
```

当前测试覆盖：配置解析、日期/搜索条件、HTML 转文本、MIME 正文提取、
MCP 工具注册、只读安全、收件人白名单。

### 新增一个邮件操作

1. 在 `mail.py` 中实现操作（保持不依赖 MCP）。
2. 在 `server.py` 中添加 `@mcp.tool()` 包装。
3. 如果对人类也有用，在 `cli.py` 中添加子命令。
4. 添加测试并运行 `make test`。

更详细的智能体开发规范见 `AGENTS.md`。

---

## 常见问题

| 问题 | 解决方法 |
| --- | --- |
| `MAIL_IMAP_HOST ... required` | `.env` 未加载；进入项目目录或使用 `--env-file` |
| `IMAP connection failed` | 检查主机/端口、TLS 开关、网络、防火墙 |
| `Could not select mailbox` | 文件夹名区分大小写；先运行 `mailagent folders` |
| `SMTP send failed` | 检查 SMTP 主机/端口、STARTTLS 与 SSL、应用密码 |
| `BODY[TEXT]` 摘要为空 | 部分服务器不支持部分抓取；用 `mail_read` 读取完整正文 |
| 智能体看不到工具 | 确认 MCP 客户端指向正确的 `mailagent` 且环境变量已配置 |
| `Mail account is in read-only mode` | 去掉 `MAIL_READ_ONLY=true` 以允许修改操作 |
| 发送被拒绝 | 检查 `MAIL_ALLOWED_TO` 白名单是否包含目标收件人 |

---

## Roadmap

- [ ] OAuth2 支持（Gmail/Outlook Token 流程）
- [ ] IMAP IDLE / 实时收件通知
- [ ] 独立 HTTP REST API
- [ ] 文件夹创建/重命名/删除
- [ ] 草稿支持
- [ ] S/MIME 和 PGP
- [ ] 预构建包（APT、AUR、PyPI）

---

## License

[MIT](LICENSE) © 2026 ASAKAFENG. 欢迎贡献。
