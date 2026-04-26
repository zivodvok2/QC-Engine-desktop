import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#0b0c0f',
        surface:  '#111318',
        surface2: '#181b22',
        line:     '#1f2330',
        accent:   '#4af0a0',
        'accent-dim': '#2ab870',
        tx:       '#e8eaf2',
        muted:    '#8b90a8',
        critical: '#f04a6a',
        warning:  '#f0c04a',
        info:     '#4a9ef0',
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
