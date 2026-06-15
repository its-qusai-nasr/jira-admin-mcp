"""Project tools: list, get, statuses, roles, update_role, versions, features, notifications, categories."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError
from jira_mcp.helpers import format_project


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_projects_list",
        annotations={"readOnlyHint": True},
    )
    async def list_projects(
        query: Annotated[str | None, "Filter by project name or key substring"] = None,
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """List Jira projects, optionally filtered by name or key.

        Returns: {total, projects: [{id, key, name, project_type, lead}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params: dict = {"maxResults": min(max_results, 200)}
        if query:
            params["query"] = query
        try:
            data = await client.get("/project/search", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        projects = [format_project(p) for p in data.get("values", [])]
        return {"total": data.get("total", len(projects)), "projects": projects}

    @mcp.tool(
        name="jira_projects_get",
        annotations={"readOnlyHint": True},
    )
    async def get_project(
        project_key: Annotated[str, "Project key, e.g. 'PROJ'"],
        ctx: Context = None,
    ) -> dict:
        """Get full project details including lead, issue types, and description.

        Returns: {id, key, name, project_type, lead, description, issue_types, category}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(
                f"/project/{project_key}",
                params={"expand": "description,lead,issueTypes"},
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        result = format_project(data)
        result["description"] = data.get("description")
        result["issue_types"] = [
            {"id": t.get("id"), "name": t.get("name"), "subtask": t.get("subtask", False)}
            for t in data.get("issueTypes", [])
        ]
        result["category"] = data.get("projectCategory", {}).get("name") if data.get("projectCategory") else None
        return result

    @mcp.tool(
        name="jira_projects_get_statuses",
        annotations={"readOnlyHint": True},
    )
    async def get_project_statuses(
        project_key: Annotated[str, "Project key"],
        ctx: Context = None,
    ) -> dict:
        """Get all statuses available in a project, grouped by issue type.

        Returns: {project_key, issue_types: [{name, statuses: [{id, name, category}]}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/project/{project_key}/statuses")
        except JiraApiError as e:
            raise ToolError(str(e))

        issue_types = [
            {
                "name": it.get("name"),
                "statuses": [
                    {
                        "id": s.get("id"),
                        "name": s.get("name"),
                        "category": s.get("statusCategory", {}).get("name"),
                    }
                    for s in it.get("statuses", [])
                ],
            }
            for it in data
        ]
        return {"project_key": project_key, "issue_types": issue_types}

    @mcp.tool(
        name="jira_projects_get_roles",
        annotations={"readOnlyHint": True},
    )
    async def get_project_roles(
        project_key: Annotated[str, "Project key"],
        ctx: Context = None,
    ) -> dict:
        """Get project roles and their actors (users/groups).

        Returns: {project_key, roles: [{name, id, actors: [{display_name, type, name}]}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            roles_data = await client.get(f"/project/{project_key}/roledetails")
        except JiraApiError as e:
            raise ToolError(str(e))

        roles = []
        for role in roles_data:
            role_id = role.get("id")
            try:
                detail = await client.get(f"/project/{project_key}/role/{role_id}")
            except JiraApiError:
                detail = {}

            actors = [
                {
                    "display_name": a.get("displayName"),
                    "type": a.get("type"),
                    "name": a.get("name"),
                    "account_id": a.get("actorUser", {}).get("accountId") if a.get("type") == "atlassian-user-role-actor" else None,
                }
                for a in detail.get("actors", [])
            ]
            roles.append({
                "name": role.get("name"),
                "id": role_id,
                "actors": actors,
            })

        return {"project_key": project_key, "roles": roles}

    @mcp.tool(
        name="jira_projects_update_role",
        annotations={"readOnlyHint": False},
    )
    async def update_project_role(
        project_key: Annotated[str, "Project key"],
        role_id: Annotated[int, "Role ID from jira_projects_get_roles"],
        action: Annotated[str, "'add' or 'remove'"],
        actor_type: Annotated[str, "'user' or 'group'"],
        actor_value: Annotated[str, "Account ID for users, group name for groups"],
        ctx: Context = None,
    ) -> dict:
        """Add or remove an actor (user or group) from a project role.

        Use jira_projects_get_roles first to find the role_id.
        Returns: {success, project_key, role_id, action, actor_value}
        """
        client: JiraClient = ctx.lifespan_context["client"]

        if action == "add":
            body = {}
            if actor_type == "user":
                body["user"] = [actor_value]
            else:
                body["group"] = [actor_value]
            try:
                await client.post(f"/project/{project_key}/role/{role_id}", json=body)
            except JiraApiError as e:
                raise ToolError(str(e))
        elif action == "remove":
            param_key = "user" if actor_type == "user" else "group"
            try:
                await client.delete(
                    f"/project/{project_key}/role/{role_id}",
                    params={param_key: actor_value},
                )
            except JiraApiError as e:
                raise ToolError(str(e))
        else:
            raise ToolError("action must be 'add' or 'remove'")

        return {
            "success": True,
            "project_key": project_key,
            "role_id": role_id,
            "action": action,
            "actor_value": actor_value,
        }

    @mcp.tool(
        name="jira_projects_get_versions",
        annotations={"readOnlyHint": True},
    )
    async def get_project_versions(
        project_key: Annotated[str, "Project key"],
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """Get versions (releases) for a project.

        Returns: {project_key, total, versions: [{id, name, description, released, release_date, archived}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(
                f"/project/{project_key}/version",
                params={"maxResults": min(max_results, 200)},
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        versions = [
            {
                "id": v.get("id"),
                "name": v.get("name"),
                "description": v.get("description"),
                "released": v.get("released", False),
                "release_date": v.get("releaseDate"),
                "archived": v.get("archived", False),
            }
            for v in data.get("values", [])
        ]
        return {"project_key": project_key, "total": data.get("total", len(versions)), "versions": versions}

    @mcp.tool(
        name="jira_projects_create_version",
        annotations={"readOnlyHint": False},
    )
    async def create_project_version(
        project_key: Annotated[str, "Project key"],
        name: Annotated[str, "Version name, e.g. 'v1.0', '2026-Q1'"],
        description: Annotated[str | None, "Version description"] = None,
        release_date: Annotated[str | None, "Release date in YYYY-MM-DD format"] = None,
        released: Annotated[bool, "Mark as released. Default: False"] = False,
        ctx: Context = None,
    ) -> dict:
        """Create a new version (release) in a project.

        Returns: {id, name, project_key}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        # Need project ID
        try:
            proj = await client.get(f"/project/{project_key}")
        except JiraApiError as e:
            raise ToolError(str(e))

        body: dict = {
            "name": name,
            "projectId": int(proj.get("id")),
            "released": released,
        }
        if description:
            body["description"] = description
        if release_date:
            body["releaseDate"] = release_date

        try:
            data = await client.post("/version", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))

        return {"id": data.get("id"), "name": data.get("name"), "project_key": project_key}

    @mcp.tool(
        name="jira_projects_get_features",
        annotations={"readOnlyHint": True},
    )
    async def get_project_features(
        project_key: Annotated[str, "Project key"],
        ctx: Context = None,
    ) -> dict:
        """Get features and their states for a project.

        Shows which project features are enabled/disabled (e.g. backlog, board, calendar, security).
        Returns: {project_key, features: [{feature, state, toggle_locked}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/project/{project_key}/features")
        except JiraApiError as e:
            raise ToolError(str(e))

        features = [
            {
                "feature": f.get("feature"),
                "state": f.get("state"),
                "toggle_locked": f.get("toggleLocked", False),
            }
            for f in data.get("features", [])
        ]
        return {"project_key": project_key, "features": features}

    @mcp.tool(
        name="jira_projects_get_notification_scheme",
        annotations={"readOnlyHint": True},
    )
    async def get_project_notification_scheme(
        project_key: Annotated[str, "Project key"],
        ctx: Context = None,
    ) -> dict:
        """Get the notification scheme assigned to a project.

        Returns: {project_key, scheme_id, scheme_name, description}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/project/{project_key}/notificationscheme")
        except JiraApiError as e:
            raise ToolError(str(e))

        return {
            "project_key": project_key,
            "scheme_id": data.get("id"),
            "scheme_name": data.get("name"),
            "description": data.get("description"),
        }

    @mcp.tool(
        name="jira_projects_get_categories",
        annotations={"readOnlyHint": True},
    )
    async def get_project_categories(
        ctx: Context = None,
    ) -> dict:
        """List all project categories.

        Categories group projects for organization (e.g. 'Engineering', 'Marketing').
        Returns: {total, categories: [{id, name, description}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get("/projectCategory")
        except JiraApiError as e:
            raise ToolError(str(e))

        categories = [
            {"id": c.get("id"), "name": c.get("name"), "description": c.get("description")}
            for c in (data if isinstance(data, list) else [])
        ]
        return {"total": len(categories), "categories": categories}
