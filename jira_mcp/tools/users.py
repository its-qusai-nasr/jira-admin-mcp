"""User tools: search and get user details."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError
from jira_mcp.helpers import format_user


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_users_search",
        annotations={"readOnlyHint": True},
    )
    async def search_users(
        query: Annotated[str, "Search by email or display name. Examples: 'jane.doe@example.com', 'Jane', 'jdoe'"],
        max_results: Annotated[int, "Max results. Default: 10"] = 10,
        ctx: Context = None,
    ) -> dict:
        """Search for Jira users by email or display name.

        Always use this to look up a user's account_id before adding them to groups or assigning issues.
        Not this when you already have the account_id: use jira_users_get instead.
        Returns: {total, users: [{account_id, display_name, email, active}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(
                "/user/search",
                params={"query": query, "maxResults": min(max_results, 50)},
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        users = [format_user(u) for u in data if u.get("accountType") == "atlassian"]
        return {"total": len(users), "users": users}

    @mcp.tool(
        name="jira_users_get",
        annotations={"readOnlyHint": True},
    )
    async def get_user(
        account_id: Annotated[str, "Jira account ID, e.g. '712020:3d64f12e-90ed-4591-ad64-6ea6768bd9ff'"],
        ctx: Context = None,
    ) -> dict:
        """Get details for a specific Jira user by account ID.

        Use jira_users_search to find the account_id first.
        Returns: {account_id, display_name, email, active, groups}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get("/user", params={"accountId": account_id, "expand": "groups"})
        except JiraApiError as e:
            raise ToolError(str(e))

        result = format_user(data)
        groups = data.get("groups", {}).get("items", [])
        result["groups"] = [g.get("name") for g in groups]
        return result
