"""FastMCP server: Jira Cloud administration tools."""

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from jira_mcp.config import load_config
from jira_mcp.client import JiraClient

INSTRUCTIONS = """\
Jira Cloud administration server. Operates a Jira Cloud site via REST API v3
using an Atlassian account's email + API token. Examples below are illustrative.

TOOL ROUTING:
- Issue work (search, create, update, transition, delete, link, changelog): jira_issues_*
- Issue comments: jira_comments_*
- User lookup: jira_users_*
- Group membership + create/delete: jira_groups_*
- Project inspection, roles, versions, features: jira_projects_*
- Permission schemes: jira_permissions_*
- Custom field options: jira_fields_*
- Saved JQL filters: jira_filters_*
- Issue link types: jira_issue_link_types_list
- Status search: jira_statuses_search
- Workflow/screen/issue-type schemes: jira_workflows_*, jira_screens_*, jira_issuetypes_*
- Bulk operations: jira_bulk_*
- Async task polling (generic + bulk queue): jira_tasks_*

CONVENTIONS:
- Always identify users by email first (jira_users_search), then use account_id for writes.
- Always use issue keys (e.g. PROJ-123), not numeric issue IDs.
- For permission scheme changes: check current scheme, verify it's not shared, then modify.
- Custom field IDs look like "customfield_10001". Use jira_fields_search to find them by name.
- JQL queries go through jira_issues_search. Prefer targeted JQL over broad listing.
- For select/dropdown fields, set value as {"value": "Option Name"}.
- For user fields, set value as {"accountId": "..."}.

SAFETY:
- Never delete projects without explicit user confirmation.
- Never modify shared permission schemes: create a dedicated one first.
- Verify user identity (search by email) before group membership changes.
- Present a plan before modifying workflow schemes.

NAMING:
- Project keys: 2-5 uppercase letters (ENG, OPS, SUP)
- Groups: lowercase with hyphens (jira-developers, jira-administrators)
- Custom fields: Capitalized Words (Company Department, Story Points)
"""


@lifespan
async def app_lifespan(server):
    """Initialize shared Jira HTTP client at server startup."""
    config = load_config()
    client = JiraClient(config)
    try:
        yield {"client": client, "config": config}
    finally:
        await client.close()


mcp = FastMCP(
    name="jira-admin",
    instructions=INSTRUCTIONS,
    lifespan=app_lifespan,
    on_duplicate="error",
    mask_error_details=True,
)

# Import and register tool modules
from jira_mcp.tools import (  # noqa: E402
    issues, comments, users, groups, projects, permissions,
    fields, workflows, issuetypes, screens, bulk,
    filters, links, statuses, tasks,
)

issues.register(mcp)
comments.register(mcp)
users.register(mcp)
groups.register(mcp)
projects.register(mcp)
permissions.register(mcp)
fields.register(mcp)
workflows.register(mcp)
issuetypes.register(mcp)
screens.register(mcp)
bulk.register(mcp)
filters.register(mcp)
links.register(mcp)
statuses.register(mcp)
tasks.register(mcp)


def main():
    """Entry point for CLI."""
    mcp.run()


if __name__ == "__main__":
    main()
