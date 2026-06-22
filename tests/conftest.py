import pytest

import jira_mcp.config as config_mod


@pytest.fixture(autouse=True)
def dummy_jira_env(monkeypatch):
    """Make every test hermetic: provide harmless Jira settings and stop
    config loading from reading any real .env that happens to be on disk
    (e.g. one a developer created for live testing). No network is ever made;
    tool *listing* and config parsing never hit Jira."""
    monkeypatch.setattr(config_mod, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "dummy-token")
    monkeypatch.delenv("JIRA_DRY_RUN", raising=False)
