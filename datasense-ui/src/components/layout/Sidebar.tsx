import React, { useState } from 'react'
import { Play, ChevronDown, ChevronRight, Sparkles, AlertCircle, Wifi, WifiOff, Clapperboard, Eye, EyeOff, Settings, Mail, RotateCcw, Info } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { FileUpload } from '../upload/FileUpload'
import { relaunchOnboarding } from '../onboarding/OnboardingTooltip'
import { useAppStore } from '../../store/appStore'
import { useQCRun } from '../../hooks/useQCRun'
import { useHealth } from '../../hooks/useHealth'
import type { ProjectSummary } from '../../api/dashboard'

const GROQ_MODELS = [
  'llama-3.1-8b-instant',
  'llama-3.3-70b-versatile',
  'llama3-8b-8192',
  'gemma2-9b-it',
]

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`w-8 h-4 rounded-full transition-colors relative ${checked ? 'bg-accent' : 'bg-line'}`}
    >
      <span className={`absolute top-0.5 w-3 h-3 bg-white rounded-full transition-transform ${checked ? 'translate-x-4' : 'translate-x-0.5'}`} />
    </button>
  )
}

function Section({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-t border-line">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-muted hover:text-tx transition-colors"
      >
        <span className="uppercase tracking-wider">{title}</span>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && <div className="px-4 pb-4 space-y-3">{children}</div>}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted">{label}</p>
      {children}
    </div>
  )
}

export function Sidebar() {
  const { config, updateConfig, fileId, jobStatus, jobProgress, jobError,
          setActiveTab, openDemos, openSettings,
          theme, setTheme, accent, setAccent,
          groqApiKey, setGroqApiKey, authUser } = useAppStore()
  const qcl = useQueryClient()
  const dashSummary: ProjectSummary[] = qcl.getQueryData(['dash-summary']) ?? []
  const activeProjects = dashSummary.filter(p => p.status === 'active').length
  const totalFlagged = dashSummary.reduce((s, p) => s + (p.flagged ?? 0), 0)
  const [showKey, setShowKey] = useState(false)
  const [localKey, setLocalKey] = useState(groqApiKey)
  const [aboutOpen, setAboutOpen] = useState(false)
  const { run, isRunning, runError } = useQCRun()
  const { online, loading: healthLoading } = useHealth()

  const upd = (key: keyof typeof config, val: unknown) =>
    updateConfig({ [key]: val } as never)

  const updNested = <K extends keyof typeof config>(
    key: K,
    patch: Partial<(typeof config)[K]>,
  ) => updateConfig({ [key]: { ...(config[key] as object), ...patch } } as never)

  return (
    <aside className="w-64 shrink-0 bg-surface border-r border-line flex flex-col h-full overflow-y-auto">
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-line">
        <div className="w-7 h-7 bg-accent rounded flex items-center justify-center shrink-0">
          <span className="font-display font-extrabold text-bg text-xs">SL</span>
        </div>
        <div className="flex-1">
          <div className="font-display font-extrabold text-sm text-tx leading-none">Servalab</div>
          <div className="text-[10px] text-muted leading-none mt-0.5">QC Engine</div>
        </div>
        {/* Backend health */}
        {!healthLoading && (
          <div title={online ? 'Backend online' : 'Backend unreachable'}>
            {online
              ? <Wifi size={12} className="text-accent" />
              : <WifiOff size={12} className="text-critical animate-pulse" />
            }
          </div>
        )}
        <button
          onClick={openSettings}
          title="Settings"
          className="text-muted hover:text-tx transition-colors"
        >
          <Settings size={14} />
        </button>
      </div>

      {!online && !healthLoading && (
        <div className="px-4 py-2 bg-critical/10 border-b border-critical/30">
          <p className="text-[10px] text-critical leading-tight">Backend unreachable. Please try again shortly.</p>
        </div>
      )}

      {/* File upload */}
      <div className="px-4 py-3 border-b border-line">
        <FileUpload compact />
      </div>

      {/* QC Settings */}
      <Section title="QC Settings" defaultOpen>
        <Field label={`Missing threshold — ${(config.missing_threshold * 100).toFixed(0)}%`}>
          <input
            type="range" min={0} max={0.5} step={0.01}
            value={config.missing_threshold}
            onChange={(e) => upd('missing_threshold', parseFloat(e.target.value))}
            className="w-full"
          />
        </Field>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">Duplicate check</span>
          <Toggle
            checked={config.duplicate_check.enabled}
            onChange={(v) => updNested('duplicate_check', { enabled: v })}
          />
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">Duration check</span>
          <Toggle
            checked={config.interview_duration.enabled}
            onChange={(v) => updNested('interview_duration', { enabled: v })}
          />
        </div>

        {config.interview_duration.enabled && (
          <div className="space-y-2 pl-2 border-l border-line">
            <Field label="Duration column">
              <input
                type="text"
                value={config.interview_duration.column}
                onChange={(e) => updNested('interview_duration', { column: e.target.value })}
                className="w-full"
                placeholder="duration_minutes"
              />
            </Field>
            <div className="flex gap-2">
              <Field label="Min (min)">
                <input type="number" className="w-full" value={config.interview_duration.min_expected}
                  onChange={(e) => updNested('interview_duration', { min_expected: +e.target.value })} />
              </Field>
              <Field label="Max (min)">
                <input type="number" className="w-full" value={config.interview_duration.max_expected}
                  onChange={(e) => updNested('interview_duration', { max_expected: +e.target.value })} />
              </Field>
            </div>
          </div>
        )}
      </Section>

      {/* Interviewer checks */}
      <Section title="Interviewer Checks">
        <Field label="Interviewer column">
          <input
            type="text" className="w-full"
            value={config.interviewer_duration_check.interviewer_column}
            onChange={(e) => {
              updNested('interviewer_duration_check', { interviewer_column: e.target.value })
              updNested('interviewer_productivity_check', { interviewer_column: e.target.value })
            }}
            placeholder="interviewer_id"
          />
        </Field>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">Duration anomaly</span>
          <Toggle
            checked={config.interviewer_duration_check.enabled}
            onChange={(v) => updNested('interviewer_duration_check', { enabled: v })}
          />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">Productivity check</span>
          <Toggle
            checked={config.interviewer_productivity_check.enabled}
            onChange={(v) => updNested('interviewer_productivity_check', { enabled: v })}
          />
        </div>
      </Section>

      {/* Consent */}
      <Section title="Consent / Eligibility">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">Enable</span>
          <Toggle
            checked={config.consent_eligibility_check.enabled}
            onChange={(v) => updNested('consent_eligibility_check', { enabled: v })}
          />
        </div>
        {config.consent_eligibility_check.enabled && (
          <div className="space-y-2 pl-2 border-l border-line">
            <Field label="Screener column">
              <input type="text" className="w-full" value={config.consent_eligibility_check.screener_column}
                onChange={(e) => updNested('consent_eligibility_check', { screener_column: e.target.value })} />
            </Field>
            <Field label="Disqualify value">
              <input type="text" className="w-full" value={config.consent_eligibility_check.disqualify_value}
                onChange={(e) => updNested('consent_eligibility_check', { disqualify_value: e.target.value })} />
            </Field>
          </div>
        )}
      </Section>

      {/* Fabrication */}
      <Section title="Fabrication Detection">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">Enable</span>
          <Toggle
            checked={config.fabrication_check.enabled}
            onChange={(v) => updNested('fabrication_check', { enabled: v })}
          />
        </div>
        {config.fabrication_check.enabled && (
          <div className="space-y-2 pl-2 border-l border-line">
            <Field label="ID column">
              <input type="text" className="w-full" value={config.fabrication_check.id_column ?? ''}
                onChange={(e) => updNested('fabrication_check', { id_column: e.target.value })} />
            </Field>
          </div>
        )}
      </Section>

      {/* Verbatim */}
      <Section title="Verbatim Quality (Groq AI)">
        <p className="text-xs text-muted -mt-1">AI-powered open-text quality scoring. Set Groq API key in Settings.</p>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted flex items-center gap-1"><Sparkles size={11} />Enable</span>
          <Toggle
            checked={config.verbatim_check.enabled}
            onChange={(v) => updNested('verbatim_check', { enabled: v })}
          />
        </div>
        {config.verbatim_check.enabled && (
          <div className="space-y-2 pl-2 border-l border-line">
            <Field label="Verbatim columns (comma-separated)">
              <input
                type="text"
                className="w-full text-xs"
                value={config.verbatim_check.verbatim_columns.join(', ')}
                onChange={(e) =>
                  updNested('verbatim_check', {
                    verbatim_columns: e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="comment, feedback, open_text"
              />
            </Field>
            <Field label="Model">
              <select
                className="w-full"
                value={config.verbatim_check.model}
                onChange={(e) => updNested('verbatim_check', { model: e.target.value })}
              >
                {GROQ_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </Field>
            <Field label={`Min quality score — ${config.verbatim_check.min_score}/5`}>
              <input type="range" min={1} max={5} step={1} className="w-full"
                value={config.verbatim_check.min_score}
                onChange={(e) => updNested('verbatim_check', { min_score: +e.target.value })} />
            </Field>
            <Field label={`Sample size — ${config.verbatim_check.sample_size}`}>
              <input type="range" min={10} max={200} step={10} className="w-full"
                value={config.verbatim_check.sample_size}
                onChange={(e) => updNested('verbatim_check', { sample_size: +e.target.value })} />
            </Field>
          </div>
        )}
      </Section>

      {/* Settings */}
      <Section title="Settings">
        {/* Theme */}
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
                    : 'border-line text-muted hover:border-muted'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Accent colour */}
        <div className="space-y-1.5">
          <p className="text-xs text-muted">Accent colour</p>
          <div className="flex gap-2">
            {([
              ['emerald', '#4af0a0'],
              ['blue',    '#4a9ef0'],
              ['purple',  '#a078f0'],
              ['orange',  '#f09040'],
              ['pink',    '#f04a90'],
            ] as const).map(([name, hex]) => (
              <button
                key={name}
                title={name}
                onClick={() => setAccent(name)}
                style={{ background: hex }}
                className={`w-6 h-6 rounded-full transition-transform hover:scale-110 ${
                  accent === name ? 'ring-2 ring-offset-1 ring-offset-surface ring-white/60 scale-110' : ''
                }`}
              />
            ))}
          </div>
        </div>

        {/* Groq API key */}
        <div className="space-y-1">
          <p className="text-xs text-muted flex items-center gap-1"><Sparkles size={10} />Groq API key</p>
          <div className="flex gap-1">
            <div className="relative flex-1">
              <input
                type={showKey ? 'text' : 'password'}
                className="w-full pr-7 text-xs"
                value={localKey}
                onChange={(e) => setLocalKey(e.target.value)}
                onBlur={() => setGroqApiKey(localKey.trim())}
                placeholder="gsk_…"
              />
              <button
                onClick={() => setShowKey((s) => !s)}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted hover:text-tx"
              >
                {showKey ? <EyeOff size={10} /> : <Eye size={10} />}
              </button>
            </div>
            <button
              onClick={() => setGroqApiKey(localKey.trim())}
              className="btn-ghost text-[10px] px-2 py-1"
            >
              Save
            </button>
          </div>
        </div>

        {/* About — collapsible */}
        <div className="space-y-1.5">
          <button
            onClick={() => setAboutOpen((o) => !o)}
            className="w-full flex items-center justify-between text-xs text-muted uppercase tracking-wider hover:text-tx transition-colors"
          >
            <span className="flex items-center gap-1.5"><Info size={11} />About</span>
            {aboutOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </button>
          {aboutOpen && (
            <p className="text-xs text-muted leading-relaxed pt-1">
              Servalab is a survey QC engine for CATI research teams — detecting missing values,
              straightlining, interviewer fraud, logic violations, and more before sign-off.
            </p>
          )}
        </div>

        {/* Contact / actions */}
        <div className="space-y-1.5">
          <p className="text-xs text-muted uppercase tracking-wider">Contact</p>
          <a
            href="mailto:zivoo.ouma@outlook.com"
            className="flex items-center gap-2 text-xs text-muted hover:text-tx transition-colors"
          >
            <Mail size={11} className="text-accent shrink-0" />
            Contact developer
          </a>
          <a
            href="mailto:zivoo.ouma@outlook.com?subject=Servalab Feedback"
            className="flex items-center gap-2 text-xs text-muted hover:text-tx transition-colors"
          >
            <Mail size={11} className="text-accent shrink-0" />
            Send feedback
          </a>
          <button
            onClick={relaunchOnboarding}
            className="flex items-center gap-2 text-xs text-muted hover:text-tx transition-colors w-full"
          >
            <RotateCcw size={11} className="text-accent shrink-0" />
            Relaunch tour
          </button>
        </div>
      </Section>

      {/* Quick project stats — shown when logged in and summary is cached */}
      {authUser && dashSummary.length > 0 && (
        <div className="px-4 py-2.5 border-t border-line">
          <div className="flex items-center gap-1.5 text-[10px]">
            <span className="text-accent font-bold">{activeProjects}</span>
            <span className="text-muted">active project{activeProjects !== 1 ? 's' : ''}</span>
            <span className="text-line mx-1">·</span>
            {totalFlagged > 0 ? (
              <><span className="text-critical font-bold">{totalFlagged}</span><span className="text-muted ml-1">flagged</span></>
            ) : (
              <span className="text-accent">0 flagged</span>
            )}
          </div>
        </div>
      )}

      {/* Demos quick link */}
      <div className="px-4 py-3 border-t border-line">
        <button
          onClick={() => fileId ? setActiveTab('Demos') : openDemos()}
          className="w-full flex items-center gap-2 text-xs text-muted hover:text-tx transition-colors py-1"
        >
          <Clapperboard size={13} />
          Watch demos
        </button>
      </div>

      {/* Run button */}
      <div className="px-4 py-4 border-t border-line space-y-2">
        {isRunning && (
          <div className="w-full bg-line rounded-full h-1">
            <div className="bg-accent h-1 rounded-full transition-all" style={{ width: `${jobProgress || 20}%` }} />
          </div>
        )}
        {(runError || (jobStatus === 'failed' && jobError)) && (
          <div className="flex items-start gap-1.5 text-critical text-[10px]">
            <AlertCircle size={11} className="shrink-0 mt-0.5" />
            <span className="break-words">{runError ?? jobError}</span>
          </div>
        )}
        <button
          onClick={run}
          disabled={!fileId || isRunning || !online}
          className="btn-primary w-full flex items-center justify-center gap-2"
        >
          <Play size={14} />
          {isRunning
            ? jobStatus === 'queued' ? 'Queued…' : `Running ${jobProgress}%`
            : 'Run QC'}
        </button>
      </div>
    </aside>
  )
}
