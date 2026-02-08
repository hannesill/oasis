"""Dataset definitions with modality-based filtering.

This module provides:
- Modality enum: Data types available in a dataset (TABULAR, NOTES, etc.)
- DatasetDefinition: Dataset metadata with modalities
- DatasetRegistry: Registry for managing dataset definitions
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from oasis.core.exceptions import DatasetError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Maximum file size for custom dataset JSON files (1MB)
# Prevents memory exhaustion from malicious/oversized files
MAX_DATASET_FILE_SIZE = 1024 * 1024


class Modality(Enum):
    """Data modalities available in a dataset.

    Modalities describe what kinds of data a dataset contains. Tools declare
    which modalities they require, and only datasets with those modalities
    will have the tool available.

    This is intentionally high-level. Fine-grained data discovery (which tables
    exist, what columns they have) is handled by schema introspection tools
    and the LLM's ability to write adaptive SQL.
    """

    TABULAR = auto()  # Structured tables (facilities, demographics, etc.)


@dataclass
class DatasetDefinition:
    """Dataset definition with modality declarations.

    Attributes:
        name: Unique identifier for the dataset
        description: Human-readable description
        version: Dataset version string
        file_listing_url: URL for downloading dataset files
        subdirectories_to_scan: Directories to scan for data files
        default_duckdb_filename: Default filename for local DuckDB database
        primary_verification_table: Table to check for dataset verification
        modalities: Immutable set of data modalities (TABULAR, etc.)
    """

    name: str
    description: str = ""
    version: str = "1.0"
    file_listing_url: str | None = None
    subdirectories_to_scan: list[str] = field(default_factory=list)
    default_duckdb_filename: str | None = None
    primary_verification_table: str | None = None

    # Modality declarations (immutable)
    modalities: frozenset[Modality] = field(default_factory=frozenset)

    # Filesystem directory -> canonical schema name
    # e.g. {"": "vf"} maps root-level files to the "vf" schema
    schema_mapping: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize computed fields."""
        if not self.default_duckdb_filename:
            self.default_duckdb_filename = f"{self.name.replace('-', '_')}.duckdb"


class DatasetRegistry:
    """Registry for managing dataset definitions.

    This class maintains a global registry of available datasets with
    enhanced capability metadata.
    """

    _registry: ClassVar[dict[str, DatasetDefinition]] = {}

    @classmethod
    def register(cls, dataset: DatasetDefinition):
        """Register a dataset in the registry.

        Args:
            dataset: DatasetDefinition to register
        """
        cls._registry[dataset.name.lower()] = dataset

    @classmethod
    def get(cls, name: str) -> DatasetDefinition | None:
        """Get a dataset by name.

        Args:
            name: Dataset name (case-insensitive)

        Returns:
            DatasetDefinition if found, None otherwise
        """
        return cls._registry.get(name.lower())

    @classmethod
    def list_all(cls) -> list[DatasetDefinition]:
        """Get all registered datasets.

        Returns:
            List of all DatasetDefinition objects
        """
        return list(cls._registry.values())

    @classmethod
    def get_active(cls) -> DatasetDefinition:
        """Get the currently active dataset definition.

        This method retrieves the active dataset from config and returns
        its definition. Raises an error if no active dataset is configured.

        Returns:
            DatasetDefinition for the active dataset

        Raises:
            DatasetError: If no active dataset is configured or dataset not found
        """
        # Import here to avoid circular dependency
        from oasis.config import get_active_dataset

        active_ds_name = get_active_dataset()
        if not active_ds_name:
            raise DatasetError(
                "No active dataset configured. "
                "Use `set_dataset('dataset-name')` to select a dataset."
            )

        ds_def = cls.get(active_ds_name)
        if not ds_def:
            raise DatasetError(
                f"Active dataset '{active_ds_name}' not found in registry. "
                f"Available datasets: {', '.join(d.name for d in cls.list_all())}"
            )

        return ds_def

    @classmethod
    def reset(cls):
        """Clear registry and re-register built-in datasets."""
        cls._registry.clear()
        cls._register_builtins()

    @classmethod
    def load_custom_datasets(cls, custom_dir: Path) -> None:
        """Load custom dataset definitions from JSON files.

        JSON files can specify modalities as string arrays:
            "modalities": ["TABULAR", "NOTES"]

        If not specified, defaults to TABULAR modality.

        Args:
            custom_dir: Directory containing custom dataset JSON files
        """
        if not custom_dir.exists():
            logger.debug(f"Custom datasets directory does not exist: {custom_dir}")
            return

        for f in custom_dir.glob("*.json"):
            try:
                # Check file size to prevent DoS via large files
                if f.stat().st_size > MAX_DATASET_FILE_SIZE:
                    logger.warning(
                        f"Dataset file too large (>{MAX_DATASET_FILE_SIZE} bytes), "
                        f"skipping: {f}"
                    )
                    continue

                data = json.loads(f.read_text())

                # Convert string arrays to enum frozensets
                if "modalities" in data:
                    data["modalities"] = frozenset(
                        Modality[m] for m in data["modalities"]
                    )
                else:
                    # Default: tabular data
                    data["modalities"] = frozenset({Modality.TABULAR})

                # Default empty dict for schema mapping
                data.setdefault("schema_mapping", {})

                ds = DatasetDefinition(**data)
                cls.register(ds)
                logger.debug(f"Loaded custom dataset: {ds.name}")
            except KeyError as e:
                logger.warning(
                    f"Failed to load custom dataset from {f}: "
                    f"Invalid modality name: {e}"
                )
            except Exception as e:
                logger.warning(f"Failed to load custom dataset from {f}: {e}")

    @classmethod
    def _register_builtins(cls):
        """Register built-in datasets."""
        vf_ghana = DatasetDefinition(
            name="vf-ghana",
            description="Virtue Foundation Ghana Healthcare Facilities",
            primary_verification_table="vf.facilities",
            modalities=frozenset({Modality.TABULAR}),
            schema_mapping={"": "vf"},
        )

        cls.register(vf_ghana)


# Initialize registry
DatasetRegistry._register_builtins()
