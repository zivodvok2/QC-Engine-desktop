import React, { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import type { RangeRule, PatternRule } from '../../types'

export function Config() {
  const { config, updateConfig, columnNames } = useAppStore()
  const [newRange, setNewRange] = useState<Partial<RangeRule>>({ column: '', min: 0, max: 100 })
  const [newPattern, setNewPattern] = useState<Partial<PatternRule>>({ column: '', pattern: '', description: '' })

  const addRange = () => {
    if (!newRange.column) return
    updateConfig({ range_rules: [...config.range_rules, newRange as RangeRule] })
    setNewRange({ column: '', min: 0, max: 100 })
  }

  const removeRange = (i: number) =>
    updateConfig({ range_rules: config.range_rules.filter((_, idx) => idx !== i) })

  const addPattern = () => {
    if (!newPattern.column || !newPattern.pattern) return
    updateConfig({ pattern_rules: [...config.pattern_rules, newPattern as PatternRule] })
    setNewPattern({ column: '', pattern: '', description: '' })
  }

  const removePattern = (i: number) =>
    updateConfig({ pattern_rules: config.pattern_rules.filter((_, idx) => idx !== i) })

  return (
    <div className="space-y-8 max-w-2xl animate-fade-in">
      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Configuration</h2>
        <p className="text-xs text-muted mt-0.5">Fine-tune range rules and pattern validations.</p>
      </div>

      {/* Range rules */}
      <section className="space-y-3">
        <p className="label">Range Rules</p>
        <p className="text-xs text-muted">Flag numeric values outside expected bounds.</p>

        {config.range_rules.map((rule, i) => (
          <div key={i} className="card2 flex items-center gap-3 px-4 py-2">
            <span className="text-sm text-accent flex-1">{rule.column}</span>
            <span className="text-xs text-muted">{rule.min ?? '–∞'} → {rule.max ?? '+∞'}</span>
            <button onClick={() => removeRange(i)} className="text-muted hover:text-critical transition-colors">
              <Trash2 size={13} />
            </button>
          </div>
        ))}

        <div className="card p-3 flex flex-wrap gap-2 items-end">
          <div className="space-y-1 flex-1 min-w-32">
            <p className="text-xs text-muted">Column</p>
            <select className="w-full" value={newRange.column}
              onChange={(e) => setNewRange((r) => ({ ...r, column: e.target.value }))}>
              <option value="">Select…</option>
              {columnNames.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">Min</p>
            <input type="number" className="w-20" value={newRange.min ?? ''}
              onChange={(e) => setNewRange((r) => ({ ...r, min: parseFloat(e.target.value) }))} />
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted">Max</p>
            <input type="number" className="w-20" value={newRange.max ?? ''}
              onChange={(e) => setNewRange((r) => ({ ...r, max: parseFloat(e.target.value) }))} />
          </div>
          <button onClick={addRange} className="btn-ghost flex items-center gap-1 text-xs">
            <Plus size={12} /> Add
          </button>
        </div>
      </section>

      {/* Pattern rules */}
      <section className="space-y-3">
        <p className="label">Pattern Rules (Regex)</p>
        <p className="text-xs text-muted">Flag values that don't match a regular expression.</p>

        {config.pattern_rules.map((rule, i) => (
          <div key={i} className="card2 flex items-center gap-3 px-4 py-2">
            <span className="text-sm text-accent">{rule.column}</span>
            <span className="text-xs text-muted font-mono flex-1 truncate">{rule.pattern}</span>
            {rule.description && <span className="text-xs text-muted">{rule.description}</span>}
            <button onClick={() => removePattern(i)} className="text-muted hover:text-critical transition-colors">
              <Trash2 size={13} />
            </button>
          </div>
        ))}

        <div className="card p-3 space-y-2">
          <div className="flex flex-wrap gap-2">
            <div className="space-y-1 flex-1 min-w-28">
              <p className="text-xs text-muted">Column</p>
              <select className="w-full" value={newPattern.column}
                onChange={(e) => setNewPattern((r) => ({ ...r, column: e.target.value }))}>
                <option value="">Select…</option>
                {columnNames.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="space-y-1 flex-1 min-w-40">
              <p className="text-xs text-muted">Regex pattern</p>
              <input type="text" className="w-full font-mono" value={newPattern.pattern ?? ''}
                onChange={(e) => setNewPattern((r) => ({ ...r, pattern: e.target.value }))}
                placeholder="^\d{4}$" />
            </div>
          </div>
          <div className="flex gap-2 items-end">
            <div className="space-y-1 flex-1">
              <p className="text-xs text-muted">Description (optional)</p>
              <input type="text" className="w-full" value={newPattern.description ?? ''}
                onChange={(e) => setNewPattern((r) => ({ ...r, description: e.target.value }))} />
            </div>
            <button onClick={addPattern} className="btn-ghost flex items-center gap-1 text-xs">
              <Plus size={12} /> Add
            </button>
          </div>
        </div>
      </section>

      {/* Duplicate subset */}
      <section className="space-y-3">
        <p className="label">Duplicate Check</p>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted">Subset columns (comma-separated):</span>
          <input type="text" className="flex-1"
            value={config.duplicate_check.subset_columns.join(', ')}
            onChange={(e) =>
              updateConfig({ duplicate_check: { ...config.duplicate_check, subset_columns: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) } })
            }
            placeholder="respondent_id, phone" />
        </div>
      </section>
    </div>
  )
}
