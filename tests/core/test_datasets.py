"""Tests for oasis.core.datasets module.

Tests cover:
- Modality enum
- DatasetDefinition with modalities
- DatasetRegistry with enhanced datasets
- JSON loading with modalities
"""

import json
import tempfile
from pathlib import Path

from oasis.core.datasets import (
    DatasetDefinition,
    DatasetRegistry,
    Modality,
)


class TestEnums:
    """Test Modality enum."""

    def test_modality_enum_values(self):
        """Test that all expected modalities are defined."""
        assert Modality.TABULAR


class TestDatasetDefinition:
    """Test DatasetDefinition."""

    def test_dataset_definition_with_modalities(self):
        """Test creating dataset with explicit modalities."""
        ds = DatasetDefinition(
            name="test-dataset",
            modalities=frozenset({Modality.TABULAR}),
        )

        assert Modality.TABULAR in ds.modalities

    def test_default_duckdb_filename_generation(self):
        """Test that default DuckDB filename is auto-generated."""
        ds = DatasetDefinition(name="my-test-dataset")
        assert ds.default_duckdb_filename == "my_test_dataset.duckdb"

    def test_custom_duckdb_filename(self):
        """Test setting custom DuckDB filename."""
        ds = DatasetDefinition(
            name="test-dataset",
            default_duckdb_filename="custom.duckdb",
        )
        assert ds.default_duckdb_filename == "custom.duckdb"

    def test_modalities_are_immutable(self):
        """Test that modalities are immutable frozensets."""
        ds = DatasetDefinition(
            name="test-dataset",
            modalities=frozenset({Modality.TABULAR}),
        )
        assert isinstance(ds.modalities, frozenset)

    def test_schema_mapping_defaults_to_empty(self):
        """Test that schema_mapping defaults to empty dict."""
        ds = DatasetDefinition(name="test-dataset")
        assert ds.schema_mapping == {}


class TestDatasetRegistry:
    """Test DatasetRegistry with enhanced datasets."""

    def test_registry_builtin_datasets(self):
        """Test that built-in datasets are registered."""
        DatasetRegistry.reset()

        vf_ghana = DatasetRegistry.get("vf-ghana")
        assert vf_ghana is not None
        assert vf_ghana.name == "vf-ghana"

    def test_vf_ghana_modalities(self):
        """Test that VF Ghana has expected modalities."""
        DatasetRegistry.reset()
        vf_ghana = DatasetRegistry.get("vf-ghana")

        assert Modality.TABULAR in vf_ghana.modalities

    def test_register_custom_dataset(self):
        """Test registering a custom dataset."""
        custom_ds = DatasetDefinition(
            name="custom-dataset",
            modalities=frozenset({Modality.TABULAR}),
        )

        DatasetRegistry.register(custom_ds)

        retrieved = DatasetRegistry.get("custom-dataset")
        assert retrieved is not None
        assert retrieved.name == "custom-dataset"

    def test_case_insensitive_lookup(self):
        """Test that dataset lookup is case-insensitive."""
        DatasetRegistry.reset()

        # All should work
        assert DatasetRegistry.get("vf-ghana") is not None
        assert DatasetRegistry.get("VF-GHANA") is not None
        assert DatasetRegistry.get("Vf-Ghana") is not None

    def test_list_all_datasets(self):
        """Test listing all datasets."""
        DatasetRegistry.reset()
        all_datasets = DatasetRegistry.list_all()

        assert len(all_datasets) >= 1
        names = [ds.name for ds in all_datasets]
        assert "vf-ghana" in names

    def test_vf_ghana_schema_mapping(self):
        """Test VF Ghana has correct schema mappings."""
        DatasetRegistry.reset()
        ds = DatasetRegistry.get("vf-ghana")
        assert ds.schema_mapping == {"": "vf"}
        assert ds.primary_verification_table == "vf.facilities"


class TestDatasetRegistryEdgeCases:
    """Test registry edge cases that could cause silent data loss or crashes."""

    def test_register_overwrites_existing(self):
        """Registering a dataset with an existing name overwrites the old one.

        This is important because custom datasets could shadow built-in ones.
        """
        DatasetRegistry.reset()
        original = DatasetRegistry.get("vf-ghana")
        assert original is not None

        replacement = DatasetDefinition(
            name="vf-ghana",
            description="Overwritten",
            modalities=frozenset({Modality.TABULAR}),
        )
        DatasetRegistry.register(replacement)

        retrieved = DatasetRegistry.get("vf-ghana")
        assert retrieved.description == "Overwritten"
        assert Modality.TABULAR in retrieved.modalities

        # Clean up
        DatasetRegistry.reset()

    def test_reset_restores_builtins(self):
        """reset() clears custom datasets and restores all built-ins."""
        DatasetRegistry.register(
            DatasetDefinition(name="ephemeral-custom", modalities=frozenset())
        )
        assert DatasetRegistry.get("ephemeral-custom") is not None

        DatasetRegistry.reset()
        assert DatasetRegistry.get("ephemeral-custom") is None
        assert DatasetRegistry.get("vf-ghana") is not None

    def test_get_nonexistent_returns_none(self):
        """get() returns None for unknown dataset names."""
        DatasetRegistry.reset()
        assert DatasetRegistry.get("nonexistent-dataset-xyz") is None

    def test_get_active_no_config_raises(self, monkeypatch):
        """get_active() raises DatasetError when no dataset is configured."""
        import pytest

        import oasis.config as cfg
        from oasis.core.exceptions import DatasetError

        monkeypatch.setattr(cfg, "get_active_dataset", lambda: None)

        with pytest.raises(DatasetError, match="No active dataset"):
            DatasetRegistry.get_active()

    def test_get_active_unknown_dataset_raises(self, monkeypatch):
        """get_active() raises DatasetError when config points to unknown dataset."""
        import pytest

        import oasis.config as cfg
        from oasis.core.exceptions import DatasetError

        monkeypatch.setattr(cfg, "get_active_dataset", lambda: "no-such-dataset")

        with pytest.raises(DatasetError, match="not found in registry"):
            DatasetRegistry.get_active()

    def test_custom_json_oversized_file_skipped(self, tmp_path):
        """JSON files exceeding MAX_DATASET_FILE_SIZE are skipped."""
        from oasis.core.datasets import MAX_DATASET_FILE_SIZE

        big_file = tmp_path / "huge.json"
        big_file.write_text("x" * (MAX_DATASET_FILE_SIZE + 1))

        DatasetRegistry.reset()
        DatasetRegistry.load_custom_datasets(tmp_path)
        # The oversized file should not crash and should not register anything
        assert DatasetRegistry.get("huge") is None

    def test_custom_json_with_schema_mapping(self, tmp_path):
        """Custom JSON with schema_mapping fields loads correctly."""
        json_data = {
            "name": "custom-mapped",
            "schema_mapping": {"": "custom_schema"},
        }
        (tmp_path / "mapped.json").write_text(json.dumps(json_data))

        DatasetRegistry.reset()
        DatasetRegistry.load_custom_datasets(tmp_path)

        ds = DatasetRegistry.get("custom-mapped")
        assert ds is not None
        assert ds.schema_mapping == {"": "custom_schema"}

        DatasetRegistry.reset()

    def test_load_custom_datasets_nonexistent_dir(self, tmp_path):
        """load_custom_datasets with nonexistent directory does not crash."""
        DatasetRegistry.reset()
        DatasetRegistry.load_custom_datasets(tmp_path / "nonexistent")
        # Should not raise, just return silently
        assert DatasetRegistry.get("vf-ghana") is not None

    def test_load_custom_datasets_malformed_json(self, tmp_path):
        """Malformed JSON files are skipped gracefully."""
        (tmp_path / "bad.json").write_text("{invalid json!!!}")

        DatasetRegistry.reset()
        DatasetRegistry.load_custom_datasets(tmp_path)
        # Should not crash; malformed file is simply skipped
        assert DatasetRegistry.get("vf-ghana") is not None


class TestJSONLoading:
    """Test JSON loading with modalities."""

    def test_json_loading_with_modalities(self):
        """Test loading dataset with explicit modalities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_data = {
                "name": "test-json-dataset",
                "description": "Test dataset from JSON",
                "modalities": ["TABULAR"],
            }
            json_path = Path(tmpdir) / "test.json"
            json_path.write_text(json.dumps(json_data))

            DatasetRegistry.reset()
            DatasetRegistry.load_custom_datasets(Path(tmpdir))

            ds = DatasetRegistry.get("test-json-dataset")
            assert ds is not None
            assert Modality.TABULAR in ds.modalities

    def test_json_loading_defaults_when_not_specified(self):
        """Test that default modalities are applied when not in JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_data = {
                "name": "test-minimal-dataset",
                "description": "Minimal dataset without modalities",
            }
            json_path = Path(tmpdir) / "minimal.json"
            json_path.write_text(json.dumps(json_data))

            DatasetRegistry.reset()
            DatasetRegistry.load_custom_datasets(Path(tmpdir))

            ds = DatasetRegistry.get("test-minimal-dataset")
            assert ds is not None
            # Default modality: TABULAR
            assert Modality.TABULAR in ds.modalities

    def test_json_loading_invalid_modality(self):
        """Test that invalid modality names are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_data = {
                "name": "test-invalid-modality",
                "modalities": ["INVALID_MODALITY"],
            }
            json_path = Path(tmpdir) / "invalid.json"
            json_path.write_text(json.dumps(json_data))

            DatasetRegistry.reset()
            DatasetRegistry.load_custom_datasets(Path(tmpdir))

            # Should not be registered due to invalid modality
            ds = DatasetRegistry.get("test-invalid-modality")
            assert ds is None

    def test_json_loading_tabular_modality(self):
        """Test loading dataset with TABULAR modality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_data = {
                "name": "test-tabular-dataset",
                "modalities": ["TABULAR"],
            }
            json_path = Path(tmpdir) / "tabular.json"
            json_path.write_text(json.dumps(json_data))

            DatasetRegistry.reset()
            DatasetRegistry.load_custom_datasets(Path(tmpdir))

            ds = DatasetRegistry.get("test-tabular-dataset")
            assert ds is not None
            assert len(ds.modalities) == 1
            assert Modality.TABULAR in ds.modalities
