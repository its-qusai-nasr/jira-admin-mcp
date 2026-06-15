"""Response cleaning, field projection, and formatting utilities."""

from __future__ import annotations

from typing import Any

# Fields to always strip from Jira API responses
STRIP_FIELDS = {
    "self", "_links", "expand", "avatarUrls", "iconUrl",
    "statusUrl", "style", "avatarId",
}


def clean(obj: Any, strip: set[str] | None = None) -> Any:
    """Recursively remove noise fields from a Jira API response."""
    strip = strip or STRIP_FIELDS
    if isinstance(obj, dict):
        return {k: clean(v, strip) for k, v in obj.items() if k not in strip}
    elif isinstance(obj, list):
        return [clean(item, strip) for item in obj]
    return obj


def pick(obj: dict, keys: list[str]) -> dict:
    """Project specific keys from a dict. Supports dotted paths like 'fields.summary'."""
    result = {}
    for key in keys:
        if "." in key:
            parts = key.split(".", 1)
            val = obj.get(parts[0])
            if isinstance(val, dict):
                inner = val.get(parts[1])
                if inner is not None:
                    result[key.replace(".", "_")] = inner
        else:
            if key in obj:
                result[key] = obj[key]
    return result


def format_issue_summary(issue: dict) -> dict:
    """Extract high-signal fields from a full issue response."""
    f = issue.get("fields", {})
    return {
        "key": issue.get("key"),
        "summary": f.get("summary"),
        "status": _name(f.get("status")),
        "issue_type": _name(f.get("issuetype")),
        "assignee": _name(f.get("assignee"), key="displayName"),
        "reporter": _name(f.get("reporter"), key="displayName"),
        "priority": _name(f.get("priority")),
        "project": _name(f.get("project"), key="key"),
        "created": f.get("created"),
        "updated": f.get("updated"),
    }


def format_issue_full(issue: dict) -> dict:
    """Full issue with all fields cleaned."""
    result = format_issue_summary(issue)
    f = issue.get("fields", {})
    result.update({
        "description": f.get("description"),
        "labels": f.get("labels", []),
        "components": [c.get("name") for c in (f.get("components") or [])],
        "fix_versions": [v.get("name") for v in (f.get("fixVersions") or [])],
        "due_date": f.get("duedate"),
        "resolution": _name(f.get("resolution")) if f.get("resolution") else None,
        "custom_fields": {
            k: _extract_cf_value(v) for k, v in f.items()
            if k.startswith("customfield_") and v is not None
        },
    })
    return result


def format_user(user: dict) -> dict:
    """Extract key user fields."""
    return {
        "account_id": user.get("accountId"),
        "display_name": user.get("displayName"),
        "email": user.get("emailAddress"),
        "active": user.get("active"),
    }


def format_group(group: dict) -> dict:
    """Extract key group fields."""
    return {
        "name": group.get("name"),
        "group_id": group.get("groupId"),
        "member_count": group.get("memberCount"),
    }


def format_project(project: dict) -> dict:
    """Extract key project fields."""
    return {
        "id": project.get("id"),
        "key": project.get("key"),
        "name": project.get("name"),
        "project_type": project.get("projectTypeKey"),
        "lead": _name(project.get("lead"), key="displayName"),
    }


def text_to_adf(text: str) -> dict:
    """Wrap plain text in minimal Atlassian Document Format."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def is_adf(value: Any) -> bool:
    """Check if a value looks like ADF JSON."""
    return isinstance(value, dict) and value.get("type") == "doc"


def _name(obj: Any, key: str = "name") -> str | None:
    """Safely extract a named field from a Jira object."""
    if isinstance(obj, dict):
        return obj.get(key)
    return None


def _extract_cf_value(value: Any) -> Any:
    """Extract readable value from custom field data."""
    if isinstance(value, dict):
        # Option fields: {"value": "..."}
        if "value" in value:
            return value["value"]
        # User fields: {"displayName": "..."}
        if "displayName" in value:
            return value["displayName"]
        # Nested name: {"name": "..."}
        if "name" in value:
            return value["name"]
        return value
    if isinstance(value, list):
        return [_extract_cf_value(v) for v in value]
    return value
