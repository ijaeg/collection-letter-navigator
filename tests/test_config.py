"""Tests for :mod:`collection_letter_navigator.config`.

Related: FR-04 AC2, FR-07 AC2, FR-20 AC2, §9
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import dotenv
import pytest

from collection_letter_navigator import config


def test_module_imports() -> None:
    """The configuration module imports and exposes its constants."""
    assert config.RETRIEVAL_TOP_K == 6
    assert config.MAX_CHUNK_CHARACTERS == 2_000


def test_fr20_ac2_chat_model_overridable_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """CHAT_MODEL in the environment replaces the default model."""
    monkeypatch.setenv("CHAT_MODEL", "test/model")
    try:
        assert importlib.reload(config).CHAT_MODEL == "test/model"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_nfr01_dotenv_is_loaded_before_settings_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A value from the project's .env file reaches config (NFR-01)."""
    seen: dict[str, Any] = {}

    def fake_load_dotenv(path: Path, override: bool = False) -> bool:
        seen["path"], seen["override"] = path, override
        os.environ["CHAT_MODEL"] = "from/dotenv"  # what the real .env would do
        return True

    monkeypatch.delenv("CHAT_MODEL", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", fake_load_dotenv)
    try:
        reloaded = importlib.reload(config)
        assert reloaded.CHAT_MODEL == "from/dotenv"
        assert seen == {"path": reloaded.PROJECT_ROOT / ".env", "override": False}
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_fr05_ac4_query_translation_switch_read_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QUERY_TRANSLATION=off disables the query-translation step."""
    monkeypatch.setenv("QUERY_TRANSLATION", "off")
    try:
        assert importlib.reload(config).QUERY_TRANSLATION_ENABLED is False
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_fr23_ac3_api_key_is_not_a_configuration_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the name of the key variable is a constant, never the key itself."""
    secret = "sk-or-v1-test-not-a-real-key"
    monkeypatch.setenv(config.OPENROUTER_API_KEY_ENV, secret)
    try:
        reloaded = importlib.reload(config)
        assert reloaded.OPENROUTER_API_KEY_ENV == "OPENROUTER_API_KEY"
        assert all(secret not in repr(value) for value in vars(reloaded).values())
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_d8_pinning_is_on_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pinning explicit references is the default since D-8 and can be switched off."""
    monkeypatch.delenv("PIN_EXPLICIT_REFERENCES", raising=False)
    try:
        assert importlib.reload(config).PIN_EXPLICIT_REFERENCES is True
        monkeypatch.setenv("PIN_EXPLICIT_REFERENCES", "off")
        assert importlib.reload(config).PIN_EXPLICIT_REFERENCES is False
    finally:
        monkeypatch.undo()
        importlib.reload(config)
