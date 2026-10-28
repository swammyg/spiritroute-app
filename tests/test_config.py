from pathlib import Path

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"


def test_env_example_documents_exactly_the_defaults():
    assert Settings(_env_file=ENV_EXAMPLE) == Settings(_env_file=None)


def test_blank_qdrant_settings_mean_unset():
    settings = Settings(_env_file=None, qdrant_url="", qdrant_api_key="")
    assert settings.qdrant_url is None
    assert settings.qdrant_api_key is None


def test_cors_origins_are_split_and_trimmed():
    settings = Settings(_env_file=None, cors_origins=" http://a.test , http://b.test,, ")
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]
