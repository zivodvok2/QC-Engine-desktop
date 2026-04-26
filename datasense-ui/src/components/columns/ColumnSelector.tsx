import React from 'react'
import { X } from 'lucide-react'
import { useAppStore } from '../../store/appStore'

interface Props {
  selected: string[]
  onChange: (cols: string[]) => void
  multi?: boolean
  label?: string
  placeholder?: string
  columns?: string[]   // override store columns if needed
}

export function ColumnSelector({ selected, onChange, multi = true, label, placeholder, columns: colsProp }: Props) {
  const storeColumns = useAppStore((s) => s.columnNames)
  const columns = colsProp ?? storeColumns

  const toggle = (col: string) => {
    if (multi) {
      onChange(selected.includes(col) ? selected.filter((c) => c !== col) : [...selected, col])
    } else {
      onChange(selected[0] === col ? [] : [col])
    }
  }

  const remove = (col: string) => onChange(selected.filter((c) => c !== col))

  if (columns.length === 0) {
    return (
      <div className="text-xs text-muted italic py-2">
        {placeholder ?? 'Upload a file first to see columns.'}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {label && <p className="label">{label}</p>}

      {/* Selected pills */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((col) => (
            <span
              key={col}
              className="inline-flex items-center gap-1 bg-accent/20 text-accent text-xs px-2 py-0.5 rounded-full"
            >
              {col}
              <button onClick={() => remove(col)} className="hover:text-white transition-colors">
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Column chips */}
      <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto pr-1">
        {columns.map((col) => {
          const active = selected.includes(col)
          return (
            <button
              key={col}
              onClick={() => toggle(col)}
              className={`
                text-xs px-2.5 py-1 rounded-full border transition-all
                ${active
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-line text-muted hover:border-muted hover:text-tx'
                }
              `}
            >
              {col}
            </button>
          )
        })}
      </div>
    </div>
  )
}
