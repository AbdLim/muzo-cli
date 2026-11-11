"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def isolated_default_config(tmp_path_factory, monkeypatch):
    """Keep tests from reading or writing the developer's real muzo config."""
    fake = tmp_path_factory.mktemp("muzo-config") / "config.toml"
    monkeypatch.setattr("muzo.config.get_default_config_path", lambda: fake)
    return fake
