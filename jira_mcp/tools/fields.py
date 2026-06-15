"""Custom field tools: search, contexts, options, manage options."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_fields_search",
        annotations={"readOnlyHint": True},
    )
    async def search_fields(
        query: Annotated[str | None, "Search by field name, e.g. 'Story Points', 'Team'. Leave empty to list all."] = None,
        field_type: Annotated[str | None, "'custom' for custom fields only, 'system' for system fields, or None for all"] = None,
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """Search for Jira fields (custom and system).

        Use this to find field IDs (customfield_XXXXX) for custom fields by name
        before referencing them in other tools.
        Returns: {total, fields: [{id, name, custom, schema_type}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params: dict = {"maxResults": min(max_results, 200)}
        if query:
            params["query"] = query
        if field_type:
            params["type"] = field_type

        try:
            data = await client.get("/field/search", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        fields = [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "custom": str(f.get("id", "")).startswith("customfield_"),
                "schema_type": f.get("schema", {}).get("type") if isinstance(f.get("schema"), dict) else None,
                "type_display": f.get("typeDisplayName"),
            }
            for f in data.get("values", [])
        ]
        return {"total": data.get("total", len(fields)), "fields": fields}

    @mcp.tool(
        name="jira_fields_get_contexts",
        annotations={"readOnlyHint": True},
    )
    async def get_field_contexts(
        field_id: Annotated[str, "Custom field ID, e.g. 'customfield_10001'"],
        ctx: Context = None,
    ) -> dict:
        """Get contexts for a custom field.

        Contexts determine which projects/issue types the field appears in.
        Returns: {field_id, contexts: [{id, name, description, is_global_context, is_any_issue_type}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/field/{field_id}/context")
        except JiraApiError as e:
            raise ToolError(str(e))

        contexts = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "description": c.get("description"),
                "is_global_context": c.get("isGlobalContext", False),
                "is_any_issue_type": c.get("isAnyIssueType", False),
            }
            for c in data.get("values", [])
        ]
        return {"field_id": field_id, "contexts": contexts}

    @mcp.tool(
        name="jira_fields_get_options",
        annotations={"readOnlyHint": True},
    )
    async def get_field_options(
        field_id: Annotated[str, "Custom field ID, e.g. 'customfield_10001'"],
        context_id: Annotated[int, "Context ID from jira_fields_get_contexts"],
        ctx: Context = None,
    ) -> dict:
        """Get options for a custom field in a specific context.

        For select/dropdown fields, returns the available option values.
        Returns: {field_id, context_id, options: [{id, value, disabled}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/field/{field_id}/context/{context_id}/option")
        except JiraApiError as e:
            raise ToolError(str(e))

        options = [
            {
                "id": o.get("id"),
                "value": o.get("value"),
                "disabled": o.get("disabled", False),
            }
            for o in data.get("values", [])
        ]
        return {"field_id": field_id, "context_id": context_id, "options": options}

    @mcp.tool(
        name="jira_fields_manage_options",
        annotations={"readOnlyHint": False},
    )
    async def manage_field_options(
        field_id: Annotated[str, "Custom field ID"],
        context_id: Annotated[int, "Context ID"],
        action: Annotated[str, "'add' to add new options, 'update' to modify existing, 'reorder' to change order"],
        options: Annotated[list[dict], "For 'add': [{'value': 'New Option'}]. For 'update': [{'id': '10001', 'value': 'Updated'}]. For 'reorder': [{'id': '10001', 'position': 'First'}]"],
        ctx: Context = None,
    ) -> dict:
        """Add, update, or reorder options for a custom field.

        Use jira_fields_get_options first to see existing options and their IDs.
        Returns: {success, field_id, context_id, action}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        path = f"/field/{field_id}/context/{context_id}/option"

        try:
            if action == "add":
                await client.post(path, json={"options": options})
            elif action == "update":
                await client.put(path, json={"options": options})
            elif action == "reorder":
                await client.put(f"{path}/move", json={"customFieldOptionIds": [o["id"] for o in options], "position": options[0].get("position", "First")})
            else:
                raise ToolError("action must be 'add', 'update', or 'reorder'")
        except JiraApiError as e:
            raise ToolError(str(e))

        return {"success": True, "field_id": field_id, "context_id": context_id, "action": action}

    @mcp.tool(
        name="jira_fields_create_context",
        annotations={"readOnlyHint": False},
    )
    async def create_field_context(
        field_id: Annotated[str, "Custom field ID, e.g. 'customfield_10001'"],
        name: Annotated[str, "Context name"],
        description: Annotated[str | None, "Context description"] = None,
        project_ids: Annotated[
            list[str] | None,
            "Project IDs to scope the context to. Omit for a global context.",
        ] = None,
        issue_type_ids: Annotated[
            list[str] | None,
            "Issue type IDs to restrict the context to. Omit for all issue types.",
        ] = None,
        ctx: Context = None,
    ) -> dict:
        """Create a new context for a custom field, optionally scoped on creation.

        A context determines which projects/issue types a field appears in, and
        owns its own set of options. projectIds/issueTypeIds are applied in the
        same create call.
        Returns: {success, field_id, context: {id, name, project_ids, issue_type_ids}}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        body: dict = {"name": name}
        if description:
            body["description"] = description
        if project_ids:
            body["projectIds"] = project_ids
        if issue_type_ids:
            body["issueTypeIds"] = issue_type_ids

        try:
            data = await client.post(f"/field/{field_id}/context", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {
            "success": True,
            "field_id": field_id,
            "context": {
                "id": data.get("id"),
                "name": data.get("name"),
                "project_ids": data.get("projectIds", []),
                "issue_type_ids": data.get("issueTypeIds", []),
            },
        }

    @mcp.tool(
        name="jira_fields_update_context",
        annotations={"readOnlyHint": False},
    )
    async def update_field_context(
        field_id: Annotated[str, "Custom field ID"],
        context_id: Annotated[int, "Context ID from jira_fields_get_contexts"],
        name: Annotated[str | None, "New context name"] = None,
        description: Annotated[str | None, "New context description"] = None,
        ctx: Context = None,
    ) -> dict:
        """Rename or re-describe a custom field context.

        Returns: {success, field_id, context_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        body: dict = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if not body:
            raise ToolError("Provide at least one of: name, description")

        try:
            data = await client.put(
                f"/field/{field_id}/context/{context_id}", json=body
            )
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {"success": True, "field_id": field_id, "context_id": context_id}

    @mcp.tool(
        name="jira_fields_delete_context",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_field_context(
        field_id: Annotated[str, "Custom field ID"],
        context_id: Annotated[int, "Context ID to delete"],
        ctx: Context = None,
    ) -> dict:
        """Delete a custom field context permanently.

        Deletes the context and all of its options. Confirm first.
        Returns: {success, field_id, context_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.delete(f"/field/{field_id}/context/{context_id}")
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {"success": True, "field_id": field_id, "context_id": context_id}

    @mcp.tool(
        name="jira_fields_assign_context_projects",
        annotations={"readOnlyHint": False},
    )
    async def assign_context_projects(
        field_id: Annotated[str, "Custom field ID"],
        context_id: Annotated[int, "Context ID"],
        project_ids: Annotated[list[str], "Project IDs to scope the context to"],
        ctx: Context = None,
    ) -> dict:
        """Scope a custom field context to specific projects.

        Note: assigning projects converts a global context into a
        project-scoped one.
        Returns: {success, field_id, context_id, project_ids}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        if not project_ids:
            raise ToolError("project_ids must be a non-empty list")
        try:
            data = await client.put(
                f"/field/{field_id}/context/{context_id}/project",
                json={"projectIds": project_ids},
            )
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {
            "success": True,
            "field_id": field_id,
            "context_id": context_id,
            "project_ids": project_ids,
        }

    @mcp.tool(
        name="jira_fields_remove_context_projects",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def remove_context_projects(
        field_id: Annotated[str, "Custom field ID"],
        context_id: Annotated[int, "Context ID"],
        project_ids: Annotated[list[str], "Project IDs to unscope from the context"],
        ctx: Context = None,
    ) -> dict:
        """Remove projects from a custom field context's scope.

        Returns: {success, field_id, context_id, removed_project_ids}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        if not project_ids:
            raise ToolError("project_ids must be a non-empty list")
        try:
            data = await client.post(
                f"/field/{field_id}/context/{context_id}/project/remove",
                json={"projectIds": project_ids},
            )
        except JiraApiError as e:
            raise ToolError(str(e))
        if isinstance(data, dict) and data.get("dry_run"):
            return data
        return {
            "success": True,
            "field_id": field_id,
            "context_id": context_id,
            "removed_project_ids": project_ids,
        }

    @mcp.tool(
        name="jira_fields_add_context_issuetypes",
        annotations={"readOnlyHint": False},
    )
    async def add_context_issuetypes(
        field_id: Annotated[str, "Custom field ID"],
        context_id: Annotated[int, "Context ID"],
        issue_type_ids: Annotated[list[str], "Issue type IDs to add to the context"],
        ctx: Context = None,
    ) -> dict:
        """Restrict a custom field context to specific issue types.

        Returns: {success, field_id, context_id, issue_type_ids}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        if not issue_type_ids:
            raise ToolError("issue_type_ids must be a non-empty list")
        try:
            data = await client.put(
                f"/field/{field_id}/context/{context_id}/issuetype",
                json={"issueTypeIds": issue_type_ids},
            )
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {
            "success": True,
            "field_id": field_id,
            "context_id": context_id,
            "issue_type_ids": issue_type_ids,
        }

    @mcp.tool(
        name="jira_fields_remove_context_issuetypes",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def remove_context_issuetypes(
        field_id: Annotated[str, "Custom field ID"],
        context_id: Annotated[int, "Context ID"],
        issue_type_ids: Annotated[
            list[str], "Issue type IDs to remove from the context"
        ],
        ctx: Context = None,
    ) -> dict:
        """Remove issue types from a custom field context.

        Returns: {success, field_id, context_id, removed_issue_type_ids}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        if not issue_type_ids:
            raise ToolError("issue_type_ids must be a non-empty list")
        try:
            data = await client.post(
                f"/field/{field_id}/context/{context_id}/issuetype/remove",
                json={"issueTypeIds": issue_type_ids},
            )
        except JiraApiError as e:
            raise ToolError(str(e))
        if isinstance(data, dict) and data.get("dry_run"):
            return data
        return {
            "success": True,
            "field_id": field_id,
            "context_id": context_id,
            "removed_issue_type_ids": issue_type_ids,
        }

    @mcp.tool(
        name="jira_fields_get_project_mapping",
        annotations={"readOnlyHint": True},
    )
    async def get_context_project_mapping(
        field_id: Annotated[str, "Custom field ID"],
        context_ids: Annotated[
            list[int] | None,
            "Context IDs to inspect. Omit to inspect all contexts of the field.",
        ] = None,
        ctx: Context = None,
    ) -> dict:
        """Show which projects each context of a custom field is scoped to.

        Use this to audit field scope, e.g. confirm a custom field's context
        is correctly scoped to the intended projects.
        Returns: {field_id, mappings: [{context_id, project_id, is_global_context}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        if context_ids is None:
            try:
                ctx_data = await client.get(f"/field/{field_id}/context")
            except JiraApiError as e:
                raise ToolError(str(e))
            context_ids = [
                int(c["id"]) for c in ctx_data.get("values", []) if c.get("id")
            ]
        if not context_ids:
            return {"field_id": field_id, "mappings": []}

        params = {"contextId": context_ids}
        try:
            data = await client.get(
                f"/field/{field_id}/context/projectmapping", params=params
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        mappings = [
            {
                "context_id": m.get("contextId"),
                "project_id": m.get("projectId"),
                "is_global_context": m.get("isGlobalContext", False),
            }
            for m in data.get("values", [])
        ]
        return {"field_id": field_id, "mappings": mappings}
