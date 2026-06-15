"""Load and validate Jira connection settings from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    email: str
    api_token: str
    dry_run: bool = False

    @property
    def api_base(self) -> str:
        return f"{self.base_url.rstrip('/')}/rest/api/3"

    @property
    def auth(self) -> tuple[str, str]:
        return (self.email, self.api_token)


def load_config() -> JiraConfig:
    """Load config from environment. Checks parent directories for .env."""
    # Walk up from package dir to find .env
    search = Path(__file__).resolve().parent
    for _ in range(5):
        env_path = search / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            break
        search = search.parent

    base_url = os.environ.get("JIRA_BASE_URL")
    email = os.environ.get("JIRA_EMAIL")
    api_token = os.environ.get("JIRA_API_TOKEN")
    dry_run = os.environ.get("JIRA_DRY_RUN", "false").lower() in ("true", "1", "yes")

    missing = []
    if not base_url:
        missing.append("JIRA_BASE_URL")
    if not email:
        missing.append("JIRA_EMAIL")
    if not api_token:
        missing.append("JIRA_API_TOKEN")
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Set them in .env or export them."
        )

    return JiraConfig(
        base_url=base_url,
        email=email,
        api_token=api_token.strip('"'),
        dry_run=dry_run,
    )
