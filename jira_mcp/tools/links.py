"""Issue link type tools: list available link types."""

from __future__ import annotations

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_issue_link_types_list",
        annotations={"readOnlyHint": True},
    )
    async def list_issue_link_types(
        ctx: Context = None,
    ) -> dict:
        """List all available issue link types.

        Shows link types like Blocks, Cloners, Duplicate, Relates, etc.
        Each type has an inward and outward label.
        Use the 'name' field with jira_issues_link to create links.
        Returns: {total, link_types: [{id, name, inward, outward}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get("/issueLinkType")
        except JiraApiError as e:
            raise ToolError(str(e))

        link_types = [
            {
                "id": lt.get("id"),
                "name": lt.get("name"),
                "inward": lt.get("inward"),
                "outward": lt.get("outward"),
            }
            for lt in data.get("issueLinkTypes", [])
        ]
        return {"total": len(link_types), "link_types": link_types}
