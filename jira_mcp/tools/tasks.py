"""Task tools: poll and cancel long-running async Jira operations.

Two distinct async surfaces exist in Jira Cloud:
- generic tasks   -> GET /task/{taskId}        (reindex, scheme migration, etc.)
- bulk-op queue   -> GET /bulk/queue/{taskId}  (the /bulk/issues/* endpoints)
They are NOT interchangeable, so jira_tasks_get_status routes by `kind`.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from jira_mcp.client import JiraClient, JiraApiError


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="jira_tasks_get_status",
        annotations={"readOnlyHint": True},
    )
    async def get_task_status(
        task_id: Annotated[str, "Task ID returned by an async operation"],
        kind: Annotated[
            str,
            "'generic' for /task/{id} (reindex, migrations) or "
            "'bulk_queue' for /bulk/queue/{id} (bulk transition/edit/move/delete)",
        ] = "generic",
        ctx: Context = None,
    ) -> dict:
        """Poll the status of a long-running async Jira task.

        Returns: {task_id, kind, status, progress_percent, result, message,
                  submitted, started, finished, elapsed_ms}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        k = kind.lower()
        if k in ("generic", "task"):
            path = f"/task/{task_id}"
        elif k in ("bulk_queue", "bulk", "queue"):
            path = f"/bulk/queue/{task_id}"
        else:
            raise ToolError("kind must be 'generic' or 'bulk_queue'")

        try:
            data = await client.get(path)
        except JiraApiError as e:
            raise ToolError(str(e))

        return {
            "task_id": task_id,
            "kind": k,
            "status": data.get("status"),
            "progress_percent": data.get("progress") or data.get("progressPercent"),
            "result": data.get("result"),
            "message": data.get("message"),
            "submitted": data.get("submitted") or data.get("created"),
            "started": data.get("started"),
            "finished": data.get("finished") or data.get("ended"),
            "elapsed_ms": data.get("elapsedRuntime"),
            "raw": data,
        }

    @mcp.tool(
        name="jira_tasks_cancel",
        annotations={"readOnlyHint": False},
    )
    async def cancel_task(
        task_id: Annotated[str, "Generic task ID to cancel (/task/{id})"],
        ctx: Context = None,
    ) -> dict:
        """Request cancellation of a running generic async task.

        Only applies to /task/{id} tasks that are cancellable; bulk-queue
        tasks cannot be cancelled this way.
        Returns: {success, task_id, note}
        """
        client: JiraClient = ctx.lifespan_context["client"]
        try:
            data = await client.post(f"/task/{task_id}/cancel")
        except JiraApiError as e:
            raise ToolError(str(e))
        if isinstance(data, dict) and data.get("dry_run"):
            return data
        return {
            "success": True,
            "task_id": task_id,
            "note": "Cancellation requested; poll jira_tasks_get_status to confirm.",
        }
