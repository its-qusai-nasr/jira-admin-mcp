"""Filter tools: search, create, update, delete, and manage sharing of JQL filters."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def _build_share_body(
    share_type: str,
    group_name: str | None,
    project_id: str | None,
    role_id: str | None,
    account_id: str | None,
) -> dict:
    """Assemble a SharePermissionInputBean body for POST /filter/{id}/permission.

    share_type: 'group' | 'project' | 'projectRole' | 'user' | 'authenticated' | 'global'
    """
    st = share_type.lower()
    if st == "group":
        if not group_name:
            raise ToolError("share_type 'group' requires group_name")
        return {"type": "group", "groupname": group_name}
    if st == "project":
        if not project_id:
            raise ToolError("share_type 'project' requires project_id")
        return {"type": "project", "projectId": project_id}
    if st in ("projectrole", "project_role"):
        if not (project_id and role_id):
            raise ToolError("share_type 'projectRole' requires project_id and role_id")
        return {"type": "projectRole", "projectId": project_id, "projectRoleId": role_id}
    if st == "user":
        if not account_id:
            raise ToolError("share_type 'user' requires account_id")
        return {"type": "user", "accountId": account_id}
    if st in ("authenticated", "loggedin"):
        return {"type": "loggedin"}
    if st == "global":
        return {"type": "global"}
    raise ToolError(
        "share_type must be one of: group, project, projectRole, user, authenticated, global"
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_filters_search",
        annotations={"readOnlyHint": True},
    )
    async def search_filters(
        filter_name: Annotated[str | None, "Filter by name substring"] = None,
        owner_account_id: Annotated[str | None, "Filter by owner's account ID"] = None,
        max_results: Annotated[int, "Max results. Default: 25"] = 25,
        ctx: Context = None,
    ) -> dict:
        """Search for saved JQL filters.

        Returns: {total, filters: [{id, name, jql, owner, favourite_count}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params: dict = {"maxResults": min(max_results, 100)}
        if filter_name:
            params["filterName"] = filter_name
        if owner_account_id:
            params["accountId"] = owner_account_id

        try:
            data = await client.get("/filter/search", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        filters = [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "jql": f.get("jql"),
                "owner": f.get("owner", {}).get("displayName"),
                "favourite_count": f.get("favouritedCount"),
            }
            for f in data.get("values", [])
        ]
        return {"total": data.get("total", len(filters)), "filters": filters}

    @mcp.tool(
        name="jira_filters_create",
        annotations={"readOnlyHint": False},
    )
    async def create_filter(
        name: Annotated[str, "Filter name"],
        jql: Annotated[str, "JQL query string for the filter"],
        description: Annotated[str | None, "Filter description"] = None,
        favourite: Annotated[bool, "Add to favourites. Default: False"] = False,
        ctx: Context = None,
    ) -> dict:
        """Create a new saved JQL filter.

        The filter is owned by the authenticated user.
        Share permissions can be managed separately via the Jira UI.
        Returns: {id, name, jql}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        body: dict = {"name": name, "jql": jql, "favourite": favourite}
        if description:
            body["description"] = description

        try:
            data = await client.post("/filter", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))

        return {"id": data.get("id"), "name": data.get("name"), "jql": data.get("jql")}

    @mcp.tool(
        name="jira_filters_get",
        annotations={"readOnlyHint": True},
    )
    async def get_filter(
        filter_id: Annotated[str, "Filter ID, e.g. '10000'"],
        ctx: Context = None,
    ) -> dict:
        """Get a single saved JQL filter by ID.

        Returns: {id, name, jql, description, owner, owner_account_id, favourite_count, share_permissions}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/filter/{filter_id}")
        except JiraApiError as e:
            raise ToolError(str(e))

        owner = data.get("owner") or {}
        shares = [
            {
                "id": p.get("id"),
                "type": p.get("type"),
                "group": (p.get("group") or {}).get("name"),
                "project": (p.get("project") or {}).get("key"),
                "role": (p.get("role") or {}).get("name"),
            }
            for p in data.get("sharePermissions", [])
        ]
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "jql": data.get("jql"),
            "description": data.get("description"),
            "owner": owner.get("displayName"),
            "owner_account_id": owner.get("accountId"),
            "favourite_count": data.get("favouritedCount"),
            "share_permissions": shares,
        }

    @mcp.tool(
        name="jira_filters_update",
        annotations={"readOnlyHint": False},
    )
    async def update_filter(
        filter_id: Annotated[str, "Filter ID"],
        name: Annotated[str | None, "New filter name"] = None,
        jql: Annotated[str | None, "New JQL query string"] = None,
        description: Annotated[str | None, "New description"] = None,
        ctx: Context = None,
    ) -> dict:
        """Update an existing saved JQL filter's name, JQL, or description.

        Jira requires name + jql on every update, so unspecified fields are
        pre-fetched and re-sent unchanged.
        Returns: {success, id, name, jql}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            current = await client.get(f"/filter/{filter_id}")
        except JiraApiError as e:
            raise ToolError(str(e))

        body: dict = {
            "name": name if name is not None else current.get("name"),
            "jql": jql if jql is not None else current.get("jql"),
        }
        new_desc = description if description is not None else current.get("description")
        if new_desc is not None:
            body["description"] = new_desc

        try:
            data = await client.put(f"/filter/{filter_id}", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))

        if data.get("dry_run"):
            return data
        return {
            "success": True,
            "id": data.get("id"),
            "name": data.get("name"),
            "jql": data.get("jql"),
        }

    @mcp.tool(
        name="jira_filters_delete",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_filter(
        filter_id: Annotated[str, "Filter ID to delete"],
        ctx: Context = None,
    ) -> dict:
        """Delete a saved JQL filter permanently.

        Boards and dashboards backed by this filter will break. Confirm first.
        Returns: {success, filter_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.delete(f"/filter/{filter_id}")
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {"success": True, "filter_id": filter_id}

    @mcp.tool(
        name="jira_filters_change_owner",
        annotations={"readOnlyHint": False},
    )
    async def change_filter_owner(
        filter_id: Annotated[str, "Filter ID"],
        new_owner_account_id: Annotated[str, "Account ID of the new owner"],
        ctx: Context = None,
    ) -> dict:
        """Change the owner of a saved JQL filter.

        Returns: {success, filter_id, new_owner_account_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.put(
                f"/filter/{filter_id}/owner",
                json={"accountId": new_owner_account_id},
            )
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {
            "success": True,
            "filter_id": filter_id,
            "new_owner_account_id": new_owner_account_id,
        }

    @mcp.tool(
        name="jira_filters_get_shares",
        annotations={"readOnlyHint": True},
    )
    async def get_filter_shares(
        filter_id: Annotated[str, "Filter ID"],
        ctx: Context = None,
    ) -> dict:
        """List the share permissions of a saved JQL filter.

        Returns: {filter_id, total, shares: [{id, type, group, project, role}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/filter/{filter_id}/permission")
        except JiraApiError as e:
            raise ToolError(str(e))

        shares = [
            {
                "id": p.get("id"),
                "type": p.get("type"),
                "group": (p.get("group") or {}).get("name"),
                "project": (p.get("project") or {}).get("key"),
                "role": (p.get("role") or {}).get("name"),
            }
            for p in (data if isinstance(data, list) else [])
        ]
        return {"filter_id": filter_id, "total": len(shares), "shares": shares}

    @mcp.tool(
        name="jira_filters_add_share",
        annotations={"readOnlyHint": False},
    )
    async def add_filter_share(
        filter_id: Annotated[str, "Filter ID"],
        share_type: Annotated[
            str,
            "'group' | 'project' | 'projectRole' | 'user' | 'authenticated' | 'global'",
        ],
        group_name: Annotated[str | None, "Group name (for share_type 'group')"] = None,
        project_id: Annotated[
            str | None, "Project ID (for 'project' / 'projectRole')"
        ] = None,
        role_id: Annotated[str | None, "Project role ID (for 'projectRole')"] = None,
        account_id: Annotated[str | None, "User account ID (for 'user')"] = None,
        ctx: Context = None,
    ) -> dict:
        """Add a share permission to a saved JQL filter.

        Requires that you OWN the filter. To share a filter you do not own,
        use jira_filters_force_add_share instead.
        Returns: {success, filter_id, share}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        body = _build_share_body(
            share_type, group_name, project_id, role_id, account_id
        )
        try:
            data = await client.post(f"/filter/{filter_id}/permission", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))
        if isinstance(data, dict) and data.get("dry_run"):
            return data
        created = data[0] if isinstance(data, list) and data else data
        return {
            "success": True,
            "filter_id": filter_id,
            "share": {
                "id": created.get("id") if isinstance(created, dict) else None,
                "type": body["type"],
            },
        }

    @mcp.tool(
        name="jira_filters_remove_share",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def remove_filter_share(
        filter_id: Annotated[str, "Filter ID"],
        permission_id: Annotated[str, "Share permission ID from jira_filters_get_shares"],
        ctx: Context = None,
    ) -> dict:
        """Remove a share permission from a saved JQL filter.

        Returns: {success, filter_id, permission_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.delete(
                f"/filter/{filter_id}/permission/{permission_id}"
            )
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {
            "success": True,
            "filter_id": filter_id,
            "permission_id": permission_id,
        }

    @mcp.tool(
        name="jira_filters_force_add_share",
        annotations={"readOnlyHint": False},
    )
    async def force_add_filter_share(
        filter_id: Annotated[str, "Filter ID (may be owned by someone else)"],
        share_type: Annotated[
            str,
            "'group' | 'project' | 'projectRole' | 'user' | 'authenticated' | 'global'",
        ],
        group_name: Annotated[str | None, "Group name (for share_type 'group')"] = None,
        project_id: Annotated[
            str | None, "Project ID (for 'project' / 'projectRole')"
        ] = None,
        role_id: Annotated[str | None, "Project role ID (for 'projectRole')"] = None,
        account_id: Annotated[str | None, "User account ID (for 'user')"] = None,
        ctx: Context = None,
    ) -> dict:
        """Add a share to a filter you do NOT own, via the admin owner-swap workaround.

        overrideSharePermissions only works on READs (JRACLOUD-60899), so to
        WRITE a share onto another user's filter this does:
          1. take ownership of the filter,
          2. add the share,
          3. restore the original owner.
        Ownership is always restored, even on failure (best-effort rollback).
        Returns: {success, filter_id, share, owner_restored, original_owner_account_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        body = _build_share_body(
            share_type, group_name, project_id, role_id, account_id
        )

        # Resolve self + original owner up front.
        try:
            me = await client.get("/myself")
            current = await client.get(f"/filter/{filter_id}")
        except JiraApiError as e:
            raise ToolError(str(e))

        self_account_id = me.get("accountId")
        original_owner = (current.get("owner") or {}).get("accountId")
        if not self_account_id:
            raise ToolError("Could not resolve own account ID from /myself")

        already_owned = original_owner == self_account_id

        # Step 1: take ownership (skip if already ours).
        if not already_owned:
            try:
                res = await client.put(
                    f"/filter/{filter_id}/owner",
                    json={"accountId": self_account_id},
                )
            except JiraApiError as e:
                raise ToolError(f"Failed to take ownership of filter: {e}")
            if isinstance(res, dict) and res.get("dry_run"):
                return {
                    "dry_run": True,
                    "would_call": "owner-swap + add share + restore owner",
                    "filter_id": filter_id,
                    "share_body": body,
                    "original_owner_account_id": original_owner,
                }

        # Step 2: add the share. Step 3: restore owner no matter what.
        share_created = None
        share_error = None
        try:
            data = await client.post(f"/filter/{filter_id}/permission", json=body)
            share_created = data[0] if isinstance(data, list) and data else data
        except JiraApiError as e:
            share_error = str(e)

        owner_restored = True
        restore_error = None
        if not already_owned:
            try:
                await client.put(
                    f"/filter/{filter_id}/owner",
                    json={"accountId": original_owner},
                )
            except JiraApiError as e:
                owner_restored = False
                restore_error = str(e)

        if share_error is not None:
            raise ToolError(
                f"Share not added: {share_error}. "
                f"Owner restored: {owner_restored}."
                + (f" Restore error: {restore_error}" if restore_error else "")
            )
        if not owner_restored:
            raise ToolError(
                f"Share WAS added but owner restore FAILED: {restore_error}. "
                f"Filter {filter_id} is still owned by you ({self_account_id}). "
                f"Run jira_filters_change_owner to restore {original_owner}."
            )

        return {
            "success": True,
            "filter_id": filter_id,
            "share": {
                "id": share_created.get("id")
                if isinstance(share_created, dict)
                else None,
                "type": body["type"],
            },
            "owner_restored": True,
            "original_owner_account_id": original_owner,
        }
