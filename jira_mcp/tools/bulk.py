"""Bulk operation tools: edit and transition multiple issues."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_bulk_edit_issues",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def bulk_edit_issues(
        issue_keys: Annotated[list[str], "List of issue keys, e.g. ['PROJ-1', 'PROJ-2', 'PROJ-3']"],
        fields: Annotated[dict, "Fields to set on all issues. Same format as jira_issues_update."],
        send_notification: Annotated[bool, "Send email notifications. Default: False"] = False,
        ctx: Context = None,
    ) -> dict:
        """Bulk edit fields on multiple Jira issues.

        All issues get the same field values set. For batch operations like
        bulk-setting labels, priorities, or custom fields.
        Returns: {success, updated_count} or dry_run info.
        """
        client: JiraClient = ctx.lifespan_context["client"]

        # Resolve issue IDs from keys
        issue_ids = []
        for key in issue_keys:
            try:
                issue = await client.get(f"/issue/{key}", params={"fields": "summary"})
                issue_ids.append(issue.get("id"))
            except JiraApiError as e:
                raise ToolError(f"Failed to resolve {key}: {e}")

        # Build edit payload
        edit_fields = []
        for field_id, value in fields.items():
            edit_fields.append({
                "fieldId": field_id,
                "value": value,
            })

        body = {
            "editedFieldsInput": {
                "editEntries": edit_fields,
            },
            "selectedIssueIdsOrKeys": issue_keys,
            "sendNotification": send_notification,
        }

        try:
            data = await client.post("/bulk/issues/fields", json=body)
        except JiraApiError as e:
            raise ToolError(str(e))

        return {
            "success": True,
            "task_id": data.get("taskId"),
            "issue_count": len(issue_keys),
        }

    @mcp.tool(
        name="jira_bulk_transition_issues",
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def bulk_transition_issues(
        issue_keys: Annotated[list[str], "List of issue keys to transition"],
        target_status: Annotated[str, "Target status name, e.g. 'Done', 'In Progress'. All issues must have this transition available."],
        send_notification: Annotated[bool, "Send email notifications. Default: False"] = False,
        ctx: Context = None,
    ) -> dict:
        """Bulk transition multiple issues to a new status.

        All issues must have an available transition to the target status.
        Automatically resolves transition IDs.
        Returns: {success, transitioned_count, target_status}
        """
        client: JiraClient = ctx.lifespan_context["client"]

        # Get transitions for the first issue to find the transition ID
        if not issue_keys:
            raise ToolError("issue_keys must not be empty")

        try:
            trans_data = await client.get(f"/issue/{issue_keys[0]}/transitions")
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
            available = [t.get("to", {}).get("name") for t in transitions]
            raise ToolError(
                f"No transition to '{target_status}' available. "
                f"Available: {', '.join(available)}."
            )

        # Transition each issue
        succeeded = []
        failed = []
        for key in issue_keys:
            try:
                await client.post(
                    f"/issue/{key}/transitions",
                    json={"transition": {"id": match["id"]}},
                )
                succeeded.append(key)
            except JiraApiError as e:
                failed.append({"key": key, "error": str(e)})

        return {
            "success": len(failed) == 0,
            "transitioned": succeeded,
            "failed": failed,
            "target_status": target_status,
        }
