"""Screen tools: list, get fields, get schemes."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_screens_list",
        annotations={"readOnlyHint": True},
    )
    async def list_screens(
        query: Annotated[str | None, "Filter by screen name substring"] = None,
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """List Jira screens, optionally filtered by name.

        Returns: {total, screens: [{id, name, description}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params: dict = {"maxResults": min(max_results, 200)}
        if query:
            params["queryString"] = query
        try:
            data = await client.get("/screens", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        screens = [
            {"id": s.get("id"), "name": s.get("name"), "description": s.get("description")}
            for s in data.get("values", [])
        ]
        return {"total": data.get("total", len(screens)), "screens": screens}

    @mcp.tool(
        name="jira_screens_get_fields",
        annotations={"readOnlyHint": True},
    )
    async def get_screen_fields(
        screen_id: Annotated[int, "Screen ID from jira_screens_list"],
        tab_id: Annotated[int | None, "Specific tab ID. Omit to get all tabs with fields."] = None,
        ctx: Context = None,
    ) -> dict:
        """Get fields on a screen, optionally for a specific tab.

        Returns: {screen_id, tabs: [{id, name, fields: [{id, name}]}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]

        try:
            tabs_data = await client.get(f"/screens/{screen_id}/tabs")
        except JiraApiError as e:
            raise ToolError(str(e))

        tabs = []
        for tab in tabs_data if isinstance(tabs_data, list) else tabs_data.get("values", []):
            tid = tab.get("id")
            if tab_id and tid != tab_id:
                continue
            try:
                fields_data = await client.get(f"/screens/{screen_id}/tabs/{tid}/fields")
            except JiraApiError:
                fields_data = []

            fields_list = fields_data if isinstance(fields_data, list) else fields_data.get("values", [])
            tabs.append({
                "id": tid,
                "name": tab.get("name"),
                "fields": [{"id": f.get("id"), "name": f.get("name")} for f in fields_list],
            })

        return {"screen_id": screen_id, "tabs": tabs}

    @mcp.tool(
        name="jira_screens_get_schemes",
        annotations={"readOnlyHint": True},
    )
    async def get_screen_schemes(
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """List screen schemes.

        Returns: {total, schemes: [{id, name, description}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get("/screenscheme", params={"maxResults": min(max_results, 200)})
        except JiraApiError as e:
            raise ToolError(str(e))

        schemes = [
            {"id": s.get("id"), "name": s.get("name"), "description": s.get("description")}
            for s in data.get("values", [])
        ]
        return {"total": data.get("total", len(schemes)), "schemes": schemes}
