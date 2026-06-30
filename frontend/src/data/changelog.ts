export interface ChangelogEntry {
  version: string
  date: string
  changes: string[]
}

export const changelog: ChangelogEntry[] = [
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
