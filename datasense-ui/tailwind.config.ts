import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:           'rgb(var(--c-bg) / <alpha-value>)',
        surface:      'rgb(var(--c-surface) / <alpha-value>)',
        surface2:     'rgb(var(--c-surface2) / <alpha-value>)',
        line:         'rgb(var(--c-line) / <alpha-value>)',
        accent:       'rgb(var(--c-accent) / <alpha-value>)',
        'accent-dim': 'rgb(var(--c-accent-dim) / <alpha-value>)',
        tx:           'rgb(var(--c-tx) / <alpha-value>)',
        muted:        'rgb(var(--c-muted) / <alpha-value>)',
        critical:     '#f04a6a',
        warning:      '#f0c04a',
        info:         '#4a9ef0',
      },
      fontFamily: {
        mono:    ['"DM Mono"', 'ui-monospace', 'monospace'],
        display: ['Syne', 'ui-sans-serif', 'sans-serif'],
      },
      fontWeight: {
        '700': '700',
        '800': '800',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.25s ease-out',
      },
      keyframes: {
        fadeIn:  { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}

export default config
