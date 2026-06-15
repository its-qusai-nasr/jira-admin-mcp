from fastmcp import Client

from jira_mcp.server import mcp

# A representative slice across tool groups; the full set is asserted by count.
EXPECTED_SAMPLE = {
    "jira_issues_search",
    "jira_issues_create",
    "jira_comments_add",
    "jira_users_search",
    "jira_groups_add_user",
    "jira_projects_list",
    "jira_permissions_get_scheme",
    "jira_fields_search",
    "jira_filters_create",
    "jira_workflows_get_schemes",
    "jira_issuetypes_list",
    "jira_screens_list",
    "jira_bulk_edit_issues",
    "jira_statuses_search",
    "jira_issue_link_types_list",
    "jira_tasks_get_status",
}


async def test_all_tools_registered():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    assert EXPECTED_SAMPLE <= names, EXPECTED_SAMPLE - names
    assert len(names) == 78


async def test_tool_names_are_namespaced():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert all(t.name.startswith("jira_") for t in tools)


async def test_read_only_and_write_hints():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    by_name = {t.name: t for t in tools}

    search = by_name["jira_issues_search"]
    assert search.annotations is not None
    assert search.annotations.readOnlyHint is True

    create = by_name["jira_issues_create"]
    read_only = getattr(create.annotations, "readOnlyHint", None) if create.annotations else None
    assert read_only in (None, False)
