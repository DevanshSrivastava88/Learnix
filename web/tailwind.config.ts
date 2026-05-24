import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0f0f11',
          secondary: '#18181b',
          tertiary: '#1f1f23',
          elevated: '#27272a',
        },
        border: {
          subtle: '#2a2a2e',
          default: '#3f3f46',
        },
        text: {
          primary: '#fafafa',
          secondary: '#a1a1aa',
          muted: '#71717a',
        },
        status: {
          passed: '#22c55e',
          'passed-bg': '#14532d',
          'in-progress': '#eab308',
          'in-progress-bg': '#422006',
          'needs-revision': '#f97316',
          'needs-revision-bg': '#431407',
          'not-started': '#71717a',
          'not-started-bg': '#27272a',
        },
        accent: '#6366f1',
        'accent-hover': '#4f46e5',
      },
    },
  },
  plugins: [],
}

export default config
