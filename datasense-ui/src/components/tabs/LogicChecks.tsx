import React, { useState } from 'react'
import { Plus, Trash2, Play, AlertCircle, Sparkles, ChevronDown, ChevronUp } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { ColumnSelector } from '../columns/ColumnSelector'
import { validateLogic } from '../../api/eda'
import { nlToRule } from '../../api/ai'
import { useAppStore } from '../../store/appStore'
import type { LogicRule, LogicValidateResponse } from '../../types'

const OPERATORS = ['==', '!=', '>', '<', '>=', '<=', 'is_null', 'not_null', 'in_list', 'not_in_list']
const NEED_VALUE = new Set(['==', '!=', '>', '<', '>=', '<=', 'in_list', 'not_in_list'])

interface RuleBuilder {
  id: number
  if_col: string
  if_op: string
  if_val: string
  then_cols: string[]
  then_op: string
  then_val: string
  description: string
}

let counter = 0
const newRule = (): RuleBuilder => ({
  id: ++counter, if_col: '', if_op: '==', if_val: '', then_cols: [], then_op: 'is_null', then_val: '', description: '',
})

function buildApiRule(r: RuleBuilder): LogicRule {
  return {
    description: r.description || `Rule ${r.id}`,
    if_conditions: r.if_col
      ? [{ column: r.if_col, operator: r.if_op, value: NEED_VALUE.has(r.if_op) ? r.if_val : undefined }]
      : [],
    then_conditions: r.then_cols.map((c) => ({
      column: c, operator: r.then_op, value: NEED_VALUE.has(r.then_op) ? r.then_val : undefined,
    })),
  }
}

export function LogicChecks() {
  const { fileId, groqApiKey } = useAppStore()
  const [rules, setRules] = useState<RuleBuilder[]>([newRule()])
  const [result, setResult] = useState<LogicValidateResponse | null>(null)
  const [nlOpen, setNlOpen] = useState(false)
  const [nlText, setNlText] = useState('')
  const [nlResult, setNlResult] = useState<Record<string, unknown> | null>(null)

  const nlMutation = useMutation({
    mutationFn: () => nlToRule(nlText, groqApiKey),
    onSuccess: (data) => setNlResult(data.rule),
  })

  const mutation = useMutation({
    mutationFn: () => validateLogic(fileId!, rules.map(buildApiRule)),
    onSuccess: setResult,
  })

  const update = (id: number, patch: Partial<RuleBuilder>) =>
    setRules((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)))

  const remove = (id: number) => setRules((rs) => rs.filter((r) => r.id !== id))

  return (
    <div className="space-y-6 max-w-3xl animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display font-extrabold text-base text-tx">Logic Checks</h2>
          <p className="text-xs text-muted mt-0.5">Define IF / THEN conditional rules and validate them against your file.</p>
        </div>
        <button onClick={() => setRules((rs) => [...rs, newRule()])} className="btn-ghost flex items-center gap-1.5 text-xs">
          <Plus size={12} /> Add rule
        </button>
      </div>

      {/* AI rule builder */}
      <div className="card border-line">
        <button
          onClick={() => setNlOpen((o) => !o)}
          className="w-full flex items-center justify-between px-4 py-3 text-xs text-muted hover:text-tx transition-colors"
        >
          <span className="flex items-center gap-1.5"><Sparkles size={11} className="text-accent" /> Describe in plain English (AI → rule)</span>
          {nlOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
        {nlOpen && (
          <div className="px-4 pb-4 space-y-3 border-t border-line pt-3">
            <p className="text-[10px] text-muted">
              Describe what the rule should check and Groq AI will convert it to a QC rule config.
              {!groqApiKey && <span className="text-warning ml-1">Set Groq API key in Settings first.</span>}
            </p>
            <textarea
              className="w-full h-20 text-xs bg-surface2 border border-line rounded p-2 resize-none text-tx placeholder-muted"
              placeholder="e.g. If age is under 18 then salary should be empty"
              value={nlText}
              onChange={(e) => setNlText(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                onClick={() => nlMutation.mutate()}
                disabled={!nlText.trim() || !groqApiKey || nlMutation.isPending}
                className="btn-primary flex items-center gap-1.5 text-xs"
              >
                <Sparkles size={11} />
                {nlMutation.isPending ? 'Converting…' : 'Convert to rule'}
              </button>
            </div>
            {nlMutation.isError && (
              <p className="text-xs text-critical">{(nlMutation.error as Error).message}</p>
            )}
            {nlResult && (
              <div className="space-y-1">
                <p className="text-[10px] text-muted">Generated rule JSON:</p>
                <pre className="text-[10px] bg-surface2 border border-line rounded p-2 overflow-auto text-accent">
                  {JSON.stringify(nlResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>

      {rules.map((rule, idx) => (
        <div key={rule.id} className="card p-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="label">Rule {idx + 1}</span>
            <button onClick={() => remove(rule.id)} className="text-muted hover:text-critical transition-colors">
              <Trash2 size={14} />
            </button>
          </div>

          <div className="space-y-1">
            <p className="text-xs text-muted">Description (optional)</p>
            <input type="text" className="w-full" value={rule.description}
              onChange={(e) => update(rule.id, { description: e.target.value })}
              placeholder="e.g. Under-18 must not have salary" />
          </div>

          {/* IF */}
          <div className="space-y-2">
            <p className="label text-info">IF</p>
            <div className="flex flex-wrap gap-2 items-end">
              <div className="space-y-1 flex-1 min-w-32">
                <p className="text-xs text-muted">Column</p>
                <ColumnSelector multi={false} selected={rule.if_col ? [rule.if_col] : []}
                  onChange={(cs) => update(rule.id, { if_col: cs[0] ?? '' })} />
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted">Operator</p>
                <select value={rule.if_op} onChange={(e) => update(rule.id, { if_op: e.target.value })}>
                  {OPERATORS.map((op) => <option key={op}>{op}</option>)}
                </select>
              </div>
              {NEED_VALUE.has(rule.if_op) && (
                <div className="space-y-1 flex-1 min-w-24">
                  <p className="text-xs text-muted">Value</p>
                  <input type="text" className="w-full" value={rule.if_val}
                    onChange={(e) => update(rule.id, { if_val: e.target.value })} placeholder="value" />
                </div>
              )}
            </div>
          </div>

          {/* THEN */}
          <div className="space-y-2">
            <p className="label text-warning">THEN</p>
            <div className="flex flex-wrap gap-2 items-end">
              <div className="space-y-1 flex-1">
                <ColumnSelector multi label="Column(s)" selected={rule.then_cols}
                  onChange={(cs) => update(rule.id, { then_cols: cs })} />
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted">Operator</p>
                <select value={rule.then_op} onChange={(e) => update(rule.id, { then_op: e.target.value })}>
                  {OPERATORS.map((op) => <option key={op}>{op}</option>)}
                </select>
              </div>
              {NEED_VALUE.has(rule.then_op) && (
                <div className="space-y-1 flex-1 min-w-24">
                  <p className="text-xs text-muted">Value</p>
                  <input type="text" className="w-full" value={rule.then_val}
                    onChange={(e) => update(rule.id, { then_val: e.target.value })} placeholder="value" />
                </div>
              )}
            </div>
          </div>
        </div>
      ))}

      <button
        onClick={() => mutation.mutate()}
        disabled={!fileId || mutation.isPending}
        className="btn-primary flex items-center gap-2"
      >
        <Play size={14} />
        {mutation.isPending ? 'Validating…' : 'Run checks'}
      </button>

      {mutation.isError && (
        <div className="flex items-center gap-2 text-critical text-sm">
          <AlertCircle size={14} />
          {(mutation.error as Error).message}
        </div>
      )}

      {result && (
        <div className="card p-4 space-y-3 animate-fade-in">
          <div className="flex items-center gap-2">
            <span className={result.violation_count > 0 ? 'badge-critical' : 'badge-info'}>
              {result.violation_count} violations
            </span>
          </div>
          {result.violation_count > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-line">
                    {Object.keys(result.flagged_rows[0] ?? {}).map((k) => (
                      <th key={k} className="text-left py-1.5 px-2 text-muted font-normal whitespace-nowrap">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.flagged_rows.slice(0, 100).map((row, i) => (
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
