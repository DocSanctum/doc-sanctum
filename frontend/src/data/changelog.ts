export interface ChangelogEntry {
  version: string
  date: string
  changes: string[]
}

export const changelog: ChangelogEntry[] = [
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
