import React from 'react'
import ReactDOM from 'react-dom/client'
import { Analytics } from '@vercel/analytics/react'
import App from './App'
import './index.css'

// Apply saved theme/accent before first render to avoid flash
;(function () {
  const ACCENTS: Record<string, [string, string]> = {
    emerald: ['74 240 160', '42 184 112'],
    blue:    ['74 158 240', '42 110 200'],
    purple:  ['160 120 240', '110 80 200'],
    orange:  ['240 144 64',  '200 100 24'],
    pink:    ['240 74 144',  '200 34 104'],
  }
  const t = localStorage.getItem('ds_theme') ?? 'dark'
  const a = localStorage.getItem('ds_accent') ?? 'emerald'
  document.documentElement.setAttribute('data-theme', t)
  const [acc, dim] = ACCENTS[a] ?? ACCENTS.emerald
  document.documentElement.style.setProperty('--c-accent', acc)
  document.documentElement.style.setProperty('--c-accent-dim', dim)
})()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <Analytics />
  </React.StrictMode>,
)
