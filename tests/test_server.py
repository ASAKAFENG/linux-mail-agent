from linux_mail_agent.cli import main
from linux_mail_agent.server import create_server


def test_cli_help_smoke(capsys):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "mailagent" in out


def test_server_registers_tools():
    mcp = create_server()
    names = {tool.name for tool in mcp._tool_manager._tools.values()}
    assert {
        "mail_list",
        "mail_read",
        "mail_send",
        "mail_reply",
        "mail_move",
        "mail_delete",
    } <= names
