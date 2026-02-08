"""
Setup script for OASIS MCP Server with Claude Desktop.
Automatically configures Claude Desktop to use the OASIS MCP server.
"""

import json
import os
import shutil
from pathlib import Path


def get_claude_config_path():
    """Get the Claude Desktop configuration file path."""
    home = Path.home()

    # macOS path
    claude_config = (
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "claude_desktop_config.json"
    )
    if claude_config.parent.exists():
        return claude_config

    # Windows path
    claude_config = (
        home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    )
    if claude_config.parent.exists():
        return claude_config

    # Linux path
    claude_config = home / ".config" / "Claude" / "claude_desktop_config.json"
    if claude_config.parent.exists():
        return claude_config

    raise FileNotFoundError("Could not find Claude Desktop configuration directory")


def get_current_directory():
    """Get the current OASIS project directory."""
    p = Path(__file__).resolve()

    # Try to find pyproject.toml
    search_p = p
    while search_p != search_p.parent:
        if (search_p / "pyproject.toml").exists():
            return search_p
        search_p = search_p.parent

    # If installed as package and no pyproject.toml found, use CWD
    return Path.cwd()


def get_python_path():
    """Get the Python executable path."""
    # Try to use the current virtual environment
    if "VIRTUAL_ENV" in os.environ:
        venv_python = Path(os.environ["VIRTUAL_ENV"]) / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)

    # Fall back to system python
    return shutil.which("python") or shutil.which("python3") or "python"


def find_oasis_data_dir(working_directory: Path) -> Path:
    """Find the actual oasis_data directory by searching upward from working_directory."""
    cwd = working_directory.resolve()
    for path in [cwd, *cwd.parents]:
        data_dir = path / "oasis_data"
        if data_dir.exists() and data_dir.is_dir():
            # Check for characteristic OASIS data artifacts
            if (
                (data_dir / "config.json").exists()
                or (data_dir / "databases").exists()
                or (data_dir / "parquet").exists()
                or (data_dir / "datasets").exists()
                or (data_dir / "raw_files").exists()
            ):
                return data_dir
    # If not found, return the default location
    return working_directory / "oasis_data"


def create_mcp_config(db_path=None):
    """Create MCP server configuration."""
    current_dir = get_current_directory()
    python_path = get_python_path()

    # Find the actual oasis_data directory (may be in parent directory)
    oasis_data_dir = find_oasis_data_dir(current_dir)

    config = {
        "mcpServers": {
            "oasis": {
                "command": python_path,
                "args": ["-m", "oasis.mcp_server"],
                "cwd": str(current_dir),
                "env": {
                    "OASIS_DATA_DIR": str(oasis_data_dir),
                    "MAPBOX_TOKEN": os.environ.get("MAPBOX_TOKEN", ""),
                },
            }
        }
    }

    # Add PYTHONPATH only if running from source (checked by presence of pyproject.toml)
    if (current_dir / "pyproject.toml").exists():
        config["mcpServers"]["oasis"]["env"]["PYTHONPATH"] = str(current_dir / "src")

    # Add custom DuckDB path if provided
    if db_path:
        config["mcpServers"]["oasis"]["env"]["OASIS_DB_PATH"] = db_path

    return config


def setup_claude_desktop(db_path=None):
    """Setup Claude Desktop with OASIS MCP server."""
    try:
        claude_config_path = get_claude_config_path()
        print(f"Found Claude Desktop config at: {claude_config_path}")

        # Load existing config or create new one
        existing_config = {}
        if claude_config_path.exists() and claude_config_path.stat().st_size > 0:
            try:
                with open(claude_config_path) as f:
                    existing_config = json.load(f)
                print("Loaded existing Claude Desktop configuration")
            except json.JSONDecodeError:
                print("Found corrupted config file, creating new configuration")
                existing_config = {}
        else:
            print("Creating new Claude Desktop configuration")

        # Create MCP config
        mcp_config = create_mcp_config(db_path)

        # Merge configurations
        if "mcpServers" not in existing_config:
            existing_config["mcpServers"] = {}

        existing_config["mcpServers"].update(mcp_config["mcpServers"])

        # Ensure directory exists
        claude_config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write updated config
        with open(claude_config_path, "w") as f:
            json.dump(existing_config, f, indent=2)

        print("Successfully configured Claude Desktop!")
        print(f"Config file: {claude_config_path}")
        print("Backend: duckdb")

        db_path_display = db_path or "default (oasis_data/databases/vf_ghana.duckdb)"
        print(f"Database: {db_path_display}")

        print("\nPlease restart Claude Desktop to apply changes")

        return True

    except Exception as e:
        print(f"Error setting up Claude Desktop: {e}")
        return False


def main():
    """Main setup function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Setup OASIS MCP Server with Claude Desktop"
    )
    parser.add_argument(
        "--db-path", help="Path to DuckDB database (optional)"
    )

    args = parser.parse_args()

    print("Setting up OASIS MCP Server with Claude Desktop...")

    success = setup_claude_desktop(db_path=args.db_path)

    if success:
        print("\nSetup complete! You can now use OASIS tools in Claude Desktop.")
        print(
            "\nTry asking Claude: 'What tools do you have available for healthcare data?'"
        )
    else:
        print("\nSetup failed. Please check the error messages above.")
        exit(1)


if __name__ == "__main__":
    main()
