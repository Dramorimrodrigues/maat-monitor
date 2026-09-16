"""Fixtures compartilhadas — THEMIS Monitor. Copyright (c) 2026 Márcio Luis Amorim — MIT."""

import pytest


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Diretório de dados isolado: nenhum teste toca arquivos reais do usuário."""
    monkeypatch.setenv("THEMIS_HOME", str(tmp_path))
    return tmp_path
