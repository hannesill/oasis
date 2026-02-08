"""
Dynamic MCP Configuration Generator for OASIS Server.
Generates MCP server configurations that can be copied and pasted into any MCP client.
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from oasis.config import get_default_database_path


class MCPConfigGenerator:
    """Generator for MCP server configurations."""

    def __init__(self):
        # Start looking for project root
        p = Path(__file__).resolve()
        found_project_root = False

        # Try to find pyproject.toml
        search_p = p
        while search_p != search_p.parent:
            if (search_p / "pyproject.toml").exists():
                found_project_root = True
                p = search_p
                break
            search_p = search_p.parent

        if found_project_root:
            self.current_dir = p
        else:
            # If installed as package and no pyproject.toml found, use CWD
            self.current_dir = Path.cwd()

        self.default_python = self._get_default_python()

    def _find_oasis_data_dir(self, working_directory: str) -> Path:
        """Find the actual oasis_data directory by searching upward from working_directory."""
        cwd = Path(working_directory).resolve()
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
        return Path(working_directory) / "oasis_data"

    def _get_default_python(self) -> str:
        """Get the default Python executable path."""
        # Try to use the current virtual environment
        if "VIRTUAL_ENV" in os.environ:
            venv_python = Path(os.environ["VIRTUAL_ENV"]) / "bin" / "python"
            if venv_python.exists():
                return str(venv_python)

        # Fall back to system python
        return shutil.which("python") or shutil.which("python3") or "python"

    def _validate_python_path(self, python_path: str) -> bool:
        """Validate that the Python path exists and is executable."""
        path = Path(python_path)
        return path.exists() and path.is_file() and os.access(path, os.X_OK)

    def _validate_directory(self, dir_path: str) -> bool:
        """Validate that the directory exists."""
        return Path(dir_path).exists() and Path(dir_path).is_dir()

    def generate_config(
        self,
        server_name: str = "oasis",
        python_path: str | None = None,
        working_directory: str | None = None,
        db_path: str | None = None,
        additional_env: dict[str, str] | None = None,
        module_name: str = "oasis.mcp_server",
    ) -> dict[str, Any]:
        """Generate MCP server configuration."""

        # Use defaults if not provided
        if python_path is None:
            python_path = self.default_python
        if working_directory is None:
            working_directory = str(self.current_dir)

        # Validate inputs
        if not self._validate_python_path(python_path):
            raise ValueError(f"Invalid Python path: {python_path}")
        if not self._validate_directory(working_directory):
            raise ValueError(f"Invalid working directory: {working_directory}")

        # Find the actual oasis_data directory (may be in parent directory)
        oasis_data_dir = self._find_oasis_data_dir(working_directory)

        # Build environment variables
        env = {
            "OASIS_DATA_DIR": str(oasis_data_dir),
        }

        # Add PYTHONPATH if we're running from source
        if (Path(working_directory) / "pyproject.toml").exists() or (
            Path(working_directory) / "src"
        ).exists():
            env["PYTHONPATH"] = str(Path(working_directory) / "src")

        # Add custom DuckDB path if provided
        if db_path:
            env["OASIS_DB_PATH"] = db_path

        # Add any additional environment variables
        if additional_env:
            env.update(additional_env)

        # Create the configuration
        config = {
            "mcpServers": {
                server_name: {
                    "command": python_path,
                    "args": ["-m", module_name],
                    "cwd": working_directory,
                    "env": env,
                }
            }
        }

        return config

    def interactive_config(self) -> dict[str, Any]:
        """Interactive configuration builder."""
        print("OASIS MCP Server Configuration Generator")
        print("=" * 50)

        # Server name
        print("\nServer Configuration:")
        print("The server name is how your MCP client will identify this server.")
        server_name = (
            input("Server name (press Enter for default 'oasis'): ").strip() or "oasis"
        )

        # Python path
        print(f"\nDefault Python path: {self.default_python}")
        python_path = input(
            "Python executable path (press Enter for default): "
        ).strip()
        if not python_path:
            python_path = self.default_python

        # Working directory
        print(f"\nDefault working directory: {self.current_dir}")
        working_directory = input(
            "Working directory (press Enter for default): "
        ).strip()
        if not working_directory:
            working_directory = str(self.current_dir)

        # DuckDB Configuration
        print("\nDuckDB Configuration:")
        default_db_path = get_default_database_path("vf-ghana")
        if default_db_path:
            print(f"Default database path: {default_db_path}")

        print(
            "\nLeaving database path empty allows switching datasets dynamically via 'oasis use'."
        )
        db_path = (
            input(
                "DuckDB database path (optional, press Enter for dynamic): "
            ).strip()
            or None
        )

        # Additional environment variables
        additional_env = {}
        print("\nAdditional environment variables (optional):")
        print(
            "Enter key=value pairs, one per line. Press Enter on empty line to finish."
        )
        while True:
            env_var = input("Environment variable: ").strip()
            if not env_var:
                break
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                additional_env[key.strip()] = value.strip()
                print(f"Added: {key.strip()}={value.strip()}")
            else:
                print("Invalid format. Use key=value")

        return self.generate_config(
            server_name=server_name,
            python_path=python_path,
            working_directory=working_directory,
            db_path=db_path,
            additional_env=additional_env if additional_env else None,
            module_name="oasis.mcp_server",
        )


def print_config_info(config: dict[str, Any]):
    """Print configuration information."""
    # Get the first (and likely only) server configuration
    server_name = next(iter(config["mcpServers"].keys()))
    server_config = config["mcpServers"][server_name]

    print("\nConfiguration Summary:")
    print("=" * 30)
    print(f"Server name: {server_name}")
    print(f"Python path: {server_config['command']}")
    print(f"Working directory: {server_config['cwd']}")
    print("Backend: duckdb")

    if "OASIS_DB_PATH" in server_config["env"]:
        print(f"Database path: {server_config['env']['OASIS_DB_PATH']}")
    else:
        default_path = get_default_database_path("vf-ghana")
        if default_path:
            print(f"Database path: {default_path}")

    # Show additional env vars (excluding ones we've already displayed)
    additional_env = {
        k: v
        for k, v in server_config["env"].items()
        if k not in ["PYTHONPATH", "OASIS_DB_PATH"]
    }
    if additional_env:
        print("Additional environment variables:")
        for key, value in additional_env.items():
            print(f"   {key}: {value}")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate MCP server configuration for OASIS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python dynamic_mcp_config.py

  # Quick generation with defaults
  python dynamic_mcp_config.py --quick

  # Save to file
  python dynamic_mcp_config.py --output config.json
        """,
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Generate configuration with defaults (non-interactive)",
    )
    parser.add_argument(
        "--server-name", default="oasis", help="Name for the MCP server (default: oasis)"
    )
    parser.add_argument("--python-path", help="Path to Python executable")
    parser.add_argument("--working-directory", help="Working directory for the server")
    parser.add_argument(
        "--db-path", help="Path to DuckDB database"
    )
    parser.add_argument(
        "--env",
        action="append",
        help="Additional environment variables (format: KEY=VALUE)",
    )
    parser.add_argument(
        "--output", "-o", help="Save configuration to file instead of printing"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty print JSON (default: True)",
    )

    args = parser.parse_args()

    generator = MCPConfigGenerator()

    try:
        if args.quick:
            # Quick mode with command line arguments
            additional_env = {}
            if args.env:
                for env_var in args.env:
                    if "=" in env_var:
                        key, value = env_var.split("=", 1)
                        additional_env[key.strip()] = value.strip()

            config = generator.generate_config(
                server_name=args.server_name,
                python_path=args.python_path,
                working_directory=args.working_directory,
                db_path=args.db_path,
                additional_env=additional_env if additional_env else None,
                module_name="oasis.mcp_server",
            )
        else:
            # Interactive mode
            config = generator.interactive_config()

        # Print configuration info
        print_config_info(config)

        # Output the configuration
        json_output = json.dumps(config, indent=2 if args.pretty else None)

        if args.output:
            # Save to file
            with open(args.output, "w") as f:
                f.write(json_output)
            print(f"\nConfiguration saved to: {args.output}")
        else:
            # Print to terminal
            print("\nMCP Configuration (copy and paste this into your MCP client):")
            print("=" * 70)
            print(json_output)
            print("=" * 70)
            print(
                "\nCopy the JSON above and paste it into your MCP client configuration."
            )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
