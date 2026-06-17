import React, { useState } from 'react'
import { X, ChevronDown, ChevronRight, RotateCcw, Eye, EyeOff, CheckCircle2, AlertCircle, Mail, MessageSquare } from 'lucide-react'
import { relaunchOnboarding } from '../onboarding/OnboardingTooltip'
import { useAppStore } from '../../store/appStore'

const APP_VERSION = '2.0.0'

const GROQ_MODELS = [
  'llama-3.1-8b-instant',
  'llama-3.3-70b-versatile',
  'llama3-8b-8192',
  'gemma2-9b-it',
]

const ACCENT_OPTIONS: { name: 'emerald' | 'blue' | 'purple' | 'orange' | 'pink'; hex: string }[] = [
  { name: 'emerald', hex: '#4af0a0' },
  { name: 'blue',    hex: '#4a9ef0' },
  { name: 'purple',  hex: '#a078f0' },
  { name: 'orange',  hex: '#f09040' },
  { name: 'pink',    hex: '#f04a90' },
]

function Accordion({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <section className="border border-line rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2.5 text-xs text-muted hover:text-tx hover:bg-surface2 transition-colors uppercase tracking-wider"
      >
        <span>{label}</span>
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      </button>
      {open && <div className="px-3 pb-3 pt-1 space-y-3 border-t border-line">{children}</div>}
    </section>
  )
}

interface Props { onClose: () => void }

export function SettingsPanel({ onClose }: Props) {
  const { groqApiKey, setGroqApiKey, config, updateConfig, theme, setTheme, accent, setAccent } = useAppStore()
  const [showKey, setShowKey] = useState(false)
  const [localKey, setLocalKey] = useState(groqApiKey)

  const saveKey = () => setGroqApiKey(localKey.trim())
  const hasKey = groqApiKey.length > 0

  return (
    <div className="fixed inset-0 z-40 flex justify-end animate-fade-in">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative card w-80 h-full overflow-y-auto rounded-none border-l border-line animate-slide-up p-6 space-y-4">

        <div className="flex items-center justify-between mb-2">
          <h2 className="font-display font-extrabold text-base">Settings</h2>
          <button onClick={onClose} className="text-muted hover:text-tx transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Appearance — always open */}
        <section className="space-y-4">
          <p className="label">Appearance</p>
          <div className="space-y-1.5">
            <p className="text-xs text-muted">Theme</p>
            <div className="flex gap-1.5">
              {(['dark', 'light', 'midnight'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTheme(t)}
                  className={`flex-1 py-1.5 text-[10px] rounded border capitalize transition-colors ${
                    theme === t
                      ? 'border-accent text-accent bg-accent/10'
                      : 'border-line text-muted hover:border-muted hover:text-tx'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            <p className="text-xs text-muted">Accent colour</p>
            <div className="flex gap-2.5 items-center">
              {ACCENT_OPTIONS.map(({ name, hex }) => (
                <button
                  key={name}
                  title={name}
                  onClick={() => setAccent(name)}
                  style={{ background: hex }}
                  className={`w-6 h-6 rounded-full transition-transform hover:scale-110 ${
                    accent === name ? 'ring-2 ring-offset-2 ring-offset-surface ring-white/50 scale-110' : ''
                  }`}
                />
              ))}
            </div>
          </div>
        </section>

        {/* Groq AI — always open */}
        <section className="space-y-3">
          <p className="label">Groq AI — Verbatim Checks</p>
          <p className="text-xs text-muted">
            Required for AI-assisted verbatim quality checks. Get a free key at{' '}
            <a href="https://console.groq.com" target="_blank" rel="noreferrer" className="text-accent hover:underline">
              console.groq.com
            </a>
          </p>
          <div className="flex items-center gap-2 text-xs">
            {hasKey
              ? <><CheckCircle2 size={12} className="text-accent shrink-0" /><span className="text-accent">Personal key saved</span></>
              : <><AlertCircle size={12} className="text-muted shrink-0" /><span className="text-muted">No personal key — server key used if available</span></>
            }
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">API Key</p>
            <div className="flex gap-1.5">
              <div className="relative flex-1">
                <input
                  type={showKey ? 'text' : 'password'}
                  className="w-full pr-8"
                  value={localKey}
                  onChange={(e) => setLocalKey(e.target.value)}
                  onBlur={saveKey}
                  placeholder="gsk_…"
                />
                <button
                  onClick={() => setShowKey((s) => !s)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-tx"
                >
                  {showKey ? <EyeOff size={12} /> : <Eye size={12} />}
                </button>
              </div>
              <button onClick={saveKey} className="btn-ghost text-xs px-3">Save</button>
            </div>
            {localKey && (
              <button onClick={() => { setLocalKey(''); setGroqApiKey('') }} className="text-xs text-muted hover:text-critical transition-colors">
                Clear key
              </button>
            )}
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">Model</p>
            <select
              className="w-full"
              value={config.verbatim_check.model}
              onChange={(e) => updateConfig({ verbatim_check: { ...config.verbatim_check, model: e.target.value } })}
            >
              {GROQ_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        </section>

        {/* Onboarding */}
        <section className="space-y-2">
          <p className="label">Onboarding</p>
          <button onClick={relaunchOnboarding} className="w-full flex items-center gap-2 btn-ghost text-sm justify-center">
            <RotateCcw size={14} />
            Relaunch tour
          </button>
        </section>

        {/* About — collapsible */}
        <Accordion label="About">
          <div className="flex items-center gap-2 pt-1">
            <div className="w-7 h-7 bg-accent rounded flex items-center justify-center shrink-0">
              <span className="font-display font-extrabold text-bg text-xs">SL</span>
            </div>
            <div>
              <p className="text-sm font-display font-bold text-tx">Servalab</p>
              <p className="text-[10px] text-muted">v{APP_VERSION}</p>
            </div>
          </div>
          <p className="text-xs text-muted leading-relaxed">
            Servalab is a survey quality control engine built for CATI research teams.
            It helps field managers detect data quality issues — including missing values,
            straightlining, interviewer fraud, logic violations, and more — before data
            is signed off for analysis.
          </p>
          <p className="text-xs text-muted leading-relaxed">
            Upload a CSV or Excel file, configure your checks, and get a full flagged
            report in seconds. Supports multi-wave comparison, quota tracking, verbatim
            AI scoring, and interviewer risk profiling.
          </p>
        </Accordion>

        {/* Contact — collapsible, no visible email */}
        <Accordion label="Contact Developer">
          <a
            href="mailto:zivoo.ouma@outlook.com"
            className="w-full flex items-center gap-2 btn-ghost text-sm justify-center"
          >
            <Mail size={14} />
            Send a message
          </a>
          <a
            href="mailto:zivoo.ouma@outlook.com?subject=Servalab Feedback"
            className="w-full flex items-center gap-2 btn-ghost text-sm justify-center"
          >
            <MessageSquare size={14} />
            Send feedback
          </a>
        </Accordion>

      </div>
    </div>
  )
}
