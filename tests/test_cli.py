import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from oasis.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def inject_version(monkeypatch):
    # Patch __version__ in the console module where print_logo imports it
    monkeypatch.setattr("oasis.__version__", "0.0.1")


def test_help_shows_app_name():
    result = runner.invoke(app, ["--help"])
    # exit code 0 for successful help display
    assert result.exit_code == 0
    # help output contains the app name
    assert "OASIS CLI" in result.stdout


def test_version_option_exits_zero_and_shows_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    # Now displays logo with version
    assert "v0.0.1" in result.stdout


def test_unknown_command_reports_error():
    result = runner.invoke(app, ["not-a-cmd"])
    # unknown command should fail
    assert result.exit_code != 0
    # Check both stdout and stderr since error messages might go to either depending on environment
    error_message = "No such command 'not-a-cmd'"
    assert (
        error_message in result.stdout
        or (hasattr(result, "stderr") and error_message in result.stderr)
        or error_message in result.output
    )


def test_init_command_duckdb_custom_path(tmp_path):
    """Test that oasis init --db-path uses custom database path override and DuckDB flow."""
    # Create a temp parquet dir with a dummy file so presence detection works
    pq_dir = tmp_path / "parquet" / "vf-ghana"
    pq_dir.mkdir(parents=True)
    (pq_dir / "test.parquet").touch()

    custom_db_path = tmp_path / "custom_vf_ghana.duckdb"
    resolved_custom_db_path = custom_db_path.resolve()

    with (
        patch("oasis.config._find_project_root_from_cwd", return_value=Path.cwd()),
        patch("oasis.cli.get_dataset_parquet_root", return_value=pq_dir),
        patch("oasis.cli.init_duckdb_from_parquet", return_value=True) as mock_init,
        patch("oasis.cli.verify_table_rowcount", return_value=100) as mock_rowcount,
        patch("oasis.cli.set_active_dataset"),
    ):
        result = runner.invoke(
            app, ["init", "vf-ghana", "--db-path", str(custom_db_path)]
        )

    assert result.exit_code == 0
    # With Rich panels, paths may be split across lines, check for parts of filename
    assert "custom_vf_ghan" in result.stdout and ".duckdb" in result.stdout
    # Now uses "Database:" instead of "DuckDB path:"
    assert "Database:" in result.stdout

    # initializer should be called with the resolved path
    mock_init.assert_called_once_with(
        dataset_name="vf-ghana", db_target_path=resolved_custom_db_path
    )
    # verification query should be attempted
    mock_rowcount.assert_called()


@patch("subprocess.run")
@patch("oasis.cli.get_active_backend", return_value="duckdb")
def test_config_claude_success(mock_backend, mock_subprocess):
    """Test successful Claude Desktop configuration."""
    mock_subprocess.return_value = MagicMock(returncode=0)

    result = runner.invoke(app, ["config", "claude"])
    assert result.exit_code == 0
    assert "Claude Desktop configuration completed" in result.stdout

    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args[0][0]
    # correct script should be invoked
    assert "setup_claude_desktop.py" in call_args[1]


@patch("subprocess.run")
@patch("oasis.cli.get_active_backend", return_value="duckdb")
def test_config_universal_quick_mode(mock_backend, mock_subprocess):
    """Test universal config generator in quick mode."""
    mock_subprocess.return_value = MagicMock(returncode=0)

    result = runner.invoke(app, ["config", "--quick"])
    assert result.exit_code == 0
    assert "Generating OASIS MCP configuration" in result.stdout

    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args[0][0]
    assert "dynamic_mcp_config.py" in call_args[1]
    assert "--quick" in call_args


@patch("subprocess.run")
@patch("oasis.cli.get_active_backend", return_value="duckdb")
def test_config_script_failure(mock_backend, mock_subprocess):
    """Test error handling when config script fails."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(1, "cmd")

    result = runner.invoke(app, ["config", "claude"])
    # command should return failure exit code when subprocess fails
    assert result.exit_code == 1
    # Just verify that the command failed with the right exit code
    # The specific error message may vary


@patch("subprocess.run")
@patch("oasis.cli.get_active_backend", return_value="duckdb")
@patch("oasis.cli.get_default_database_path")
@patch("oasis.cli.get_active_dataset")
def test_config_claude_infers_db_path_demo(
    mock_active, mock_get_default, mock_backend, mock_subprocess
):
    mock_active.return_value = None  # unset -> default to demo
    mock_get_default.return_value = Path("/tmp/inferred-demo.duckdb")
    mock_subprocess.return_value = MagicMock(returncode=0)

    result = runner.invoke(app, ["config", "claude"])
    assert result.exit_code == 0

    # subprocess run should NOT be called with inferred --db-path (dynamic resolution)
    call_args = mock_subprocess.call_args[0][0]
    assert "--db-path" not in call_args


@patch("subprocess.run")
@patch("oasis.cli.get_active_backend", return_value="duckdb")
@patch("oasis.cli.get_default_database_path")
@patch("oasis.cli.get_active_dataset")
def test_config_claude_infers_db_path_full(
    mock_active, mock_get_default, mock_backend, mock_subprocess
):
    mock_active.return_value = "vf-ghana"
    mock_get_default.return_value = Path("/tmp/inferred-full.duckdb")
    mock_subprocess.return_value = MagicMock(returncode=0)

    result = runner.invoke(app, ["config", "claude"])
    assert result.exit_code == 0

    call_args = mock_subprocess.call_args[0][0]
    assert "--db-path" not in call_args


@patch("oasis.cli.set_active_dataset")
@patch("oasis.cli.detect_available_local_datasets")
def test_use_full_happy_path(mock_detect, mock_set_active):
    mock_detect.return_value = {
        "vf-ghana": {
            "parquet_present": True,
            "db_present": True,
            "parquet_root": "/tmp/vf-ghana",
            "db_path": "/tmp/vf_ghana.duckdb",
        },
    }

    result = runner.invoke(app, ["use", "vf-ghana"])
    assert result.exit_code == 0
    # Updated format without trailing period
    assert "Active dataset set to 'vf-ghana'" in result.stdout
    mock_set_active.assert_called_once_with("vf-ghana")


@patch("oasis.cli.compute_parquet_dir_size", return_value=123)
@patch("oasis.cli.get_active_dataset", return_value="vf-ghana")
@patch("oasis.cli.detect_available_local_datasets")
def test_status_happy_path(mock_detect, mock_active, mock_size):
    mock_detect.return_value = {
        "vf-ghana": {
            "parquet_present": True,
            "db_present": True,
            "parquet_root": "/tmp/vf-ghana",
            "db_path": "/tmp/vf_ghana.duckdb",
        },
    }

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Active dataset:" in result.stdout
    assert "vf-ghana" in result.stdout
    # Updated Rich format: "Parquet size:  X.XX GB"
    assert "Parquet size:" in result.stdout


