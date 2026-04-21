import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'LocalLens',
  description: 'Semantic file search engine for AI agents. 100% offline.',
  base: '/locallens/',
  appearance: false,

  head: [
    ['link', { rel: 'icon', href: '/locallens/logo.svg' }],
  ],

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'LocalLens',

    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'API Reference', link: '/api/python-api' },
      { text: 'CLI', link: '/cli/commands' },
      { text: 'MCP', link: '/mcp/setup' },
      { text: 'GitHub', link: 'https://github.com/mahimairaja/locallens' },
      { text: 'PyPI', link: 'https://pypi.org/project/locallens/' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Guide',
          items: [
            { text: 'Getting Started', link: '/guide/getting-started' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Quick Start', link: '/guide/quick-start' },
            { text: 'Architecture', link: '/guide/architecture' },
            { text: 'Configuration', link: '/guide/configuration' },
            { text: 'Performance', link: '/guide/performance' },
            { text: 'Supported File Types', link: '/guide/file-types' },
            { text: 'FAQ', link: '/guide/faq' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Python API', link: '/api/python-api' },
            { text: 'Data Classes', link: '/api/data-classes' },
            { text: 'Exceptions', link: '/api/exceptions' },
            { text: 'Examples', link: '/api/examples' },
          ],
        },
      ],
      '/cli/': [
        {
          text: 'CLI Reference',
          items: [
            { text: 'Commands Overview', link: '/cli/commands' },
            { text: 'index', link: '/cli/index-cmd' },
            { text: 'search', link: '/cli/search-cmd' },
            { text: 'ask', link: '/cli/ask-cmd' },
            { text: 'stats', link: '/cli/stats-cmd' },
            { text: 'doctor', link: '/cli/doctor-cmd' },
            { text: 'serve', link: '/cli/serve-cmd' },
            { text: 'JSON Output', link: '/cli/json-output' },
          ],
        },
      ],
      '/mcp/': [
        {
          text: 'MCP Server',
          items: [
            { text: 'Setup', link: '/mcp/setup' },
            { text: 'Tools Reference', link: '/mcp/tools-reference' },
            { text: 'Claude Code Integration', link: '/mcp/claude-code' },
            { text: 'Claude Desktop Integration', link: '/mcp/claude-desktop' },
            { text: 'Custom MCP Clients', link: '/mcp/custom-clients' },
          ],
        },
      ],
      '/dashboard/': [
        {
          text: 'Web Dashboard',
          items: [
            { text: 'Setup', link: '/dashboard/setup' },
            { text: 'Dashboard', link: '/dashboard/overview' },
            { text: 'Search', link: '/dashboard/search' },
            { text: 'Ask', link: '/dashboard/ask' },
            { text: 'Voice', link: '/dashboard/voice' },
          ],
        },
      ],
    },

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Built with VitePress | Mahimai AI',
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/mahimairaja/locallens' },
    ],
  },
})
