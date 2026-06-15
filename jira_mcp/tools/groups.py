"""Group tools: list, members, add/remove users, create/delete groups."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError
from jira_mcp.helpers import format_group, format_user


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_groups_list",
        annotations={"readOnlyHint": True},
    )
    async def list_groups(
        query: Annotated[str | None, "Filter groups by name substring. Leave empty to list all."] = None,
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """List Jira groups, optionally filtered by name.

        Common groups: jira-administrators, jira-developers, jira-project-leads.
        Returns: {total, groups: [{name, group_id, member_count}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params: dict = {"maxResults": min(max_results, 200)}
        if query:
            params["groupName"] = query
        try:
            data = await client.get("/group/bulk", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        groups = [format_group(g) for g in data.get("values", [])]
        return {"total": data.get("total", len(groups)), "groups": groups}

    @mcp.tool(
        name="jira_groups_get_members",
        annotations={"readOnlyHint": True},
    )
    async def get_group_members(
        group_name: Annotated[str, "Exact group name, e.g. 'jira-developers', 'jira-administrators'"],
        max_results: Annotated[int, "Max members to return. Default: 50"] = 50,
        start_at: Annotated[int, "Pagination offset. Default: 0"] = 0,
        ctx: Context = None,
    ) -> dict:
        """Get members of a Jira group.

        Returns: {group_name, total, members: [{account_id, display_name, email, active}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(
                "/group/member",
                params={
                    "groupname": group_name,
                    "startAt": start_at,
                    "maxResults": min(max_results, 200),
                },
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        members = [format_user(m) for m in data.get("values", [])]
        return {
            "group_name": group_name,
            "total": data.get("total", len(members)),
            "members": members,
        }

    @mcp.tool(
        name="jira_groups_add_user",
        annotations={"readOnlyHint": False},
    )
    async def add_user_to_group(
        group_name: Annotated[str, "Exact group name, e.g. 'jira-developers', 'jira-administrators'"],
        account_id: Annotated[str, "User's account ID from jira_users_search"],
        ctx: Context = None,
    ) -> dict:
        """Add a user to a Jira group.

        Always verify user identity first with jira_users_search.
        Returns: {success, group_name, account_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            await client.post(
                "/group/user",
                json={"accountId": account_id},
                params={"groupname": group_name},
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        return {"success": True, "group_name": group_name, "account_id": account_id}

    @mcp.tool(
        name="jira_groups_remove_user",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def remove_user_from_group(
        group_name: Annotated[str, "Exact group name"],
        account_id: Annotated[str, "User's account ID"],
        ctx: Context = None,
    ) -> dict:
        """Remove a user from a Jira group.

        Verify user identity first. Removing from permission-granting groups may lock the user out.
        Returns: {success, group_name, account_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            await client.delete(
                "/group/user",
                params={"groupname": group_name, "accountId": account_id},
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        return {"success": True, "group_name": group_name, "account_id": account_id}

    @mcp.tool(
        name="jira_groups_create",
        annotations={"readOnlyHint": False},
    )
    async def create_group(
        group_name: Annotated[str, "Name for the new group. Convention: lowercase with hyphens, e.g. 'jira-developers', 'new-team'"],
        ctx: Context = None,
    ) -> dict:
        """Create a new Jira group.

        Group names should follow convention: lowercase with hyphens.
        Returns: {name, group_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.post("/group", json={"name": group_name})
        except JiraApiError as e:
            raise ToolError(str(e))
        return {"name": data.get("name"), "group_id": data.get("groupId")}

    @mcp.tool(
        name="jira_groups_delete",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_group(
        group_name: Annotated[str, "Exact name of the group to delete"],
        ctx: Context = None,
    ) -> dict:
        """Delete a Jira group permanently.

        This removes the group and all its membership associations.
        Users are NOT deleted: only the group itself.
        Returns: {success, group_name}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            await client.delete("/group", params={"groupname": group_name})
        except JiraApiError as e:
            raise ToolError(str(e))
        return {"success": True, "group_name": group_name}
