"""Databricks configuration from environment variables.

All Databricks integration is optional. Tools degrade gracefully
when credentials are not configured.

Environment variables:
    DATABRICKS_HOST: Workspace URL (e.g., https://dbc-xxx.cloud.databricks.com)
    DATABRICKS_TOKEN: Personal access token
    OASIS_GENIE_SPACE_ID: Genie space ID for text-to-SQL queries
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabricksConfig:
    """Immutable Databricks connection config."""

    host: str | None
    token: str | None
    genie_space_id: str | None

    @property
    def is_configured(self) -> bool:
        """True if Databricks credentials are set."""
        return bool(self.host and self.token)

    @property
    def genie_available(self) -> bool:
        """True if Genie space is configured."""
        return self.is_configured and bool(self.genie_space_id)


def get_config() -> DatabricksConfig:
    """Read Databricks config from environment."""
    return DatabricksConfig(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
        genie_space_id=os.getenv("OASIS_GENIE_SPACE_ID"),
    )
