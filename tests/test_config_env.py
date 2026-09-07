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
