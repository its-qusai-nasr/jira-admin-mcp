# Publishing checklist

This repo is ready to publish. Owner/repo are already set to
`its-qusai-nasr/jira-admin-mcp` throughout (README, pyproject, server.json,
CONTRIBUTING). Start at step 1.

## 0. (done) OWNER placeholder replaced

All URLs, badges, and the `mcp-name:` marker now point at
`https://github.com/its-qusai-nasr/jira-admin-mcp`. Nothing to do here unless
you rename the repo - in which case update those same files and, to keep the
PyPI/import names matching, also `name` in `pyproject.toml` and the `jira_mcp/`
package dir.

## 1. Create the GitHub repo and push

```bash
git remote add origin https://github.com/its-qusai-nasr/jira-admin-mcp.git
git push -u origin main
```

CI (`.github/workflows/ci.yml`) runs lint + tests on Python 3.10-3.13 automatically.

## 2. PyPI Trusted Publishing (one time, no tokens)

1. Reserve the name `jira-admin-mcp` on <https://pypi.org> (it must be free; if
   taken, change `name` in `pyproject.toml` and the docs).
2. On PyPI: **Your projects -> jira-admin-mcp -> Publishing -> Add a pending
   publisher**:
   - Owner: `its-qusai-nasr`
   - Repository: `jira-admin-mcp`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. Tag a release - the publish workflow builds and uploads via OIDC:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 3. List on the MCP Registry (optional)

`server.json` is ready (PyPI package + stdio transport + env vars). After the
PyPI release is live:

1. Install the registry CLI: see <https://github.com/modelcontextprotocol/registry>.
2. Authenticate with GitHub (this proves ownership of the
   `io.github.its-qusai-nasr/...` namespace) and publish:

```bash
mcp-publisher login github
mcp-publisher publish
```

The registry verifies namespace ownership against the `mcp-name:` marker that is
already in `README.md` (it ships in the PyPI long description).

## 4. After publishing

- Confirm `uvx jira-admin-mcp` works from a clean machine.
- The README badges (PyPI version, CI) light up once the repo + first release exist.
