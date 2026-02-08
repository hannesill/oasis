"""Tests for MCP configuration scripts."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from oasis.mcp_client_configs.dynamic_mcp_config import MCPConfigGenerator


class TestMCPConfigGenerator:
    """Test the MCPConfigGenerator class."""

    def test_generate_config_duckdb_default(self):
        """Test generating DuckDB config with defaults."""
        generator = MCPConfigGenerator()

        with (
            patch.object(generator, "_validate_python_path", return_value=True),
            patch.object(generator, "_validate_directory", return_value=True),
        ):
            config = generator.generate_config()

            # OASIS_BACKEND is no longer in env - backend comes from config file
            assert "OASIS_BACKEND" not in config["mcpServers"]["oasis"]["env"]
            assert "OASIS_PROJECT_ID" not in config["mcpServers"]["oasis"]["env"]
            assert config["mcpServers"]["oasis"]["args"] == ["-m", "oasis.mcp_server"]

    def test_generate_config_duckdb_with_db_path(self):
        """Test generating DuckDB config with custom database path."""
        generator = MCPConfigGenerator()

        with (
            patch.object(generator, "_validate_python_path", return_value=True),
            patch.object(generator, "_validate_directory", return_value=True),
        ):
            config = generator.generate_config(
                db_path="/custom/path/database.duckdb"
            )

            assert "OASIS_BACKEND" not in config["mcpServers"]["oasis"]["env"]
            assert (
                config["mcpServers"]["oasis"]["env"]["OASIS_DB_PATH"]
                == "/custom/path/database.duckdb"
            )

    def test_generate_config_custom_server_name(self):
        """Test generating config with custom server name."""
        generator = MCPConfigGenerator()

        with (
            patch.object(generator, "_validate_python_path", return_value=True),
            patch.object(generator, "_validate_directory", return_value=True),
        ):
            config = generator.generate_config(server_name="custom-m4")

            assert "custom-m4" in config["mcpServers"]
            assert "oasis" not in config["mcpServers"]

    def test_generate_config_additional_env_vars(self):
        """Test generating config with additional environment variables."""
        generator = MCPConfigGenerator()

        with (
            patch.object(generator, "_validate_python_path", return_value=True),
            patch.object(generator, "_validate_directory", return_value=True),
        ):
            config = generator.generate_config(
                additional_env={"DEBUG": "true", "LOG_LEVEL": "info"}
            )

            env = config["mcpServers"]["oasis"]["env"]
            assert env["DEBUG"] == "true"
            assert env["LOG_LEVEL"] == "info"
            # OASIS_BACKEND is no longer in env - backend comes from config file
            assert "OASIS_BACKEND" not in env

    def test_validation_invalid_python_path(self):
        """Test that invalid Python path raises error."""
        generator = MCPConfigGenerator()

        with (
            patch.object(generator, "_validate_python_path", return_value=False),
            patch.object(generator, "_validate_directory", return_value=True),
        ):
            with pytest.raises(ValueError, match="Invalid Python path"):
                generator.generate_config(python_path="/invalid/python")

    def test_validation_invalid_directory(self):
        """Test that invalid working directory raises error."""
        generator = MCPConfigGenerator()

        with (
            patch.object(generator, "_validate_python_path", return_value=True),
            patch.object(generator, "_validate_directory", return_value=False),
        ):
            with pytest.raises(ValueError, match="Invalid working directory"):
                generator.generate_config(working_directory="/invalid/dir")
