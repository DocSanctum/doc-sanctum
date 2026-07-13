export interface ChangelogEntry {
  version: string
  date: string
  changes: string[]
}

export const changelog: ChangelogEntry[] = [
  {
    version: '0.10.0',
    date: '2026-07-14',
    changes: [
      'Standalone deployments now persist the vector index and its change-tracking cache across backend restarts, instead of re-embedding every document on every restart',
      'Backend automatically reconnects to the vector store in the background if it was unreachable at startup, instead of requiring a restart once it comes back up',
      'Sources can now carry their own encrypted GitHub/GitLab access token instead of relying only on the server-wide token',
      'Perf: source sync fetches documents concurrently, cutting sync time roughly 6x on large sources',
      'Settings: option toggles (language, theme, font size, line numbers) restyled as a single segmented control',
      'Fix: sources with partial indexing failures (e.g. a rate-limited fetch) now show a distinct "partial" status instead of silently appearing fully indexed',
      'Fix: transient upstream 5xx errors while fetching large repository trees no longer abort the whole sync',
      'Fix: code block line numbers now stay aligned with the rendered code',
      'Fix: wide tables now use the app’s themed scrollbar instead of the browser default',
    ],
  },
  {
    version: '0.9.0',
    date: '2026-07-11',
    changes: [
      'CI: automated issue triage — new issues get an analysis comment pointing to likely-relevant code',
      'CI: dependency audit now attempts automated fixes for vulnerabilities and opens a PR when safe',
      'CI: opt-in PR review — comment "@claude review" on a PR to get a findings comment',
    ],
  },
  {
    version: '0.8.0',
    date: '2026-07-09',
    changes: [
      'Docker: split compose into dev/prod stacks; start.sh defaults to prod, --dev is opt-in',
      'Docker: healthchecks, resource limits (BACKEND_CPU_LIMIT/BACKEND_MEMORY_LIMIT), and log rotation for the prod stack',
      'Docker: optional corporate CA certificate support, for builds and runtime requests behind a TLS-intercepting proxy',
      'Docker: bind-mounted dev containers for real hot reload (uvicorn --reload, Vite HMR)',
      'Settings: per-source index status (indexing / complete / failed) shown in the source list',
      'Markdown viewer: better readability for Korean text and wide tables in split-view panes',
      'New top-level README covering purpose, features, setup, and contributing',
      'Fix: search shortcut hint now shows the correct key for the user’s platform instead of always showing both',
      'Fix: frontend healthcheck failing under musl (resolves localhost to ::1 first)',
    ],
  },
  {
    version: '0.7.0',
    date: '2026-07-09',
    changes: [
      'Global keyword search command palette, with shortcut hint and per-pane open targets',
      'Split-view multi-pane markdown viewer, with a per-pane color picker matching tree hover and reading-progress highlighting',
      'i18n support: Korean/English UI, defaulting by IP',
      'GitLab added as a source type; HTTP/localhost source types disabled',
      'Users can edit a registered source’s name and pick an emoji icon',
      'Table of contents panel can now be collapsed',
      'Perf: skip re-downloading unchanged GitHub files using their blob sha',
      'Fix: GitHub token auth scheme, Enterprise URL support, and Contents API for file reads (raw-domain guessing was unreliable)',
      'Fix: source tree requests no longer hard-503 or race the background poller; remote files now index in the background',
      'Fix: code highlight theme now follows the app theme by default',
      'Fix: reading progress bar getting stuck / never reaching 100% in Safari, and a phantom scrollbar in the viewer',
      'Fix: missing icon column backfilled on existing source databases',
      'Fix: light-theme code blocks now use a light gray background instead of white',
      'Fix: fenced code blocks were silently double-wrapped in an extra dark <pre>, which also broke the data-line attribute used to scroll a search result into view',
    ],
  },
  {
    version: '0.6.0',
    date: '2026-07-04',
    changes: [
      'Semantic search and remote-source caching added to the MCP server',
      'Scaleout deployment mode: multiple backend replicas sharing one persistent vector index',
      'Backend port published as a range so scaleout replicas don’t clash',
      'Optional corporate proxy support for docker compose builds and outbound requests',
      'start.sh / stop.sh wrapper scripts for docker compose',
      'Markdown viewer: table of contents, code copy button, permalink deep links, breadcrumb, reading progress bar',
      'Confirm dialog before deleting a registered source',
      'Fix: embedding model cache is now reachable when the container’s HOME is remapped to the host user’s home directory, which was causing source registration to fail with "Local embedding engine is unavailable"',
    ],
  },
  {
    version: '0.5.0',
    date: '2026-07-01',
    changes: [
      'Settings panel: app theme and font size buttons right-aligned',
      'Settings panel: code theme changed to vertical list with checkmark indicator',
      'Settings panel: polling section always visible with note for GitHub/HTTP sources; local sources shown as disabled',
      'Changelog: show recent 5 entries with link to full history page',
      'Fix CI: pytest path resolution and ruff lint/format errors',
    ],
  },
  {
    version: '0.4.0',
    date: '2026-07-01',
    changes: [
      'MCP server status panel in settings (enable/disable toggle, SSE and Streamable HTTP endpoints, tool list)',
      'MCP enable/disable state persisted in SQLite — survives container restarts',
      'Larger DocSanctum title in settings panel',
    ],
  },
  {
    version: '0.3.0',
    date: '2026-07-01',
    changes: [
      'Version history and changelog viewer in settings panel',
      'Editable polling interval for remote sources in settings panel',
      'Fix font size (sm/base/lg) not applying due to Tailwind purge',
    ],
  },
  {
    version: '0.2.0',
    date: '2026-07-01',
    changes: [
      'Resizable sidebar (drag to 180–480px)',
      'Settings as a full panel in the main area (replaced popup modal)',
      'Light / Dark app theme toggle',
      'Improved Markdown rendering (@tailwindcss/typography, highlight.js themes)',
      'Code highlight theme selector (4 dark / 3 light themes)',
      'Open external URLs in a new tab',
      'Show source path below name in sidebar',
      'Replace emoji status icons with CSS dots',
    ],
  },
  {
    version: '0.1.0',
    date: '2026-06-30',
    changes: [
      'Initial release',
      'MCP server with SSE transport (list / read / search tools)',
      'Markdown file viewer',
      'Local folder / GitHub / HTTP / Localhost source support',
      'File tree navigation',
      'Optional GitHub API token support',
    ],
  },
]
