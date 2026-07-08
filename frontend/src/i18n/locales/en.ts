export const en = {
  common: {
    cancel: 'Cancel',
    save: 'Save',
    saving: 'Saving...',
    delete: 'Delete',
    deleting: 'Deleting...',
    register: 'Register',
    registering: 'Registering...',
    loading: 'Loading...',
    retry: 'Retry',
    current: 'Current',
    optional: '(optional)',
    copy: 'Copy',
    copied: 'Copied',
    copyFailed: 'Copy failed',
  },
  app: {
    addSource: 'Add source',
    settings: 'Settings',
    openSearch: 'Search ({shortcut})',
  },
  sidebar: {
    sourceList: {
      loading: 'Loading...',
      loadError: 'Failed to load sources',
      editSource: 'Edit source info',
    },
    fileTree: {
      loading: 'Loading file list...',
      loadError: 'Failed to load file list.',
      empty: 'No markdown files',
    },
    treeNode: {
      paneOpen: 'Open in pane {paneId}',
      paneOpenActive: 'Open in pane {paneId} (active)',
    },
    addSourceModal: {
      title: 'Add source path',
      name: 'Name',
      icon: 'Icon',
      type: 'Type',
      typeLocal: 'Local folder',
      typeGithub: 'GitHub repository',
      typeGitlab: 'GitLab repository',
      path: 'Path / URL',
      pollInterval: 'Polling interval (sec)',
      indexingNotice:
        'Checking the document list. It will appear in the list right after registering, while search indexing continues in the background.',
      registerFailed: 'Registration failed',
    },
    editSourceModal: {
      title: 'Edit source info',
      name: 'Name',
      saveFailed: 'Save failed',
    },
    confirmDeleteModal: {
      title: 'Delete source',
      body: 'Are you sure you want to delete {name}? Indexed data will be removed as well and this cannot be undone.',
    },
  },
  viewer: {
    emptyState: 'Select a markdown file on the left',
    breadcrumb: {
      ariaLabel: 'Document path',
    },
    markdownViewer: {
      loading: 'Loading file...',
      notFound: 'Document not found',
    },
    readingProgress: {
      backToTop: 'Back to top',
    },
    toc: {
      ariaLabel: 'Table of contents',
      title: 'Contents',
      expand: 'Expand table of contents',
      collapse: 'Collapse table of contents',
    },
    pane: {
      changeColorTitle: 'Change pane {paneId} color',
      splitView: 'Split view',
      splitViewTitle: 'Enable split view',
      closeTitle: 'Close pane',
    },
    markdown: {
      copyCode: 'Copy code',
    },
  },
  settings: {
    title: 'Settings',
    language: {
      label: 'Language',
      korean: '한국어',
      english: 'English',
    },
    theme: {
      label: 'App theme',
      dark: 'Dark',
      light: 'Light',
    },
    fontSize: {
      label: 'Viewer font size',
      small: 'S',
      medium: 'M',
      large: 'L',
    },
    codeTheme: {
      label: 'Code highlight theme',
      dark: 'Dark',
      light: 'Light',
    },
    polling: {
      label: 'Source polling interval',
      description:
        'Applies only to GitHub, HTTP, and Localhost sources. Local sources are reflected in real time via filesystem watching.',
      empty: 'No registered sources.',
      realtime: 'Real-time detection',
      seconds: 'sec',
    },
    mcp: {
      label: 'MCP Server',
      enabled: 'Enabled',
      disabled: 'Disabled',
      enableBtn: 'Enable',
      disableBtn: 'Disable',
      tools: 'Tools ({count})',
    },
    changelog: {
      viewAll: 'View full history →',
      back: '← Back',
      allHistory: 'Full Changelog',
    },
  },
  search: {
    ariaLabel: 'Global search',
    placeholder: 'Search across all sources...',
    shortcutHint: '{shortcut} to open · Esc to close',
    noSources: 'No registered sources to search',
    noResults: 'No results found',
    loading: 'Searching...',
    moreMatches: 'More matches in this document',
    warning: '{name}: {message}',
    openInPane: 'Open in pane {paneId}',
    openInLabel: 'Open in:',
    modeKeyword: 'Keyword',
    modeSemantic: 'Semantic',
    tabSwitchHint: 'Tab to switch to {mode} mode',
    engineUnavailable: 'Semantic search is unavailable right now (local embedding engine is not running).',
  },
}

export type MessageSchema = typeof en
