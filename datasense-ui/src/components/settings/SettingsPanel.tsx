import React, { useState } from 'react'
import { X, ExternalLink, RotateCcw, Eye, EyeOff, CheckCircle2, AlertCircle } from 'lucide-react'
import { relaunchOnboarding } from '../onboarding/OnboardingTooltip'
import { useAppStore } from '../../store/appStore'

const APP_VERSION = '2.0.0'

const GROQ_MODELS = [
  'llama-3.1-8b-instant',
  'llama-3.3-70b-versatile',
  'mixtral-8x7b-32768',
  'gemma2-9b-it',
]

interface Props { onClose: () => void }

export function SettingsPanel({ onClose }: Props) {
  const { groqApiKey, setGroqApiKey, config, updateConfig } = useAppStore()
  const [showKey, setShowKey] = useState(false)
  const [localKey, setLocalKey] = useState(groqApiKey)

  const saveKey = () => setGroqApiKey(localKey.trim())
  const hasKey = groqApiKey.length > 0

  return (
    <div className="fixed inset-0 z-40 flex justify-end animate-fade-in">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative card w-80 h-full overflow-y-auto rounded-none border-l border-line animate-slide-up p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="font-display font-extrabold text-base">Settings</h2>
          <button onClick={onClose} className="text-muted hover:text-tx transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Groq AI */}
        <section className="space-y-3">
          <p className="label">Groq AI — Verbatim Checks</p>
          <p className="text-xs text-muted">
            Required for AI-assisted verbatim quality checks. Get a free key at{' '}
            <a href="https://console.groq.com" target="_blank" rel="noreferrer"
              className="text-accent hover:underline">
              console.groq.com
            </a>
          </p>

          <div className="flex items-center gap-2 text-xs">
            {hasKey ? (
              <><CheckCircle2 size={12} className="text-accent shrink-0" /><span className="text-accent">Personal key saved</span></>
            ) : (
              <><AlertCircle size={12} className="text-muted shrink-0" /><span className="text-muted">No personal key — server key used if available</span></>
            )}
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
              <button
                onClick={() => { setLocalKey(''); setGroqApiKey('') }}
                className="text-xs text-muted hover:text-critical transition-colors"
              >
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

        <section className="space-y-2">
          <p className="label">Appearance</p>
          <div className="flex items-center justify-between py-2 px-3 bg-surface2 rounded border border-line">
            <span className="text-sm">Theme</span>
            <span className="text-sm text-muted">Dark (only)</span>
          </div>
        </section>

        <section className="space-y-2">
          <p className="label">About</p>
          <div className="py-2 px-3 bg-surface2 rounded border border-line space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-muted">Version</span>
              <span className="text-accent">{APP_VERSION}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted">Engine</span>
              <span>FastAPI + Python</span>
            </div>
          </div>
        </section>

        <section className="space-y-2">
          <p className="label">Onboarding</p>
          <button
            onClick={relaunchOnboarding}
            className="w-full flex items-center gap-2 btn-ghost text-sm justify-center"
          >
            <RotateCcw size={14} />
            Relaunch tour
          </button>
        </section>

        <section className="space-y-2">
          <p className="label">Feedback</p>
          <a
            href="https://github.com/anthropics/claude-code/issues"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-sm text-muted hover:text-tx transition-colors"
          >
            <ExternalLink size={14} />
            Report an issue
          </a>
        </section>
      </div>
    </div>
  )
}
