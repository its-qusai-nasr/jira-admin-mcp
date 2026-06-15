"""Permission scheme tools: list, inspect, grant, assign."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_permissions_list_schemes",
        annotations={"readOnlyHint": True},
    )
    async def list_permission_schemes(
        ctx: Context = None,
    ) -> dict:
        """List all permission schemes in the Jira instance.

        Use jira_permissions_get_scheme to see grants in a specific scheme.
        Returns: {total, schemes: [{id, name, description}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get("/permissionscheme")
        except JiraApiError as e:
            raise ToolError(str(e))

        schemes = [
            {"id": s.get("id"), "name": s.get("name"), "description": s.get("description")}
            for s in data.get("permissionSchemes", [])
        ]
        return {"total": len(schemes), "schemes": schemes}

    @mcp.tool(
        name="jira_permissions_get_scheme",
        annotations={"readOnlyHint": True},
    )
    async def get_permission_scheme(
        scheme_id: Annotated[int, "Permission scheme ID from jira_permissions_list_schemes"],
        ctx: Context = None,
    ) -> dict:
        """Get a permission scheme with all its permission grants.

        Common permission keys: BROWSE_PROJECTS, EDIT_ISSUES, CREATE_ISSUES, ASSIGN_ISSUES,
        TRANSITION_ISSUES, ADD_COMMENTS, ADMINISTER_PROJECTS, DELETE_ISSUES.
        Returns: {id, name, description, permissions: [{permission, holder_type, holder_value}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/permissionscheme/{scheme_id}", params={"expand": "permissions"})
        except JiraApiError as e:
            raise ToolError(str(e))

        perms = [
            {
                "id": p.get("id"),
                "permission": p.get("permission"),
                "holder_type": p.get("holder", {}).get("type"),
                "holder_value": p.get("holder", {}).get("parameter") or p.get("holder", {}).get("value"),
            }
            for p in data.get("permissions", [])
        ]
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "description": data.get("description"),
            "permissions": perms,
        }

    @mcp.tool(
        name="jira_permissions_add_grant",
        annotations={"readOnlyHint": False},
    )
    async def add_permission_grant(
        scheme_id: Annotated[int, "Permission scheme ID"],
        permission: Annotated[str, "Permission key, e.g. 'BROWSE_PROJECTS', 'EDIT_ISSUES', 'ADMINISTER_PROJECTS'"],
        holder_type: Annotated[str, "'group', 'projectRole', 'reporter', 'assignee', 'projectLead', 'applicationRole', or 'anyone'"],
        holder_parameter: Annotated[str | None, "Group name for 'group', role name for 'projectRole'. Not needed for reporter/assignee/projectLead."] = None,
        ctx: Context = None,
    ) -> dict:
        """Add a permission grant to a permission scheme.

        Verify the scheme is not shared with other projects before modifying.
        Returns: {success, scheme_id, permission, holder_type}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        body: dict = {
            "holder": {"type": holder_type},
            "permission": permission,
        }
        if holder_parameter:
            body["holder"]["parameter"] = holder_parameter

        try:
            await client.post(f"/permissionscheme/{scheme_id}/permission", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))

        return {
            "success": True,
            "scheme_id": scheme_id,
            "permission": permission,
            "holder_type": holder_type,
            "holder_parameter": holder_parameter,
        }

    @mcp.tool(
        name="jira_permissions_assign_scheme",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def assign_permission_scheme(
        project_key: Annotated[str, "Project key to assign the scheme to"],
        scheme_id: Annotated[int, "Permission scheme ID to assign"],
        ctx: Context = None,
    ) -> dict:
        """Assign a permission scheme to a project. Replaces the current scheme.

        Verify the new scheme has all required permissions before assigning.
        Returns: {success, project_key, scheme_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            await client.put(f"/project/{project_key}/permissionscheme", json={"id": scheme_id})
        except JiraApiError as e:
            raise ToolError(str(e))

        return {"success": True, "project_key": project_key, "scheme_id": scheme_id}
