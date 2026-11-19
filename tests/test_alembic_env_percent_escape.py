"""
Regressao: migrations/env.py precisa escapar "%" na DATABASE_URL antes de
config.set_main_option, porque o ConfigParser do Alembic interpreta "%"
como inicio de interpolacao. Sem o escape, uma senha com "%" (como a gerada
em 16/11) quebra todo deploy com "ValueError: invalid interpolation syntax".
"""
from alembic.config import Config

FAKE_URL_WITH_PERCENT = "postgresql://postgres:ab%cd1234@host.example:5432/railway"
FAKE_URL_NO_PERCENT = "postgresql://postgres:ab$cd1234@host.example:5432/railway"


def test_url_sem_escape_quebra_com_percent():
    config = Config()
    try:
        config.set_main_option("sqlalchemy.url", FAKE_URL_WITH_PERCENT)
    except ValueError as e:
        assert "interpolation" in str(e).lower()
    else:
        raise AssertionError(
            "Esperava ValueError (interpolation syntax) sem o escape"
        )


def test_url_sem_percent_nunca_quebrou():
    config = Config()
    config.set_main_option("sqlalchemy.url", FAKE_URL_NO_PERCENT)
    assert config.get_main_option("sqlalchemy.url") == FAKE_URL_NO_PERCENT


def test_escape_percent_preserva_url_original_no_round_trip():
    config = Config()
    url_escapada = FAKE_URL_WITH_PERCENT.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", url_escapada)
    assert config.get_main_option("sqlalchemy.url") == FAKE_URL_WITH_PERCENT


def test_escape_percent_e_idempotente_sem_percent():
    config = Config()
    url_escapada = FAKE_URL_NO_PERCENT.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", url_escapada)
    assert config.get_main_option("sqlalchemy.url") == FAKE_URL_NO_PERCENT


def test_env_py_usa_replace_percent_antes_de_set_main_option():
    """Trava estrutural: garante que a linha do fix nao seja revertida."""
    texto = open("migrations/env.py", encoding="utf-8").read()
    assert 'DATABASE_URL.replace("%", "%%")' in texto
