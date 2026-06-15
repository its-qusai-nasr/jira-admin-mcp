import pytest

from jira_mcp import config as config_mod
from jira_mcp.config import JiraConfig, load_config


def test_api_base_and_auth():
    cfg = JiraConfig(base_url="https://x.atlassian.net/", email="a@b.c", api_token="t")
    assert cfg.api_base == "https://x.atlassian.net/rest/api/3"
    assert cfg.auth == ("a@b.c", "t")


def test_load_config_reads_env():
    cfg = load_config()  # dummy env provided by the autouse fixture
    assert cfg.base_url == "https://example.atlassian.net"
    assert cfg.email == "test@example.com"
    assert cfg.api_token == "dummy-token"
    assert cfg.dry_run is False


@pytest.mark.parametrize(
    "value,expected",
    [("true", True), ("1", True), ("yes", True), ("false", False), ("no", False)],
)
def test_dry_run_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("JIRA_DRY_RUN", value)
    assert load_config().dry_run is expected


def test_api_token_quotes_stripped(monkeypatch):
    monkeypatch.setenv("JIRA_API_TOKEN", '"quoted-token"')
    assert load_config().api_token == "quoted-token"


def test_missing_vars_raise_with_names(monkeypatch):
    # Do not let a stray .env on disk satisfy the vars.
    monkeypatch.setattr(config_mod, "load_dotenv", lambda *a, **k: None)
    for var in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValueError) as exc:
        load_config()
    message = str(exc.value)
    assert "JIRA_BASE_URL" in message
    assert "JIRA_EMAIL" in message
    assert "JIRA_API_TOKEN" in message
