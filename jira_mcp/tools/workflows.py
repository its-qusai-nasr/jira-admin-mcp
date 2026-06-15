"""Workflow tools: search, schemes, scheme mappings."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_workflows_search",
        annotations={"readOnlyHint": True},
    )
    async def search_workflows(
        query: Annotated[str | None, "Search by workflow name substring"] = None,
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """Search for workflows in the Jira instance.

        Returns: {total, workflows: [{id, name, description, statuses}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params: dict = {"maxResults": min(max_results, 200)}
        if query:
            params["queryString"] = query
        try:
            data = await client.get("/workflow/search", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        workflows = []
        for w in data.get("values", []):
            statuses = [
                {"name": s.get("name"), "category": s.get("statusCategory")}
                for s in w.get("statuses", [])
            ]
            workflows.append({
                "id": w.get("id", {}).get("name") if isinstance(w.get("id"), dict) else w.get("id"),
                "name": w.get("id", {}).get("name") if isinstance(w.get("id"), dict) else w.get("name"),
                "description": w.get("description"),
                "statuses": statuses,
            })

        return {"total": data.get("total", len(workflows)), "workflows": workflows}

    @mcp.tool(
        name="jira_workflows_get_schemes",
        annotations={"readOnlyHint": True},
    )
    async def get_workflow_schemes(
        max_results: Annotated[int, "Max results. Default: 50"] = 50,
        ctx: Context = None,
    ) -> dict:
        """List workflow schemes.

        Returns: {total, schemes: [{id, name, description, default_workflow}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get("/workflowscheme", params={"maxResults": min(max_results, 200)})
        except JiraApiError as e:
            raise ToolError(str(e))

        schemes = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "description": s.get("description"),
                "default_workflow": s.get("defaultWorkflow"),
            }
            for s in data.get("values", [])
        ]
        return {"total": data.get("total", len(schemes)), "schemes": schemes}

    @mcp.tool(
        name="jira_workflows_get_scheme_mappings",
        annotations={"readOnlyHint": True},
    )
    async def get_workflow_scheme_mappings(
        scheme_id: Annotated[int, "Workflow scheme ID"],
        ctx: Context = None,
    ) -> dict:
        """Get issue type to workflow mappings in a workflow scheme.

        Shows which workflow is used for each issue type.
        Returns: {scheme_id, default_workflow, mappings: [{issue_type, workflow}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            scheme_data = await client.get(f"/workflowscheme/{scheme_id}")
        except JiraApiError as e:
            raise ToolError(str(e))

        mappings = []
        issue_type_mappings = scheme_data.get("issueTypeMappings", {})
        for issue_type_id, workflow_name in issue_type_mappings.items():
            mappings.append({
                "issue_type_id": issue_type_id,
                "workflow": workflow_name,
            })

        return {
            "scheme_id": scheme_id,
            "scheme_name": scheme_data.get("name"),
            "default_workflow": scheme_data.get("defaultWorkflow"),
            "mappings": mappings,
        }

    @mcp.tool(
        name="jira_workflows_get_scheme_project_usages",
        annotations={"readOnlyHint": True},
    )
    async def get_scheme_project_usages(
        scheme_id: Annotated[int, "Workflow scheme ID"],
        ctx: Context = None,
    ) -> dict:
        """List the projects that use a given workflow scheme.

        SAFETY: run this before editing a scheme. If more than one project uses
        it, edits affect all of them: create a dedicated scheme or work on a
        draft instead.
        Returns: {scheme_id, project_count, project_ids, shared}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/workflowscheme/{scheme_id}/projectUsages")
        except JiraApiError as e:
            raise ToolError(str(e))

        project_ids = [
            p.get("id") for p in (data.get("projects") or {}).get("values", [])
        ]
        return {
            "scheme_id": scheme_id,
            "project_count": len(project_ids),
            "project_ids": project_ids,
            "shared": len(project_ids) > 1,
        }

    @mcp.tool(
        name="jira_workflows_set_scheme_issuetype",
        annotations={"readOnlyHint": False},
    )
    async def set_scheme_issuetype(
        scheme_id: Annotated[int, "Workflow scheme ID"],
        issue_type_id: Annotated[str, "Issue type ID, e.g. '10001'"],
        workflow_name: Annotated[str, "Name of the workflow to assign"],
        edit_draft: Annotated[
            bool,
            "True edits the scheme's existing DRAFT directly. False (default) "
            "edits the live scheme; in-use schemes auto-create a draft.",
        ] = False,
        ctx: Context = None,
    ) -> dict:
        """Map an issue type to a workflow within a workflow scheme.

        For in-use (shared) schemes the live edit auto-creates a draft that
        must then be published with jira_workflows_publish_scheme_draft.
        Returns: {success, scheme_id, issue_type_id, workflow, edited_draft}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        if edit_draft:
            path = f"/workflowscheme/{scheme_id}/draft/issuetype/{issue_type_id}"
            body = {"issueType": issue_type_id, "workflow": workflow_name}
        else:
            path = f"/workflowscheme/{scheme_id}/issuetype/{issue_type_id}"
            body = {
                "issueType": issue_type_id,
                "workflow": workflow_name,
                "updateDraftIfNeeded": True,
            }
        try:
            data = await client.put(path, json=body)
        except JiraApiError as e:
            raise ToolError(str(e))
        if isinstance(data, dict) and data.get("dry_run"):
            return data
        return {
            "success": True,
            "scheme_id": scheme_id,
            "issue_type_id": issue_type_id,
            "workflow": workflow_name,
            "edited_draft": edit_draft,
        }

    @mcp.tool(
        name="jira_workflows_delete_scheme_issuetype",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_scheme_issuetype(
        scheme_id: Annotated[int, "Workflow scheme ID"],
        issue_type_id: Annotated[str, "Issue type ID to unmap"],
        edit_draft: Annotated[
            bool,
            "True edits the scheme's existing DRAFT. False (default) edits the "
            "live scheme; in-use schemes auto-create a draft.",
        ] = False,
        ctx: Context = None,
    ) -> dict:
        """Remove an issue type's workflow mapping from a workflow scheme.

        The issue type falls back to the scheme's default workflow.
        Returns: {success, scheme_id, issue_type_id, edited_draft}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        if edit_draft:
            path = f"/workflowscheme/{scheme_id}/draft/issuetype/{issue_type_id}"
            params = None
        else:
            path = f"/workflowscheme/{scheme_id}/issuetype/{issue_type_id}"
            params = {"updateDraftIfNeeded": True}
        try:
            data = await client.delete(path, params=params)
        except JiraApiError as e:
            raise ToolError(str(e))
        if data.get("dry_run"):
            return data
        return {
            "success": True,
            "scheme_id": scheme_id,
            "issue_type_id": issue_type_id,
            "edited_draft": edit_draft,
        }

    @mcp.tool(
        name="jira_workflows_create_scheme_draft",
        annotations={"readOnlyHint": False},
    )
    async def create_scheme_draft(
        scheme_id: Annotated[int, "Workflow scheme ID to draft from"],
        ctx: Context = None,
    ) -> dict:
        """Create a draft of a workflow scheme so it can be edited safely.

        Use a draft when a scheme is in active use; edit the draft, then
        publish it with jira_workflows_publish_scheme_draft.
        Returns: {success, scheme_id, draft: {id, name}}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.post(f"/workflowscheme/{scheme_id}/createdraft")
        except JiraApiError as e:
            raise ToolError(str(e))
        if isinstance(data, dict) and data.get("dry_run"):
            return data
        return {
            "success": True,
            "scheme_id": scheme_id,
            "draft": {"id": data.get("id"), "name": data.get("name")},
        }

    @mcp.tool(
        name="jira_workflows_publish_scheme_draft",
        annotations={"readOnlyHint": False},
    )
    async def publish_scheme_draft(
        scheme_id: Annotated[int, "Workflow scheme ID whose draft to publish"],
        status_mappings: Annotated[
            list[dict] | None,
            "Status remappings for issues on removed statuses: "
            "[{'issueTypeId': '10001', 'statusId': '3', 'newStatusId': '1'}]. "
            "Omit if no statuses were removed.",
        ] = None,
        validate_only: Annotated[
            bool, "True returns validation results without publishing"
        ] = False,
        ctx: Context = None,
    ) -> dict:
        """Publish a workflow scheme draft, making its changes live.

        If the draft removes statuses that issues currently sit on, Jira
        requires status_mappings to relocate those issues.
        Returns: {success, scheme_id, validated_only} or validation result
        """
        client: JiraClient = ctx.lifespan_context["client"]
        body = {"statusMappings": status_mappings or []}
        try:
            data = await client.post(
                f"/workflowscheme/{scheme_id}/draft/publish",
                json=body,
                params={"validateOnly": validate_only},
            )
        except JiraApiError as e:
            raise ToolError(str(e))
        if isinstance(data, dict) and data.get("dry_run"):
            return data
        return {
            "success": True,
            "scheme_id": scheme_id,
            "validated_only": validate_only,
            "result": data if data else None,
        }
