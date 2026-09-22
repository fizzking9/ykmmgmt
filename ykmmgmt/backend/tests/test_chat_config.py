"""Config wiring for the chat matcher — env names that must actually bind.

Regression guard for a silent misconfiguration: `.env.example` documented
`YKM_CHAT_SIMILARITY_THRESHOLD`, but the setting was a plain field named
`embedding_similarity_threshold`, so the prefixed var was ignored and every
deployment silently ran the 0.75 default instead of the tuned value.
"""

from app.core.config import Settings


def _fresh_settings() -> Settings:
    # Ignore any real .env so the assertions hold on a developer machine.
    return Settings(_env_file=None)


def test_threshold_default_sits_in_the_tuned_band():
    """Range, not an exact number — the tuned value moves whenever the knowledge base
    or the encoder changes, and a pinned assertion turns every re-tune into a test
    failure. The binding rule is `chat_similarity_threshold` above (>= 0.95 precision)."""
    default = _fresh_settings().chat_similarity_threshold
    assert 0.55 < default < 0.99, default


def test_documented_env_name_binds(monkeypatch):
    monkeypatch.setenv("YKM_CHAT_SIMILARITY_THRESHOLD", "0.83")
    assert Settings(_env_file=None).chat_similarity_threshold == 0.83


def test_bare_field_name_also_binds(monkeypatch):
    monkeypatch.setenv("chat_similarity_threshold", "0.7")
    assert Settings(_env_file=None).chat_similarity_threshold == 0.7


def test_encoder_stays_offline_unless_downloads_are_allowed(monkeypatch):
    """Offline by default: a blocked huggingface.co otherwise stalls startup for
    minutes in retry back-off (seen on the dev server after a reload)."""
    assert _fresh_settings().embedding_allow_download is False
    monkeypatch.setenv("YKM_EMBEDDING_ALLOW_DOWNLOAD", "true")
    assert Settings(_env_file=None).embedding_allow_download is True
