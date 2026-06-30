/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:           'rgb(var(--c-bg)         / <alpha-value>)',
        surface:      'rgb(var(--c-surface)     / <alpha-value>)',
        surface2:     'rgb(var(--c-surface2)    / <alpha-value>)',
        line:         'rgb(var(--c-line)        / <alpha-value>)',
        accent:       'rgb(var(--c-accent)      / <alpha-value>)',
        'accent-dim': 'rgb(var(--c-accent-dim)  / <alpha-value>)',
        tx:           'rgb(var(--c-tx)          / <alpha-value>)',
        muted:        'rgb(var(--c-muted)       / <alpha-value>)',
        navy:         'rgb(var(--c-navy)        / <alpha-value>)',
        critical:     '#1B2A4A',
        warning:      '#00B5A3',
        info:         '#1B2A4A',
      },
      fontFamily: {
        sans:    ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono:    ['"DM Mono"', 'ui-monospace', 'monospace'],
        display: ['Inter', 'ui-sans-serif', 'sans-serif'],
      },
      animation: {
        'fade-in':  'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.22s ease-out',
      },
      keyframes: {
        fadeIn:  { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
      boxShadow: {
        card:    '0 2px 8px 0 rgb(27 42 74 / 0.07), 0 1px 2px 0 rgb(27 42 74 / 0.04)',
        'card-md': '0 6px 16px 0 rgb(27 42 74 / 0.10), 0 2px 4px 0 rgb(27 42 74 / 0.05)',
        'card-lg': '0 12px 32px 0 rgb(27 42 74 / 0.13), 0 4px 8px 0 rgb(27 42 74 / 0.06)',
      },
    },
  },
  plugins: [],
}
