# Contributing

Thanks for your interest in improving the Jira Admin MCP server.

## Development setup

This project uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/OWNER/jira-admin-mcp
cd jira-admin-mcp
uv sync --extra dev        # installs runtime + dev dependencies into .venv
cp .env.example .env       # add your own Jira credentials for live testing
```

## Before you open a PR

```bash
uv run ruff check .        # lint
uv run pytest              # unit tests (no network)
```

Test interactively against the MCP protocol with the Inspector:

```bash
npx @modelcontextprotocol/inspector uvx --from . jira-mcp
```

For changes that hit Jira, run with `JIRA_DRY_RUN=true` first so writes are simulated.

## Project layout

```
jira_mcp/
  server.py        FastMCP app + tool registration + server instructions
  config.py        env-var loading and validation
  client.py        async httpx client, auth, dry-run, error handling
  helpers.py       response cleaning, field projection, ADF helpers
  tools/           one module per tool group (issues, users, fields, ...)
tests/             unit tests (config, helpers, tool registration)
```

## Conventions

- A tool lives in the module matching its group and is registered in that module's `register(mcp)` function.
- Mark read-only tools with `annotations={"readOnlyHint": True}`; mark destructive ones with `destructiveHint`.
- Keep docstrings generic and example-driven (e.g. `PROJ-123`, `customfield_10001`). Do not hardcode any real instance, user, or field.
- Every write goes through `JiraClient.post/put/delete` so dry-run is honored automatically.
- No em dashes in code, comments, or docs - use a hyphen, colon, or parentheses.

## Reporting issues

Please include your client (Claude Desktop, Cursor, etc.), the tool you called, and the full error message. Never paste API tokens or other secrets.
