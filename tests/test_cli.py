"""CLI wiring tests (no model required)."""
from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from gcp_agent_playground.main import app


def test_chat_help_includes_include_flag() -> None:
    """The --help output proves --include is a recognized option."""
    runner = CliRunner()
    result = runner.invoke(app, ["chat", "--help"])
    assert result.exit_code == 0, result.output
    assert "--include" in result.output
    assert "-i" in result.output


def test_chat_include_missing_file_fails_before_profile_load() -> None:
    """A bad --include path must be rejected by typer's exists=True
    *before* profiles.load runs (so we never spin a server on a bad include).
    """
    runner = CliRunner()
    with patch("gcp_agent_playground.profiles.load") as mock_load:
        result = runner.invoke(
            app,
            ["chat", "--include", "/definitely/not/here.tf", "--profile", "heavy"],
        )
    assert result.exit_code != 0
    mock_load.assert_not_called()
