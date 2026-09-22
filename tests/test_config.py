import importlib
import os

import config as config_module


def test_project_dir_defaults_to_dot(monkeypatch):
    """`importlib.reload` mutuje `config` V MÍSTĚ - je to sdílený
    singleton, co importují i JINÉ testovací soubory. `monkeypatch.undo()`
    + druhý `reload` v `finally` VRACÍ modul do stavu před testem, jinak
    by tenhle test natrvalo poškodil `config.PROJECT_DIR`/`DATA_DIR`/...
    pro zbytek testovací session (samotný `monkeypatch` vrátí jen env
    proměnnou, ne důsledek reloadu, co už na ní stihl postavit)."""
    monkeypatch.delenv("BOOK_TRANSLATOR_PROJECT_DIR", raising=False)
    importlib.reload(config_module)
    try:
        assert config_module.PROJECT_DIR == "."
        assert config_module.DATA_DIR == os.path.join(".", "data")
        assert config_module.OUTPUT_DIR == os.path.join(".", "output")
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)


def test_project_dir_reads_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("BOOK_TRANSLATOR_PROJECT_DIR", str(tmp_path))
    importlib.reload(config_module)
    try:
        assert config_module.PROJECT_DIR == str(tmp_path)
        assert config_module.DATA_DIR == os.path.join(str(tmp_path), "data")
        assert config_module.DB_PATH == os.path.join(str(tmp_path), "data", "state.sqlite3")
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)


def test_codex_model_has_zero_price_entries():
    assert config_module.PRICE_IN_PER_MTOK[config_module.CODEX_MODEL] == 0.0
    assert config_module.PRICE_OUT_PER_MTOK[config_module.CODEX_MODEL] == 0.0


def test_codex_translate_timeout_seconds_is_positive_int():
    assert isinstance(config_module.CODEX_TRANSLATE_TIMEOUT_SECONDS, int)
    assert config_module.CODEX_TRANSLATE_TIMEOUT_SECONDS > 0


def test_claude_cli_critic_model_has_zero_price_entries():
    key = f"{config_module.MODEL_CRITIC}-cli"
    assert config_module.PRICE_IN_PER_MTOK[key] == 0.0
    assert config_module.PRICE_OUT_PER_MTOK[key] == 0.0


def test_claude_cli_critic_timeout_seconds_is_positive_int():
    assert isinstance(config_module.CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS, int)
    assert config_module.CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS > 0
