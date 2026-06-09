import React, { useRef } from 'react'
import { Plus, Trash2, Play, AlertCircle, Sparkles, ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react'
import { ColumnSelector } from '../columns/ColumnSelector'
import { validateLogic } from '../../api/eda'
import { nlToRule } from '../../api/ai'
import { addSupplemental } from '../../api/qc'
import { useAppStore } from '../../store/appStore'
import type { CheckSet, RuleBuilderState } from '../../store/appStore'
import type { LogicRule } from '../../types'

const OPERATORS = ['==', '!=', '>', '<', '>=', '<=', 'is_null', 'not_null', 'in_list', 'not_in_list']
const NEED_VALUE = new Set(['==', '!=', '>', '<', '>=', '<=', 'in_list', 'not_in_list'])

let _counter = 100
const nextId = () => ++_counter

const newIfCond = () => ({ id: nextId(), col: '', op: '==', val: '', connector: 'AND' as const })

const newRule = (): RuleBuilderState => ({
  id: nextId(),
  if_conditions: [newIfCond()],
  then_cols: [],
  then_op: 'is_null',
  then_val: '',
  description: '',
})

const newCheckSet = (idx: number): CheckSet => ({
  id: nextId(),
  name: `Check Set ${idx}`,
  rules: [newRule()],
  result: null,
  isRunning: false,
})

function buildApiRule(r: RuleBuilderState): LogicRule {
  return {
    description: r.description || `Rule ${r.id}`,
    if_conditions: r.if_conditions
      .filter((c) => c.col)
      .map((c) => ({
        column: c.col,
        operator: c.op,
        value: NEED_VALUE.has(c.op) ? c.val : undefined,
        connector: c.connector ?? 'AND',
      })),
    then_conditions: r.then_cols.map((col) => ({
      column: col,
      operator: r.then_op,
      value: NEED_VALUE.has(r.then_op) ? r.then_val : undefined,
    })),
  }
}

// ── NL helper ────────────────────────────────────────────────────────────────

function NlPanel({ groqApiKey }: { groqApiKey: string }) {
  const [open, setOpen] = React.useState(false)
  const [text, setText] = React.useState('')
  const [result, setResult] = React.useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')

  const convert = async () => {
    if (!text.trim() || !groqApiKey) return
    setLoading(true); setError('')
    try { setResult((await nlToRule(text, groqApiKey)).rule) }
    catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  return (
    <div className="card border-line">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-xs text-muted hover:text-tx transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Sparkles size={11} className="text-accent" /> Describe in plain English (AI → rule)
        </span>
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-line pt-3">
          <p className="text-[10px] text-muted">
            Describe what the rule should check and Groq AI will convert it to a QC rule.
            {!groqApiKey && <span className="text-warning ml-1">Set Groq API key in Settings first.</span>}
          </p>
          <textarea
            className="w-full h-20 text-xs bg-surface2 border border-line rounded p-2 resize-none text-tx placeholder-muted"
            placeholder="e.g. If age is under 18 and gender is Female, score on column Q1 should be 1 or 2"
            value={text} onChange={(e) => setText(e.target.value)}
          />
          <button onClick={convert} disabled={!text.trim() || !groqApiKey || loading}
            className="btn-primary flex items-center gap-1.5 text-xs">
            <Sparkles size={11} />{loading ? 'Converting…' : 'Convert to rule'}
          </button>
          {error && <p className="text-xs text-critical">{error}</p>}
          {result && (
            <div className="space-y-1">
              <p className="text-[10px] text-muted">Generated rule JSON:</p>
              <pre className="text-[10px] bg-surface2 border border-line rounded p-2 overflow-auto text-accent">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Rule card with multiple IF conditions ─────────────────────────────────────

function RuleCard({
  rule, idx, onUpdate, onRemove,
}: {
  rule: RuleBuilderState
  idx: number
  onUpdate: (patch: Partial<RuleBuilderState>) => void
  onRemove: () => void
}) {
  const updateIf = (condId: number, patch: Partial<typeof rule.if_conditions[0]>) =>
    onUpdate({ if_conditions: rule.if_conditions.map((c) => (c.id === condId ? { ...c, ...patch } : c)) })

  const removeIf = (condId: number) =>
    onUpdate({ if_conditions: rule.if_conditions.filter((c) => c.id !== condId) })

  return (
    <div className="card p-4 space-y-4 border border-line/60">
      <div className="flex items-center justify-between">
        <span className="label">Rule {idx + 1}</span>
        <button onClick={onRemove} className="text-muted hover:text-critical transition-colors">
          <Trash2 size={14} />
        </button>
      </div>

      <div className="space-y-1">
        <p className="text-xs text-muted">Description (optional)</p>
        <input type="text" className="w-full" value={rule.description}
          onChange={(e) => onUpdate({ description: e.target.value })}
          placeholder="e.g. Under-18 females must not have specific scores" />
      </div>

      {/* IF conditions — ANDed together */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="label text-info">IF (all must be true — AND)</p>
          <button
            onClick={() => onUpdate({ if_conditions: [...rule.if_conditions, newIfCond()] })}
            className="btn-ghost flex items-center gap-1 text-xs"
          >
            <Plus size={10} /> Add condition
          </button>
        </div>
        {rule.if_conditions.map((cond, ci) => (
          <div key={cond.id}>
            {ci > 0 && (
              <div className="flex items-center gap-2 my-1">
                <div className="flex-1 h-px bg-line" />
                <button
                  type="button"
                  onClick={() => updateIf(cond.id, { connector: cond.connector === 'OR' ? 'AND' : 'OR' })}
                  title="Click to toggle AND / OR"
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full border transition-colors cursor-pointer ${
                    cond.connector === 'OR'
                      ? 'text-warning bg-warning/10 border-warning/20 hover:bg-warning/20'
                      : 'text-info bg-info/10 border-info/20 hover:bg-info/20'
                  }`}
                >
                  {cond.connector === 'OR' ? 'OR' : 'AND'}
                </button>
                <div className="flex-1 h-px bg-line" />
              </div>
            )}
            <div className="flex flex-wrap gap-2 items-end">
              <div className="space-y-1 flex-1 min-w-28">
                <p className="text-xs text-muted">Column</p>
                <ColumnSelector multi={false} selected={cond.col ? [cond.col] : []}
                  onChange={(cs) => updateIf(cond.id, { col: cs[0] ?? '' })} />
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted">Operator</p>
                <select value={cond.op} onChange={(e) => updateIf(cond.id, { op: e.target.value })}>
                  {OPERATORS.map((op) => <option key={op}>{op}</option>)}
                </select>
              </div>
              {NEED_VALUE.has(cond.op) && (
                <div className="space-y-1 flex-1 min-w-24">
                  <p className="text-xs text-muted">Value</p>
                  <input type="text" className="w-full" value={cond.val}
                    onChange={(e) => updateIf(cond.id, { val: e.target.value })} placeholder="value" />
                </div>
              )}
              {rule.if_conditions.length > 1 && (
                <button onClick={() => removeIf(cond.id)} className="text-muted hover:text-critical mt-5">
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* THEN — OR via in_list */}
      <div className="space-y-2">
        <p className="label text-warning">THEN</p>
        <div className="flex flex-wrap gap-2 items-end">
          <div className="space-y-1 flex-1">
            <ColumnSelector multi label="Column(s)" selected={rule.then_cols}
              onChange={(cs) => onUpdate({ then_cols: cs })} />
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">Operator</p>
            <select value={rule.then_op} onChange={(e) => onUpdate({ then_op: e.target.value })}>
              {OPERATORS.map((op) => <option key={op}>{op}</option>)}
            </select>
          </div>
          {NEED_VALUE.has(rule.then_op) && (
            <div className="space-y-1 flex-1 min-w-28">
              <p className="text-xs text-muted">
                Value
                {(rule.then_op === 'in_list' || rule.then_op === 'not_in_list') && (
                  <span className="ml-1 text-accent">(comma-sep for OR: 8, 40)</span>
                )}
              </p>
              <input type="text" className="w-full" value={rule.then_val}
                onChange={(e) => onUpdate({ then_val: e.target.value })}
                placeholder={rule.then_op === 'in_list' ? '8, 40, 100' : 'value'} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Check Set panel ───────────────────────────────────────────────────────────

function CheckSetPanel({
  cs, fileId, jobId, onUpdate, onRemove,
}: {
  cs: CheckSet
  fileId: string | null
  jobId: string | null
  onUpdate: (patch: Partial<CheckSet>) => void
  onRemove: () => void
}) {
  const addSupplementalCheck = useAppStore((s) => s.addSupplementalCheck)
  const [error, setError] = React.useState('')

  const updateRule = (ruleId: number, patch: Partial<RuleBuilderState>) =>
    onUpdate({ rules: cs.rules.map((r) => (r.id === ruleId ? { ...r, ...patch } : r)) })

  const removeRule = (ruleId: number) =>
    onUpdate({ rules: cs.rules.filter((r) => r.id !== ruleId) })

  const run = async () => {
    if (!fileId) return
    setError('')
    onUpdate({ isRunning: true, result: null })
    try {
      const result = await validateLogic(fileId, cs.rules.map(buildApiRule))
      onUpdate({ result, isRunning: false })

      const checkEntry = {
        check_name: cs.name.toLowerCase().replace(/\s+/g, '_') || 'logic_check',
        issue_type: 'Logic Violation',
        severity: (result.violation_count > 0 ? 'warning' : 'info') as 'warning' | 'info',
        flag_count: result.violation_count,
        flagged_rows: result.flagged_rows,
      }

      // Add to QC Report tab display immediately
      addSupplementalCheck(checkEntry)

      // Push to backend report (non-blocking)
      if (jobId) {
        addSupplemental(jobId, checkEntry).catch(() => { /* non-blocking */ })
      }
    } catch (e) {
      setError((e as Error).message)
      onUpdate({ isRunning: false })
    }
  }

  return (
    <div className="border border-line rounded-xl p-4 space-y-4 bg-surface/40">
      <div className="flex items-center gap-2">
        <input
          type="text"
          className="flex-1 font-medium text-sm bg-transparent border-b border-line/60 focus:border-accent outline-none py-0.5"
          value={cs.name}
          onChange={(e) => onUpdate({ name: e.target.value })}
          placeholder="Check set name"
        />
        <button onClick={() => onUpdate({ rules: [...cs.rules, newRule()] })}
          className="btn-ghost flex items-center gap-1 text-xs">
          <Plus size={11} /> Add rule
        </button>
        <button onClick={onRemove} className="text-muted hover:text-critical transition-colors ml-1">
          <Trash2 size={13} />
        </button>
      </div>

      <div className="space-y-3">
        {cs.rules.map((rule, idx) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            idx={idx}
            onUpdate={(p) => updateRule(rule.id, p)}
            onRemove={() => removeRule(rule.id)}
          />
        ))}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={run}
          disabled={!fileId || cs.isRunning}
          className="btn-primary flex items-center gap-2 text-sm"
        >
          <Play size={13} />
          {cs.isRunning ? 'Validating…' : 'Run check set'}
        </button>
        {cs.result && !cs.isRunning && (
          <span className="flex items-center gap-1.5 text-xs text-accent">
            <CheckCircle2 size={13} /> Shown in QC Report tab
          </span>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-critical text-xs">
          <AlertCircle size={13} /> {error}
        </div>
      )}

      {cs.result && (
        <div className="card p-3 space-y-2 animate-fade-in">
          <span className={cs.result.violation_count > 0 ? 'badge-critical' : 'badge-info'}>
            {cs.result.violation_count} violations
          </span>
          {cs.result.violation_count > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-line">
                    {Object.keys(cs.result.flagged_rows[0] ?? {}).map((k) => (
                      <th key={k} className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {cs.result.flagged_rows.slice(0, 100).map((row, i) => (
                    <tr key={i} className="border-b border-line/50 hover:bg-surface2 transition-colors">
                      {Object.values(row).map((v, j) => (
                        <td key={j} className="py-1.5 px-2 whitespace-nowrap">{String(v ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function LogicChecks() {
  const { fileId, jobId, groqApiKey, logicCheckSets, setLogicCheckSets } = useAppStore()
  const counterRef = useRef(logicCheckSets.length + 1)

  const updateSet = (id: number, patch: Partial<CheckSet>) =>
    setLogicCheckSets(logicCheckSets.map((cs) => (cs.id === id ? { ...cs, ...patch } : cs)))

  const removeSet = (id: number) =>
    setLogicCheckSets(logicCheckSets.filter((cs) => cs.id !== id))

  const addSet = () => {
    counterRef.current += 1
    setLogicCheckSets([...logicCheckSets, newCheckSet(counterRef.current)])
  }

  return (
    <div className="space-y-6 max-w-3xl animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display font-extrabold text-base text-tx">Logic Checks</h2>
          <p className="text-xs text-muted mt-0.5">
            Build IF / THEN rules with AND conditions and OR values. Each check set runs independently and appears in the QC Report tab and downloaded Excel report.
          </p>
        </div>
        <button onClick={addSet} className="btn-ghost flex items-center gap-1.5 text-xs">
          <Plus size={12} /> Add check set
        </button>
      </div>

      <NlPanel groqApiKey={groqApiKey} />

      <div className="space-y-4">
        {logicCheckSets.map((cs) => (
          <CheckSetPanel
            key={cs.id}
            cs={cs}
            fileId={fileId}
            jobId={jobId}
            onUpdate={(patch) => updateSet(cs.id, patch)}
            onRemove={() => removeSet(cs.id)}
          />
        ))}
      </div>
    </div>
  )
}
