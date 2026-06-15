"""Issue type tools: list, schemes, scheme mappings."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_issuetypes_list",
        annotations={"readOnlyHint": True},
    )
    async def list_issue_types(
        project_key: Annotated[str | None, "Project key to filter by. Leave empty for all issue types."] = None,
        ctx: Context = None,
    ) -> dict:
        """List issue types, optionally filtered by project.

        Returns: {total, issue_types: [{id, name, description, subtask, hierarchy_level}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]

        if project_key:
            # Need project ID first
            try:
                proj = await client.get(f"/project/{project_key}")
            except JiraApiError as e:
                raise ToolError(str(e))
            try:
                data = await client.get("/issuetype/project", params={"projectId": proj.get("id")})
            except JiraApiError as e:
                raise ToolError(str(e))
            types_list = data if isinstance(data, list) else data.get("values", data.get("issueTypes", []))
        else:
            try:
                data = await client.get("/issuetype")
            except JiraApiError as e:
                raise ToolError(str(e))
            types_list = data if isinstance(data, list) else []

        types = [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "description": t.get("description"),
                "subtask": t.get("subtask", False),
                "hierarchy_level": t.get("hierarchyLevel"),
            }
            for t in types_list
        ]
        return {"total": len(types), "issue_types": types}

    @mcp.tool(
        name="jira_issuetypes_get_schemes",
        annotations={"readOnlyHint": True},
    )
    async def get_issue_type_schemes(
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """List issue type schemes.

        Returns: {total, schemes: [{id, name, description, default_issue_type_id}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get("/issuetypescheme", params={"maxResults": min(max_results, 200)})
        except JiraApiError as e:
            raise ToolError(str(e))

        schemes = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "description": s.get("description"),
                "default_issue_type_id": s.get("defaultIssueTypeId"),
            }
            for s in data.get("values", [])
        ]
        return {"total": data.get("total", len(schemes)), "schemes": schemes}

    @mcp.tool(
        name="jira_issuetypes_get_scheme_mappings",
        annotations={"readOnlyHint": True},
    )
    async def get_issue_type_scheme_mappings(
        scheme_id: Annotated[int, "Issue type scheme ID"],
        ctx: Context = None,
    ) -> dict:
        """Get issue types in an issue type scheme.

        Returns: {scheme_id, mappings: [{issue_type_id}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(
                "/issuetypescheme/mapping",
                params={"issueTypeSchemeId": scheme_id, "maxResults": 200},
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        mappings = [
            {
                "issue_type_scheme_id": m.get("issueTypeSchemeId"),
                "issue_type_id": m.get("issueTypeId"),
            }
            for m in data.get("values", [])
        ]
        return {"scheme_id": scheme_id, "mappings": mappings}
