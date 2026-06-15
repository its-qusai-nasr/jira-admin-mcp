"""Status tools: search statuses across the instance."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_statuses_search",
        annotations={"readOnlyHint": True},
    )
    async def search_statuses(
        query: Annotated[str | None, "Search by status name substring, e.g. 'Done', 'Progress'"] = None,
        project_key: Annotated[str | None, "Filter statuses by project"] = None,
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """Search for statuses across the Jira instance.

        Returns statuses with their category (TO_DO, IN_PROGRESS, DONE).
        Use jira_projects_get_statuses for statuses grouped by issue type in a project.
        Returns: {total, statuses: [{id, name, category, project_key}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params: dict = {"maxResults": min(max_results, 200)}
        if query:
            params["searchString"] = query
        if project_key:
            params["projectId"] = project_key  # API accepts projectId

        try:
            data = await client.get("/statuses/search", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        statuses = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "category": s.get("statusCategory"),
                "scope_project": s.get("scope", {}).get("project", {}).get("id") if s.get("scope") else None,
            }
            for s in data.get("values", [])
        ]
        return {"total": data.get("total", len(statuses)), "statuses": statuses}
