import config


def test_load_dotenv_parses_common_shapes(tmp_path):
    p = tmp_path / ".env"
    p.write_text(
        "# komentar\n"
        "\n"
        "ANTHROPIC_API_KEY=sk-ant-abc\n"
        'QUOTED="v uvozovkach"\n'
        "SINGLE='apostrof'\n"
        "export EXPORTED=hodnota\n"
        "S_MEZERAMI = kolem \n"
        "PRAZDNY=\n",
        encoding="utf-8")
    env = {}
    config._load_dotenv(str(p), env=env)
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-abc"
    assert env["QUOTED"] == "v uvozovkach"
    assert env["SINGLE"] == "apostrof"
    assert env["EXPORTED"] == "hodnota"
    assert env["S_MEZERAMI"] == "kolem"
    assert env["PRAZDNY"] == ""


def test_load_dotenv_does_not_override_real_env(tmp_path):
    """Proměnná z prostředí má přednost - .env je jen fallback."""
    p = tmp_path / ".env"
    p.write_text("ANTHROPIC_API_KEY=ze-souboru\n", encoding="utf-8")
    env = {"ANTHROPIC_API_KEY": "z-prostredi"}
    config._load_dotenv(str(p), env=env)
    assert env["ANTHROPIC_API_KEY"] == "z-prostredi"


def test_load_dotenv_missing_file_is_noop(tmp_path):
    env = {}
    config._load_dotenv(str(tmp_path / "neexistuje.env"), env=env)
    assert env == {}


def test_load_dotenv_ignores_junk_lines(tmp_path):
    p = tmp_path / ".env"
    p.write_text("bez rovnitka\n=bez_jmena\nOK=1\n", encoding="utf-8")
    env = {}
    config._load_dotenv(str(p), env=env)
    assert env == {"OK": "1"}


def test_stylist_config_defaults_present():
    """`STYLIST_TIMEOUT_SECONDS`/`STYLIST_MAX_CHARS`/`STYLIST_REPORT_REJECTED_TEXT`
    mají pevný bezpečný default beze změny. `CODEX_MODEL`/`STYLIST_ACCEPT_FS_RISK`
    jsou VĚDOMÉ per-instalační rozhodnutí vlastníka repa (viz komentáře u nich
    v config.py) - test proto jen ověří přítomnost + typ, ne konkrétní hodnotu.
    Bezpečná hodnota `STYLIST_ACCEPT_FS_RISK is False` je pořád ta, se kterou
    `python main.py polish` odmítne běžet po čerstvém `git clone` bez tohohle
    ručního kroku - `polish()` samo tu bránu vynucuje (spec kolo 20 BLOCKING),
    tenhle test to jen neduplikuje na konkrétní hodnotu."""
    import config
    assert isinstance(config.CODEX_MODEL, str)
    assert config.STYLIST_TIMEOUT_SECONDS == 180
    assert config.STYLIST_MAX_CHARS == 60_000
    assert config.STYLIST_ACCEPT_FS_RISK in (True, False)
    assert config.STYLIST_REPORT_REJECTED_TEXT is False


def test_main_has_module_level_imports_for_polish():
    import main
    for attr in ("_dt", "hashlib", "sqlite3", "time", "concordance", "glossary"):
        assert hasattr(main, attr), attr
