# Jira Admin MCP Server

[![PyPI version](https://img.shields.io/pypi/v/jira-admin-mcp.svg)](https://pypi.org/project/jira-admin-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/OWNER/jira-admin-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/jira-admin-mcp/actions/workflows/ci.yml)
[![MCP](https://img.shields.io/badge/MCP-server-000.svg)](https://modelcontextprotocol.io)

A [Model Context Protocol](https://modelcontextprotocol.io) server that gives an AI assistant (Claude, Cursor, VS Code, or any MCP client) **78 purpose-built tools to administer a Jira Cloud site** - not just read and create tickets, but the behind-the-scenes admin work: custom fields and where they appear, permission schemes, workflows, screens, issue-type schemes, groups, project roles, saved filters, and bulk operations.

Most Jira MCP servers cover everyday usage. This one covers **administration**, and adds safety rails (dry-run mode, shared-scheme detection, identity checks before group changes, actionable errors) so an agent can run real admin jobs end to end.

> Built with [FastMCP](https://gofastmcp.com). Talks to the Jira Cloud REST API v3 with your own Atlassian email + API token.

---

## Quick start

You need three things from your own Jira: a **base URL**, your **account email**, and an **API token** ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens)). The token inherits your Jira permissions, so for admin tasks use an account with the right access.

The easiest way to run an MCP server today is [`uv`](https://docs.astral.sh/uv/) / `uvx` - it handles Python and dependencies for you, no manual virtualenv. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) first, then pick one of the options below.

### Option A - run straight from GitHub (no clone, no PyPI)

Add this to your MCP client config (see [client setup](#client-setup) for file locations):

```json
{
  "mcpServers": {
    "jira-admin": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/OWNER/jira-admin-mcp", "jira-mcp"],
      "env": {
        "JIRA_BASE_URL": "https://your-company.atlassian.net",
        "JIRA_EMAIL": "you@your-company.com",
        "JIRA_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

### Option B - from PyPI (once published)

```json
{
  "mcpServers": {
    "jira-admin": {
      "command": "uvx",
      "args": ["jira-admin-mcp"],
      "env": {
        "JIRA_BASE_URL": "https://your-company.atlassian.net",
        "JIRA_EMAIL": "you@your-company.com",
        "JIRA_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

### Option C - clone for development

```bash
git clone https://github.com/OWNER/jira-admin-mcp
cd jira-admin-mcp
uv sync                 # creates .venv and installs deps from uv.lock
cp .env.example .env    # then edit .env with your Jira credentials
uv run jira-mcp         # starts the server over stdio
```

With a cloned checkout, point your client at it:

```json
{
  "mcpServers": {
    "jira-admin": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/jira-admin-mcp", "jira-mcp"]
    }
  }
}
```

---

## Configuration

The server reads its settings from environment variables (passed via the `env` block above, or from a `.env` file in the project directory when you run a local clone).

| Variable | Required | Description |
|---|---|---|
| `JIRA_BASE_URL` | yes | Your Jira Cloud base URL, e.g. `https://your-company.atlassian.net` |
| `JIRA_EMAIL` | yes | The Atlassian account email that owns the API token |
| `JIRA_API_TOKEN` | yes | API token from <https://id.atlassian.com/manage-profile/security/api-tokens> |
| `JIRA_DRY_RUN` | no | `true` simulates all writes (POST/PUT/DELETE) and returns the payload that *would* be sent, without calling Jira. Defaults to `false`. |

> **Tip:** set `JIRA_DRY_RUN=true` for your first session. Every write tool will return a `{"dry_run": true, "would_call": ...}` preview so you can watch what the agent intends to do before letting it touch live data.

---

## Client setup

Add the JSON block from the [Quick start](#quick-start) to your client's MCP config:

- **Claude Desktop** - `claude_desktop_config.json`
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- **Claude Code** - a `.mcp.json` file at your project root (or `claude mcp add`)
- **Cursor** - `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per project)
- **VS Code** - `.vscode/mcp.json` (uses a top-level `"servers"` key instead of `"mcpServers"`)

Restart the client after editing the config. The server appears as `jira-admin` with all 78 tools.

---

## What you can ask for

Once connected, the assistant can do things like:

- "Add `alice@example.com` to the `jira-developers` group."
- "Scope the `Team` custom field to projects ENG and OPS only, for the Story and Bug issue types."
- "Which projects share permission scheme 10789? I want to edit it without breaking the others."
- "Move every `Internal Task` in project OPS to the `Task` type, then transition the open ones to In Progress."
- "Create a saved filter for unresolved bugs assigned to me and share it with the developers group."
- "Show me the change history for PROJ-123 and tell me who reopened it."

---

## Tools (78 total)

<details>
<summary><b>Issues (12)</b></summary>

| Tool | Description |
|---|---|
| `jira_issues_search` | Search issues using JQL with pagination |
| `jira_issues_get` | Get single issue by key (summary or full detail) |
| `jira_issues_create` | Create issue with project, type, fields |
| `jira_issues_update` | Update fields on existing issue |
| `jira_issues_transition` | Transition to new status (auto-resolves transition ID) |
| `jira_issues_assign` | Assign/unassign issue |
| `jira_issues_get_transitions` | List available workflow transitions |
| `jira_issues_get_createmeta` | Get required fields for creating issues |
| `jira_issues_delete` | Delete an issue permanently |
| `jira_issues_link` | Create a link between two issues |
| `jira_issues_get_changelog` | Get audit history (who changed what) |
| `jira_issues_bulk_create` | Bulk create up to 50 issues |
</details>

<details>
<summary><b>Comments (2)</b></summary>

| Tool | Description |
|---|---|
| `jira_comments_list` | List comments on an issue |
| `jira_comments_add` | Add comment (plain text auto-converted to ADF) |
</details>

<details>
<summary><b>Users (2)</b></summary>

| Tool | Description |
|---|---|
| `jira_users_search` | Search by email or display name |
| `jira_users_get` | Get user details + groups by account ID |
</details>

<details>
<summary><b>Groups (6)</b></summary>

| Tool | Description |
|---|---|
| `jira_groups_list` | List groups with member counts |
| `jira_groups_get_members` | Get members of a group |
| `jira_groups_add_user` | Add user to group |
| `jira_groups_remove_user` | Remove user from group |
| `jira_groups_create` | Create a new group |
| `jira_groups_delete` | Delete a group |
</details>

<details>
<summary><b>Projects (10)</b></summary>

| Tool | Description |
|---|---|
| `jira_projects_list` | List projects filtered by name/key |
| `jira_projects_get` | Get project details + issue types |
| `jira_projects_get_statuses` | All statuses grouped by issue type |
| `jira_projects_get_roles` | Roles with actors (users/groups) |
| `jira_projects_update_role` | Add/remove actors from project roles |
| `jira_projects_get_versions` | List versions/releases in a project |
| `jira_projects_create_version` | Create a new version/release |
| `jira_projects_get_features` | Get enabled/disabled features |
| `jira_projects_get_notification_scheme` | Get notification scheme |
| `jira_projects_get_categories` | List project categories |
</details>

<details>
<summary><b>Permissions (4)</b></summary>

| Tool | Description |
|---|---|
| `jira_permissions_list_schemes` | List all permission schemes |
| `jira_permissions_get_scheme` | Get scheme with all grants |
| `jira_permissions_add_grant` | Add permission grant to scheme |
| `jira_permissions_assign_scheme` | Assign scheme to project |
</details>

<details>
<summary><b>Custom Fields (12)</b></summary>

| Tool | Description |
|---|---|
| `jira_fields_search` | Search fields by name, find field IDs |
| `jira_fields_get_contexts` | Get contexts for a custom field |
| `jira_fields_get_options` | Get options for select/dropdown fields |
| `jira_fields_manage_options` | Add, update, or reorder field options |
| `jira_fields_create_context` | Create a context, optionally scoped to projects/issue types |
| `jira_fields_update_context` | Rename or re-describe a context |
| `jira_fields_delete_context` | Delete a context and its options |
| `jira_fields_assign_context_projects` | Scope a context to specific projects |
| `jira_fields_remove_context_projects` | Unscope projects from a context |
| `jira_fields_add_context_issuetypes` | Restrict a context to specific issue types |
| `jira_fields_remove_context_issuetypes` | Remove issue types from a context |
| `jira_fields_get_project_mapping` | Audit which projects each context covers |
</details>

<details>
<summary><b>Filters (10)</b></summary>

| Tool | Description |
|---|---|
| `jira_filters_search` | Search saved JQL filters |
| `jira_filters_create` | Create a new saved JQL filter |
| `jira_filters_get` | Get a filter with owner + share permissions |
| `jira_filters_update` | Update name/JQL/description |
| `jira_filters_delete` | Delete a filter permanently |
| `jira_filters_change_owner` | Change a filter's owner |
| `jira_filters_get_shares` | List a filter's share permissions |
| `jira_filters_add_share` | Add a share (requires you own the filter) |
| `jira_filters_remove_share` | Remove a share permission |
| `jira_filters_force_add_share` | Add a share to a filter you don't own (owner-swap workaround) |
</details>

<details>
<summary><b>Issue Links, Statuses (2)</b></summary>

| Tool | Description |
|---|---|
| `jira_issue_link_types_list` | List available link types (Blocks, Relates, etc.) |
| `jira_statuses_search` | Search statuses across the instance |
</details>

<details>
<summary><b>Workflows (8)</b></summary>

| Tool | Description |
|---|---|
| `jira_workflows_search` | Search workflows by name |
| `jira_workflows_get_schemes` | List workflow schemes |
| `jira_workflows_get_scheme_mappings` | Issue type to workflow mappings |
| `jira_workflows_get_scheme_project_usages` | List projects using a scheme (shared-scheme safety check) |
| `jira_workflows_set_scheme_issuetype` | Map an issue type to a workflow |
| `jira_workflows_delete_scheme_issuetype` | Remove an issue type's workflow mapping |
| `jira_workflows_create_scheme_draft` | Create an editable draft of a scheme |
| `jira_workflows_publish_scheme_draft` | Publish a scheme draft, making it live |
</details>

<details>
<summary><b>Issue Types, Screens (6)</b></summary>

| Tool | Description |
|---|---|
| `jira_issuetypes_list` | List issue types (optionally by project) |
| `jira_issuetypes_get_schemes` | List issue type schemes |
| `jira_issuetypes_get_scheme_mappings` | Issue types in a scheme |
| `jira_screens_list` | List screens |
| `jira_screens_get_fields` | Get fields on screen tabs |
| `jira_screens_get_schemes` | List screen schemes |
</details>

<details>
<summary><b>Bulk Operations, Tasks (4)</b></summary>

| Tool | Description |
|---|---|
| `jira_bulk_edit_issues` | Bulk edit fields on multiple issues |
| `jira_bulk_transition_issues` | Bulk transition issues to new status |
| `jira_tasks_get_status` | Poll a generic task or bulk-queue task by ID |
| `jira_tasks_cancel` | Request cancellation of a generic async task |
</details>

---

## Design notes

- **Consolidate, don't wrap** - 78 workflow-oriented tools rather than a 1:1 mirror of every REST endpoint.
- **Dry run** - `JIRA_DRY_RUN=true` makes all write ops return simulated payloads.
- **Response filtering** - strips `self`, `_links`, `avatarUrls`, and similar noise so the agent sees only useful fields.
- **Detail levels** - read tools take `detail="summary"` (default) or `detail="full"`.
- **ADF auto-wrap** - plain text in comments/descriptions is auto-converted to Atlassian Document Format.
- **Transition resolution** - `jira_issues_transition` resolves a status name to its transition ID automatically.
- **Actionable errors** - error messages say what went wrong and what to try next.
- **Token-auth scope** - webhook endpoints (`/webhook`) are intentionally not wrapped; Atlassian restricts them to Connect / OAuth 2.0 apps that token auth cannot satisfy.

---

## Testing locally

Inspect and call tools interactively with the [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector):

```bash
npx @modelcontextprotocol/inspector uvx --from . jira-mcp
```

Run the unit tests (no network calls):

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

---

## Security

- **Never commit credentials.** `.env` is gitignored; use the `env` block in your client config or your OS secret manager.
- **Least privilege.** The API token acts as your Jira user. Use an account scoped to only what you need, especially for write/admin tools.
- **Start in dry-run.** `JIRA_DRY_RUN=true` lets you review every intended write before going live.
- See the official [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices).

---

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)

<!-- mcp-name: io.github.OWNER/jira-admin-mcp -->

