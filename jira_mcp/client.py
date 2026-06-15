"""Shared Jira HTTP client with auth, error handling, and dry-run support."""

from __future__ import annotations

from typing import Any

import httpx

from jira_mcp.config import JiraConfig


class JiraApiError(Exception):
    """Jira API error with actionable message for the LLM."""


class JiraClient:
    """Async HTTP client for Jira Cloud REST API v3."""

    def __init__(self, config: JiraConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_base,
            auth=(config.email, config.api_token),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def get(self, path: str, params: dict | None = None) -> dict | list:
        """GET request - always executes (read-only)."""
        resp = await self._client.get(path, params=params)
        self._check(resp)
        return resp.json()

    async def post(
        self, path: str, json: Any = None, params: dict | None = None
    ) -> dict:
        """POST request. Simulated if DRY_RUN is enabled."""
        if self.config.dry_run:
            return {"dry_run": True, "would_call": f"POST {path}", "params": params, "body": json}
        resp = await self._client.post(path, json=json, params=params)
        self._check(resp)
        if resp.status_code == 204:
            return {"success": True}
        return resp.json()

    async def put(
        self, path: str, json: Any = None, params: dict | None = None
    ) -> dict:
        """PUT request. Simulated if DRY_RUN is enabled."""
        if self.config.dry_run:
            return {"dry_run": True, "would_call": f"PUT {path}", "params": params, "body": json}
        resp = await self._client.put(path, json=json, params=params)
        self._check(resp)
        if resp.status_code == 204:
            return {"success": True}
        return resp.json()

    async def delete(
        self, path: str, params: dict | None = None, json: Any = None
    ) -> dict:
        """DELETE request. Simulated if DRY_RUN is enabled.

        Some Jira DELETE endpoints (e.g. /webhook) require a request body:
        pass it via `json`.
        """
        if self.config.dry_run:
            return {
                "dry_run": True,
                "would_call": f"DELETE {path}",
                "params": params,
                "body": json,
            }
        if json is not None:
            resp = await self._client.request("DELETE", path, json=json, params=params)
        else:
            resp = await self._client.delete(path, params=params)
        self._check(resp)
        if resp.status_code == 204 or not resp.content:
            return {"success": True}
        try:
            return resp.json()
        except Exception:
            return {"success": True}

    def _check(self, resp: httpx.Response) -> None:
        """Raise descriptive errors for HTTP failures."""
        if resp.is_success:
            return

        try:
            body = resp.json()
            errors = body.get("errorMessages", [])
            field_errors = body.get("errors", {})
            parts = errors + [f"{k}: {v}" for k, v in field_errors.items()]
            detail = "; ".join(parts) if parts else resp.text[:500]
        except Exception:
            detail = resp.text[:500]

        status = resp.status_code
        if status == 401:
            raise JiraApiError("Authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN.")
        elif status == 403:
            raise JiraApiError(f"Permission denied: {detail}")
        elif status == 404:
            raise JiraApiError(f"Not found: {detail}")
        elif status == 400:
            raise JiraApiError(f"Bad request: {detail}")
        elif status == 429:
            raise JiraApiError("Rate limited by Jira. Wait a moment and retry.")
        else:
            raise JiraApiError(f"Jira API error ({status}): {detail}")

    async def close(self) -> None:
        await self._client.aclose()
