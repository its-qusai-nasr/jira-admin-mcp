"""Comment tools: list and add comments on issues."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError
from jira_mcp.helpers import text_to_adf, is_adf


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_comments_list",
        annotations={"readOnlyHint": True},
    )
    async def list_comments(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123'"],
        max_results: Annotated[int, "Maximum comments to return. Default: 25"] = 25,
        order_by: Annotated[str, "'created' (oldest first) or '-created' (newest first). Default: '-created'"] = "-created",
        ctx: Context = None,
    ) -> dict:
        """List comments on a Jira issue.

        Returns comments with author, body, and timestamps. Sorted newest-first by default.
        Returns: {issue_key, total, comments: [{id, author, body, created, updated}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(
                f"/issue/{issue_key}/comment",
                params={"maxResults": min(max_results, 100), "orderBy": order_by},
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        comments = [
            {
                "id": c.get("id"),
                "author": c.get("author", {}).get("displayName"),
                "body": c.get("body"),
                "created": c.get("created"),
                "updated": c.get("updated"),
            }
            for c in data.get("comments", [])
        ]
        return {
            "issue_key": issue_key,
            "total": data.get("total", len(comments)),
            "comments": comments,
        }

    @mcp.tool(
        name="jira_comments_add",
        annotations={"readOnlyHint": False},
    )
    async def add_comment(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123'"],
        body: Annotated[str, "Comment text. Plain text is auto-converted to ADF format."],
        ctx: Context = None,
    ) -> dict:
        """Add a comment to a Jira issue.

        Accepts plain text (auto-converted) or raw ADF JSON.
        Returns: {id, issue_key, author, created}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        adf_body = text_to_adf(body) if not is_adf(body) else body

        try:
            data = await client.post(f"/issue/{issue_key}/comment", json={"body": adf_body})
        except JiraApiError as e:
            raise ToolError(str(e))

        return {
            "id": data.get("id"),
            "issue_key": issue_key,
            "author": data.get("author", {}).get("displayName"),
            "created": data.get("created"),
        }
