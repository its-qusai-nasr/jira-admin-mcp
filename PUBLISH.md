# Publishing checklist

This repo is ready to publish. A few values use the placeholder `OWNER` because
the GitHub owner/repo was not decided yet. Do the find-and-replace first, then
work down the list.

## 0. Replace the `OWNER` placeholder

Pick your GitHub owner (and repo name, if not `jira-admin-mcp`) and replace
`OWNER` everywhere:

```bash
# from the repo root - macOS/Linux
grep -rl 'OWNER' . --exclude-dir=.git | xargs sed -i '' 's#OWNER#your-gh-username#g'   # macOS
# or: ... | xargs sed -i 's#OWNER#your-gh-username#g'                                   # Linux
```

Files that contain it: `README.md`, `pyproject.toml`, `server.json`,
`CONTRIBUTING.md`. (Windows: use your editor's project-wide replace.)

If you also rename the repo (e.g. to `mcp-jira-admin`), update the same files
and, if you want the PyPI/import names to match, also the `name` in
`pyproject.toml` and the package dir `jira_mcp/`.

## 1. Create the GitHub repo and push

```bash
git remote add origin https://github.com/your-gh-username/jira-admin-mcp.git
git push -u origin master   # or: main
```

CI (`.github/workflows/ci.yml`) runs lint + tests on Python 3.10-3.13 automatically.

## 2. PyPI Trusted Publishing (one time, no tokens)

1. Reserve the name `jira-admin-mcp` on <https://pypi.org> (it must be free; if
   taken, change `name` in `pyproject.toml` and the docs).
2. On PyPI: **Your projects -> jira-admin-mcp -> Publishing -> Add a pending
   publisher**:
   - Owner: `your-gh-username`
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
2. Authenticate with GitHub (this proves ownership of the `io.github.OWNER/...`
   namespace) and publish:

```bash
mcp-publisher login github
mcp-publisher publish
```

The registry verifies namespace ownership against the `mcp-name:` marker that is
already in `README.md` (it ships in the PyPI long description).

## 4. After publishing

- Confirm `uvx jira-admin-mcp` works from a clean machine.
- The README badges (PyPI version, CI) light up once the repo + first release exist.
