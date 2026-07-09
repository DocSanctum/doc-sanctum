# DocSanctum

DocSanctum pulls markdown documentation scattered across a local folder, GitHub repositories, and GitLab projects into one place you can actually browse and search. Point it at where your docs live, and it builds a single tree you can read, search, and — if you use AI coding assistants — query directly through a built-in MCP server.

It's meant to run on your own machine or your team's own server. Nothing leaves it unless you tell it to.

## Why you might want this

Most teams end up with documentation spread across a handful of repos, a local notes folder, maybe a wiki nobody updates. DocSanctum doesn't try to replace any of that — it just gives you one viewer and one search box on top of what already exists.

- **One tree, many sources.** Register a local folder, a GitHub repo, or a GitLab project, and they all show up side by side in the same file tree.
- **Search that actually finds things.** A keyword search command palette for exact matches, plus semantic search for when you remember what a doc was about but not the words it used.
- **A reading experience worth using.** Split-view panes so you can read two documents at once, a table of contents, reading progress, code block copy buttons, permalinks, dark mode.
- **MCP built in, not bolted on.** The backend exposes `list_documents`, `read_document`, `search_documents`, and `semantic_search_documents` as MCP tools, so Claude or any other MCP client can answer questions using your actual docs instead of guessing.
- **Self-hosted by default.** Runs entirely in Docker containers on infrastructure you control. Optional GitHub/GitLab tokens are only used to read the repos you register.
- **English and Korean UI**, with more likely to come.

## Getting started

You need Docker and Docker Compose. Nothing else has to be installed on the host — the app, its embedding model, and its vector store all run inside containers.

```bash
git clone https://github.com/DocSanctum/doc-sanctum.git
cd doc-sanctum
cp .env.example .env
./start.sh
```

The first run builds the images, which takes a few minutes (it also downloads a small local embedding model so semantic search works offline afterward). Once it's up:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

From there, use the "Add source" button in the sidebar to register a local folder, a GitHub repo (`owner/repo`), or a GitLab project (`group/project`). Local folders index immediately; remote repos sync in the background and you'll see their status change from "syncing" to "active".

To stop everything:

```bash
./stop.sh
```

Re-running `./start.sh` picks up code changes automatically — it rebuilds only when the current commit differs from what it last built, or when you pass `--build` to force it.

### Configuration

Copy `.env.example` to `.env` and adjust as needed. The defaults work for a single-machine setup; the file documents each option inline, including:

- `GITHUB_TOKEN` / `GITLAB_TOKEN` — needed for private repos, and to raise GitHub's API rate limit from 60 to 5000 requests/hour.
- `BACKEND_PORT`, `FRONTEND_PORT` — change these if the defaults are already taken on your machine.
- `BACKEND_CPU_LIMIT` / `BACKEND_MEMORY_LIMIT` — cap the backend's CPU/memory in the production stack, so a large indexing job can't starve the rest of the machine.
- `HTTP_PROXY` / `HTTPS_PROXY` — for building and running behind a corporate proxy, see below.

## Running behind a corporate proxy

If your network only reaches the internet through a proxy, set these in `.env` before building:

```bash
HTTP_PROXY=http://proxy.internal.example.com:8080
HTTPS_PROXY=http://proxy.internal.example.com:8080
NO_PROXY=localhost,127.0.0.1
```

They're used in two places:

- **At build time** — `pip install`, `npm install`, and the embedding model download all go through the proxy.
- **At runtime** — the backend's outbound requests to remote GitHub/GitLab/HTTP sources go through it too.

Because these are baked in as build args, changing them in `.env` only takes effect on the next rebuild: run `./start.sh --build` (or `./start.sh --dev --build`) after editing them.

### Corporate CA certificates (TLS-intercepting proxies)

Some corporate proxies intercept HTTPS and re-sign traffic with an internal CA. If that's your setup, `pip install`, `npm install`, and the backend's own outbound requests will all fail certificate verification until that CA is trusted — proxy settings alone don't fix this.

To trust it, drop your PEM-encoded root/intermediate certificate(s) as `.crt` files into these gitignored directories before building, then rebuild:

```bash
cp your-corporate-ca.crt backend/certs/
cp your-corporate-ca.crt frontend/certs/
./start.sh --build
```

Leaving both directories empty is a no-op — nothing else changes. No `.env` variable is needed for this; it's picked up directly from the files at build time.

## Using it from Claude or another MCP client

DocSanctum runs its MCP server inside the same backend process, mounted at:

- `http://<host>:8000/mcp-http` — streamable HTTP transport (MCP 1.x, recommended)
- `http://<host>:8000/mcp` — SSE transport (legacy, kept for older clients)

Point your MCP client at whichever one it supports, and it can list your registered documents, read one, or search across all of them — keyword or semantic — without you having to paste file contents into a prompt by hand.

## Contributing

Contributions are welcome — bug reports, fixes, and features alike. A few things that make this easier:

1. Run the dev stack instead of the production one — it runs the Vite dev server and `uvicorn --reload` against your working tree (bind-mounted into the containers), so edits show up immediately without a rebuild:

   ```bash
   ./start.sh --dev
   ```

   You only need `./start.sh --dev --build` again if you change a dependency (`requirements.txt`/`package.json`), since those are installed at image build time.

2. Before opening a PR, run the checks CI runs. These are the same commands as `.github/workflows/backend-ci.yml` and `frontend-ci.yml`:

   ```bash
   # Backend (from the repo root, with backend/requirements-dev.txt installed)
   ruff check backend/
   ruff format --check backend/
   mypy backend/app --ignore-missing-imports
   pytest backend/tests/ -v

   # Frontend (from frontend/)
   npm run lint
   npm run typecheck
   npm run test
   npm run build
   ```

3. Open a pull request against `main` with a clear description of what changed and why. If it fixes a bug, a short repro or failing test helps a lot.

If you're not sure whether something is worth a PR, opening an issue first is always fine.

## License

DocSanctum is licensed under the [GNU Affero General Public License v3.0](LICENSE).
