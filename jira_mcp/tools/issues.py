"""Issue tools: search, get, create, update, transition, assign, delete, link, changelog, bulk_create."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError
from jira_mcp.helpers import format_issue_summary, format_issue_full, text_to_adf, is_adf


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_issues_search",
        annotations={"readOnlyHint": True},
    )
    async def search_issues(
        jql_query: Annotated[str, "JQL query string. Examples: 'project = PROJ AND status = \"To Do\"', 'assignee = currentUser() ORDER BY updated DESC'"],
        fields: Annotated[str, "Comma-separated field names to return. Default: key,summary,status,assignee,priority,issuetype,updated"] = "key,summary,status,assignee,priority,issuetype,updated",
        max_results: Annotated[int, "Maximum results (1-100). Default: 50"] = 50,
        next_page_token: Annotated[str | None, "Token for next page, from a previous search call"] = None,
        detail: Annotated[str, "'summary' (default) or 'full' (includes description, custom fields)"] = "summary",
        ctx: Context = None,
    ) -> dict:
        """Search Jira issues using JQL.

        Use this to find issues matching criteria. Prefer targeted JQL over broad searches.
        Not this when you know the exact issue key: use jira_issues_get instead.
        Returns: {total, issues: [{key, summary, status, assignee, ...}], next_page_token}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params = {
            "jql": jql_query,
            "fields": fields,
            "maxResults": min(max_results, 100),
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token
        try:
            data = await client.get("/search/jql", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        formatter = format_issue_full if detail == "full" else format_issue_summary
        issues_list = [formatter(i) for i in data.get("issues", [])]
        return {
            "total": data.get("total", len(issues_list)),
            "issues": issues_list,
            "next_page_token": data.get("nextPageToken"),
        }

    @mcp.tool(
        name="jira_issues_get",
        annotations={"readOnlyHint": True},
    )
    async def get_issue(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123', 'OPS-100'"],
        detail: Annotated[str, "'summary' (key fields) or 'full' (all fields including custom fields and description)"] = "summary",
        ctx: Context = None,
    ) -> dict:
        """Get a single Jira issue by key.

        Use this when you know the exact issue key.
        Not this for searching: use jira_issues_search with JQL instead.
        Returns: {key, summary, status, issue_type, assignee, reporter, priority, project, ...}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/issue/{issue_key}")
        except JiraApiError as e:
            raise ToolError(f"{e}. Verify the issue key format (e.g. PROJ-123).")

        if detail == "full":
            return format_issue_full(data)
        return format_issue_summary(data)

    @mcp.tool(
        name="jira_issues_create",
        annotations={"readOnlyHint": False, "idempotentHint": False},
    )
    async def create_issue(
        project_key: Annotated[str, "Project key, e.g. 'PROJ', 'OPS'"],
        issue_type: Annotated[str, "Issue type name, e.g. 'Task', 'Bug', 'Story'"],
        summary: Annotated[str, "Issue summary/title"],
        description: Annotated[str | None, "Plain text or ADF JSON string. Plain text is auto-converted."] = None,
        assignee_account_id: Annotated[str | None, "Assignee's account ID from jira_users_search"] = None,
        priority: Annotated[str | None, "Priority: 'Highest', 'High', 'Medium', 'Low', 'Lowest'"] = None,
        labels: Annotated[list[str] | None, "List of label strings"] = None,
        custom_fields: Annotated[dict | None, "Dict of custom field ID to value, e.g. {'customfield_10001': {'value': 'High'}}"] = None,
        ctx: Context = None,
    ) -> dict:
        """Create a new Jira issue.

        Use jira_issues_get_createmeta first to check required fields for the project/issue type.
        Custom fields must use their field ID (customfield_XXXXX).
        Returns: {key, id} of the created issue.
        """
        client: JiraClient = ctx.lifespan_context["client"]
        fields_payload: dict = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": summary,
        }
        if description:
            fields_payload["description"] = text_to_adf(description) if not is_adf(description) else description
        if assignee_account_id:
            fields_payload["assignee"] = {"accountId": assignee_account_id}
        if priority:
            fields_payload["priority"] = {"name": priority}
        if labels:
            fields_payload["labels"] = labels
        if custom_fields:
            fields_payload.update(custom_fields)

        try:
            data = await client.post("/issue", json={"fields": fields_payload})
        except JiraApiError as e:
            raise ToolError(f"{e}. Use jira_issues_get_createmeta to check required fields.")

        return {"key": data.get("key"), "id": data.get("id")}

    @mcp.tool(
        name="jira_issues_update",
        annotations={"readOnlyHint": False, "idempotentHint": True},
    )
    async def update_issue(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123'"],
        fields: Annotated[dict, "Dict of field name/ID to new value. Examples: {'summary': 'New title'}, {'customfield_10001': {'value': 'High'}}"],
        notify_users: Annotated[bool, "Send email notifications. Default: False"] = False,
        ctx: Context = None,
    ) -> dict:
        """Update fields on an existing Jira issue.

        For select/dropdown: {'value': 'Option'}. For users: {'accountId': '...'}.
        Use jira_issues_get first to check current values.
        Returns: {success, issue_key}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params = {"notifyUsers": str(notify_users).lower()}
        try:
            await client.put(f"/issue/{issue_key}", json={"fields": fields}, params=params)
        except JiraApiError as e:
            raise ToolError(str(e))

        return {"success": True, "issue_key": issue_key}

    @mcp.tool(
        name="jira_issues_transition",
        annotations={"readOnlyHint": False},
    )
    async def transition_issue(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123'"],
        target_status: Annotated[str, "Target status name, e.g. 'In Progress', 'Done'. Case-insensitive."],
        comment: Annotated[str | None, "Optional comment to add with the transition"] = None,
        resolution: Annotated[str | None, "Resolution name if transitioning to Done, e.g. 'Done', 'Won't Do'"] = None,
        ctx: Context = None,
    ) -> dict:
        """Transition a Jira issue to a new status.

        Automatically resolves the transition ID from the target status name.
        Use jira_issues_get_transitions to see available transitions first.
        Returns: {success, issue_key, from_status, to_status}
        """
        client: JiraClient = ctx.lifespan_context["client"]

        # Get available transitions
        try:
            trans_data = await client.get(f"/issue/{issue_key}/transitions")
        except JiraApiError as e:
            raise ToolError(str(e))

        transitions = trans_data.get("transitions", [])
        target_lower = target_status.lower()
        match = None
        for t in transitions:
            if t.get("to", {}).get("name", "").lower() == target_lower:
                match = t
                break

        if not match:
            available = [f"{t.get('name')} -> {t.get('to', {}).get('name')}" for t in transitions]
            raise ToolError(
                f"No transition to '{target_status}' available for {issue_key}. "
                f"Available transitions: {', '.join(available) or 'none'}. "
                f"Use jira_issues_get_transitions to check."
            )

        body: dict = {"transition": {"id": match["id"]}}
        if comment:
            body["update"] = {
                "comment": [{"add": {"body": text_to_adf(comment)}}]
            }
        if resolution:
            body.setdefault("fields", {})["resolution"] = {"name": resolution}

        try:
            await client.post(f"/issue/{issue_key}/transitions", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))

        return {
            "success": True,
            "issue_key": issue_key,
            "to_status": match.get("to", {}).get("name"),
        }

    @mcp.tool(
        name="jira_issues_assign",
        annotations={"readOnlyHint": False, "idempotentHint": True},
    )
    async def assign_issue(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123'"],
        assignee_account_id: Annotated[str | None, "Account ID from jira_users_search. Pass null to unassign."] = None,
        ctx: Context = None,
    ) -> dict:
        """Assign a Jira issue to a user, or unassign it.

        Use jira_users_search first to look up the account ID.
        Returns: {success, issue_key, assignee_account_id}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            await client.put(f"/issue/{issue_key}/assignee", json={"accountId": assignee_account_id})
        except JiraApiError as e:
            raise ToolError(str(e))
        return {"success": True, "issue_key": issue_key, "assignee_account_id": assignee_account_id}

    @mcp.tool(
        name="jira_issues_get_transitions",
        annotations={"readOnlyHint": True},
    )
    async def get_transitions(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123'"],
        ctx: Context = None,
    ) -> dict:
        """Get available workflow transitions for an issue.

        Use this before jira_issues_transition to see valid target statuses.
        Returns: {issue_key, transitions: [{id, name, to_status}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(f"/issue/{issue_key}/transitions")
        except JiraApiError as e:
            raise ToolError(str(e))

        transitions = [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "to_status": t.get("to", {}).get("name"),
            }
            for t in data.get("transitions", [])
        ]
        return {"issue_key": issue_key, "transitions": transitions}

    @mcp.tool(
        name="jira_issues_get_createmeta",
        annotations={"readOnlyHint": True},
    )
    async def get_createmeta(
        project_key: Annotated[str, "Project key, e.g. 'PROJ'"],
        issue_type_id: Annotated[str | None, "Issue type ID for field details. Omit to list available issue types."] = None,
        ctx: Context = None,
    ) -> dict:
        """Get metadata for creating issues in a project.

        Without issue_type_id: returns available issue types.
        With issue_type_id: returns required and optional fields for that type.
        Use this before jira_issues_create to understand required fields.
        Returns: {project_key, issue_types: [...]} or {project_key, issue_type, required_fields: [...], optional_fields: [...]}
        """
        client: JiraClient = ctx.lifespan_context["client"]

        if not issue_type_id:
            try:
                data = await client.get(f"/issue/createmeta/{project_key}/issuetypes")
            except JiraApiError as e:
                raise ToolError(str(e))
            types = [
                {"id": t.get("id"), "name": t.get("name"), "subtask": t.get("subtask", False)}
                for t in data.get("issueTypes", data.get("values", []))
            ]
            return {"project_key": project_key, "issue_types": types}

        try:
            data = await client.get(f"/issue/createmeta/{project_key}/issuetypes/{issue_type_id}")
        except JiraApiError as e:
            raise ToolError(str(e))

        required = []
        optional = []
        for f in data.get("fields", data.get("values", [])):
            field_info = {
                "field_id": f.get("fieldId"),
                "name": f.get("name"),
                "required": f.get("required", False),
                "schema_type": f.get("schema", {}).get("type") if isinstance(f.get("schema"), dict) else None,
            }
            if f.get("required"):
                required.append(field_info)
            else:
                optional.append(field_info)

        return {
            "project_key": project_key,
            "issue_type_id": issue_type_id,
            "required_fields": required,
            "optional_fields": optional[:20],  # Cap to avoid noise
        }

    @mcp.tool(
        name="jira_issues_delete",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_issue(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123'"],
        delete_subtasks: Annotated[bool, "Also delete subtasks. Default: False"] = False,
        ctx: Context = None,
    ) -> dict:
        """Delete a Jira issue permanently.

        This is irreversible. Use with caution: confirm with an admin before deleting.
        Set delete_subtasks=True to also delete all subtasks.
        Returns: {success, issue_key}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        params = {"deleteSubtasks": str(delete_subtasks).lower()}
        try:
            await client.delete(f"/issue/{issue_key}", params=params)
        except JiraApiError as e:
            raise ToolError(str(e))
        return {"success": True, "issue_key": issue_key}

    @mcp.tool(
        name="jira_issues_link",
        annotations={"readOnlyHint": False},
    )
    async def link_issues(
        inward_issue_key: Annotated[str, "The issue that is the target (inward side), e.g. 'PROJ-1'"],
        outward_issue_key: Annotated[str, "The issue that is the source (outward side), e.g. 'PROJ-2'"],
        link_type: Annotated[str, "Link type name: 'Blocks', 'Cloners', 'Duplicate', 'Relates', etc. Use jira_issue_link_types_list to see all."],
        ctx: Context = None,
    ) -> dict:
        """Create a link between two Jira issues.

        Example: link_issues('PROJ-1', 'PROJ-2', 'Blocks') means PROJ-2 blocks PROJ-1.
        Use jira_issue_link_types_list to see available link types with inward/outward labels.
        Returns: {success, inward_issue, outward_issue, link_type}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        body = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_issue_key},
            "outwardIssue": {"key": outward_issue_key},
        }
        try:
            await client.post("/issueLink", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))
        return {
            "success": True,
            "inward_issue": inward_issue_key,
            "outward_issue": outward_issue_key,
            "link_type": link_type,
        }

    @mcp.tool(
        name="jira_issues_get_changelog",
        annotations={"readOnlyHint": True},
    )
    async def get_changelog(
        issue_key: Annotated[str, "Issue key, e.g. 'PROJ-123'"],
        max_results: Annotated[int, "Max changelog entries. Default: 25"] = 25,
        ctx: Context = None,
    ) -> dict:
        """Get the changelog (audit history) of an issue.

        Shows who changed what fields and when. Useful for auditing.
        Returns: {issue_key, total, changes: [{created, author, items: [{field, from, to}]}]}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.get(
                f"/issue/{issue_key}/changelog",
                params={"maxResults": min(max_results, 100)},
            )
        except JiraApiError as e:
            raise ToolError(str(e))

        changes = [
            {
                "created": c.get("created"),
                "author": c.get("author", {}).get("displayName"),
                "items": [
                    {
                        "field": item.get("field"),
                        "from": item.get("fromString"),
                        "to": item.get("toString"),
                    }
                    for item in c.get("items", [])
                ],
            }
            for c in data.get("values", [])
        ]
        return {
            "issue_key": issue_key,
            "total": data.get("total", len(changes)),
            "changes": changes,
        }

    @mcp.tool(
        name="jira_issues_bulk_create",
        annotations={"readOnlyHint": False, "idempotentHint": False},
    )
    async def bulk_create_issues(
        issues: Annotated[list[dict], "List of issue payloads. Each: {'project_key': 'PROJ', 'issue_type': 'Task', 'summary': '...', 'description': '...', 'custom_fields': {...}}. Max 50."],
        ctx: Context = None,
    ) -> dict:
        """Create multiple Jira issues in one call (up to 50).

        Each issue in the list needs at minimum: project_key, issue_type, summary.
        Optional: description, assignee_account_id, priority, labels, custom_fields.
        Returns: {created: [{key, id}], errors: [...]}
        """
        client: JiraClient = ctx.lifespan_context["client"]

        if len(issues) > 50:
            raise ToolError("Maximum 50 issues per bulk create call.")

        issue_updates = []
        for iss in issues:
            fields_payload: dict = {
                "project": {"key": iss["project_key"]},
                "issuetype": {"name": iss["issue_type"]},
                "summary": iss["summary"],
            }
            if iss.get("description"):
                desc = iss["description"]
                fields_payload["description"] = text_to_adf(desc) if not is_adf(desc) else desc
            if iss.get("assignee_account_id"):
                fields_payload["assignee"] = {"accountId": iss["assignee_account_id"]}
            if iss.get("priority"):
                fields_payload["priority"] = {"name": iss["priority"]}
            if iss.get("labels"):
                fields_payload["labels"] = iss["labels"]
            if iss.get("custom_fields"):
                fields_payload.update(iss["custom_fields"])
            issue_updates.append({"fields": fields_payload})

        try:
            data = await client.post("/issue/bulk", json={"issueUpdates": issue_updates})
        except JiraApiError as e:
            raise ToolError(str(e))

        created = [{"key": i.get("key"), "id": i.get("id")} for i in data.get("issues", [])]
        errors = data.get("errors", [])
        return {"created": created, "errors": errors}
