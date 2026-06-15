import pytest


@pytest.fixture(autouse=True)
def dummy_jira_env(monkeypatch):
    """Provide harmless Jira settings so the server lifespan can build a
    client during tests. No network call is ever made: tool *listing* and
    config parsing never hit Jira."""
    monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "dummy-token")
    monkeypatch.delenv("JIRA_DRY_RUN", raising=False)
