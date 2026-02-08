from pathlib import Path

import pytest

from oasis.config import (
    VALID_BACKENDS,
    get_active_backend,
    get_dataset_parquet_root,
    get_default_database_path,
    set_active_backend,
)
from oasis.core.datasets import DatasetRegistry


def test_get_dataset_known():
    """Test that a known dataset can be retrieved from the registry."""
    ds = DatasetRegistry.get("vf-ghana")
    assert ds is not None
    assert ds.default_duckdb_filename == "vf_ghana.duckdb"


def test_get_dataset_unknown():
    """Test that an unknown dataset returns None."""
    assert DatasetRegistry.get("not-a-dataset") is None


def test_default_paths(tmp_path, monkeypatch):
    # Redirect default dirs to a temp location
    import oasis.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "_DEFAULT_DATABASES_DIR", tmp_path / "dbs")
    monkeypatch.setattr(cfg_mod, "_DEFAULT_PARQUET_DIR", tmp_path / "parquet")
    db_path = get_default_database_path("vf-ghana")
    raw_path = get_dataset_parquet_root("vf-ghana")
    # They should be Path objects and exist
    assert isinstance(db_path, Path)
    assert db_path.parent.exists()
    assert isinstance(raw_path, Path)
    assert raw_path.exists()


def test_raw_path_includes_dataset_name(tmp_path, monkeypatch):
    import oasis.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "_DEFAULT_PARQUET_DIR", tmp_path / "parquet")
    raw_path = get_dataset_parquet_root("vf-ghana")
    assert "vf-ghana" in str(raw_path)


def test_find_project_root_search(tmp_path, monkeypatch):
    from oasis.config import _find_project_root_from_cwd

    # Case 1: No data dir -> returns cwd
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        assert _find_project_root_from_cwd() == tmp_path

    # Case 2: Data dir exists but empty (invalid) -> returns cwd
    data_dir = tmp_path / "oasis_data"
    data_dir.mkdir()
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        assert _find_project_root_from_cwd() == tmp_path

    # Case 3: Valid data dir (has databases/) -> returns root
    (data_dir / "databases").mkdir()
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        assert _find_project_root_from_cwd() == tmp_path

    # Case 4: Valid data dir -> returns root from subdir
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    with monkeypatch.context() as m:
        m.chdir(subdir)
        assert _find_project_root_from_cwd() == tmp_path


# ----------------------------------------------------------------
# Backend configuration tests
# ----------------------------------------------------------------


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Fixture that isolates config file access to a temp directory."""
    import oasis.config as cfg_mod

    data_dir = tmp_path / "oasis_data"
    data_dir.mkdir()

    monkeypatch.setattr(cfg_mod, "_PROJECT_DATA_DIR", data_dir)
    monkeypatch.setattr(cfg_mod, "_DEFAULT_DATABASES_DIR", data_dir / "databases")
    monkeypatch.setattr(cfg_mod, "_DEFAULT_PARQUET_DIR", data_dir / "parquet")
    monkeypatch.setattr(cfg_mod, "_RUNTIME_CONFIG_PATH", data_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_CUSTOM_DATASETS_DIR", data_dir / "datasets")

    return data_dir / "config.json"


class TestGetActiveBackend:
    """Tests for get_active_backend function."""

    def test_default_is_duckdb(self, isolated_config, monkeypatch):
        """Default backend is duckdb when nothing is configured."""
        # Clear any env var
        monkeypatch.delenv("OASIS_BACKEND", raising=False)

        assert get_active_backend() == "duckdb"

    def test_env_var_takes_priority(self, isolated_config, monkeypatch):
        """OASIS_BACKEND env var takes priority over config file."""
        isolated_config.write_text('{"backend": "duckdb"}')
        monkeypatch.setenv("OASIS_BACKEND", "duckdb")

        assert get_active_backend() == "duckdb"

    def test_env_var_case_insensitive(self, isolated_config, monkeypatch):
        """OASIS_BACKEND env var is case-insensitive."""
        monkeypatch.setenv("OASIS_BACKEND", "DUCKDB")

        assert get_active_backend() == "duckdb"

    def test_config_file_used_when_no_env(self, isolated_config, monkeypatch):
        """Config file setting is used when no env var is set."""
        isolated_config.write_text('{"backend": "duckdb"}')
        monkeypatch.delenv("OASIS_BACKEND", raising=False)

        assert get_active_backend() == "duckdb"

    def test_config_file_case_insensitive(self, isolated_config, monkeypatch):
        """Config file backend setting is case-insensitive."""
        isolated_config.write_text('{"backend": "DUCKDB"}')
        monkeypatch.delenv("OASIS_BACKEND", raising=False)

        assert get_active_backend() == "duckdb"


class TestSetActiveBackend:
    """Tests for set_active_backend function."""

    def test_set_duckdb(self):
        """Can set backend to duckdb without error."""
        set_active_backend("duckdb")

    def test_case_insensitive(self):
        """Backend choice is case-insensitive."""
        set_active_backend("DUCKDB")

    def test_invalid_backend_raises_error(self):
        """Invalid backend raises ValueError."""
        with pytest.raises(ValueError, match="backend must be one of"):
            set_active_backend("invalid")


class TestValidBackends:
    """Tests for VALID_BACKENDS constant."""

    def test_contains_expected_backends(self):
        """VALID_BACKENDS contains duckdb."""
        assert "duckdb" in VALID_BACKENDS
