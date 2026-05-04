import React, { useState } from 'react'
import {
  Upload, ShieldCheck, TrendingDown, Users, Braces,
  LineChart, GitCompare, Target, MessageSquare, Database,
  PlayCircle, Tag,
} from 'lucide-react'

interface Demo {
  icon: React.ElementType
  title: string
  desc: string
  duration: string
  tag: 'getting started' | 'core' | 'advanced' | 'analysis'
  video?: string
}

const DEMOS: Demo[] = [
  {
    icon: Upload,
    title: 'Uploading Your Data',
    desc: 'Upload CSV, Excel, or SPSS files. Map key columns like respondent ID, interviewer ID, and duration.',
    duration: '~2 min',
    tag: 'getting started',
  },
  {
    icon: ShieldCheck,
    title: 'Running QC Checks',
    desc: 'Walk through the QC Report — missing values, range violations, logic flags, near-duplicates, and fabrication signals. Download Excel and HTML reports.',
    duration: '~4 min',
    tag: 'core',
  },
  {
    icon: TrendingDown,
    title: 'Straightlining Detection',
    desc: 'Detect respondents who gave the same answer across a battery of Likert-scale questions. Configure thresholds and export flagged IDs.',
    duration: '~3 min',
    tag: 'core',
  },
  {
    icon: Users,
    title: 'Interviewer Risk Analysis',
    desc: 'Get weighted risk scores (RAG) per interviewer — covering duration anomalies, productivity spikes, straightlining, and consent issues.',
    duration: '~3 min',
    tag: 'core',
  },
  {
    icon: Braces,
    title: 'Building Logic Rules',
    desc: 'Use the visual builder or AI assistant to create multi-condition IF/THEN checks — e.g. "Under-18 should not report a salary".',
    duration: '~4 min',
    tag: 'advanced',
  },
  {
    icon: LineChart,
    title: 'EDA & Data Charts',
    desc: 'Explore your data visually — frequency plots, correlation matrices, numeric distributions, and cross-tabs with interactive Plotly charts.',
    duration: '~3 min',
    tag: 'analysis',
  },
  {
    icon: GitCompare,
    title: 'Wave Comparison',
    desc: 'Compare two waves to detect demographic drift, flag new interviewers, and spot anomalous shifts in key variables across fieldwork periods.',
    duration: '~3 min',
    tag: 'advanced',
  },
  {
    icon: Target,
    title: 'Quota Monitoring',
    desc: 'Set targets per quota cell and track achievement in real time. RAG colours highlight cells that are off-track before you close fieldwork.',
    duration: '~2 min',
    tag: 'advanced',
  },
  {
    icon: MessageSquare,
    title: 'Verbatim QC',
    desc: 'Score open-ended responses for grammar quality using Groq AI. Flag low-quality or suspicious verbatims and export for manual review.',
    duration: '~3 min',
    tag: 'analysis',
  },
  {
    icon: Database,
    title: 'Batch Upload & Processing',
    desc: 'Upload and QC multiple survey files at once. Results are merged into a single consolidated report, ideal for multi-country fieldwork.',
    duration: '~3 min',
    tag: 'getting started',
  },
]

const TAG_STYLES: Record<Demo['tag'], string> = {
  'getting started': 'bg-accent/20 text-accent',
  'core':            'bg-blue-500/20 text-blue-400',
  'advanced':        'bg-yellow-500/20 text-yellow-400',
  'analysis':        'bg-purple-500/20 text-purple-400',
}

const ALL_TAGS = ['all', 'getting started', 'core', 'advanced', 'analysis'] as const
type Filter = (typeof ALL_TAGS)[number]

export function Demos() {
  const [filter, setFilter] = useState<Filter>('all')

  const visible = filter === 'all' ? DEMOS : DEMOS.filter((d) => d.tag === filter)

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display font-extrabold text-base text-tx">Demo Videos</h2>
        <p className="text-xs text-muted mt-0.5">
          Short walkthroughs for every part of the QC engine. Videos will be embedded once recorded.
        </p>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <Tag size={12} className="text-muted shrink-0" />
        {ALL_TAGS.map((tag) => (
          <button
            key={tag}
            onClick={() => setFilter(tag)}
            className={`text-[10px] px-3 py-1 rounded-full border capitalize transition-colors ${
              filter === tag
                ? 'border-accent text-accent bg-accent/10'
                : 'border-line text-muted hover:border-muted hover:text-tx'
            }`}
          >
            {tag}
          </button>
        ))}
      </div>

      {/* Card grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {visible.map((demo) => {
          const Icon = demo.icon
          return (
            <div key={demo.title} className="card p-4 space-y-3 flex flex-col">
              {/* Header */}
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 bg-surface2 rounded-lg flex items-center justify-center shrink-0">
                  <Icon size={16} className="text-accent" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-tx leading-snug">{demo.title}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[9px] px-2 py-0.5 rounded-full font-medium capitalize ${TAG_STYLES[demo.tag]}`}>
                      {demo.tag}
                    </span>
                    <span className="text-[10px] text-muted">{demo.duration}</span>
                  </div>
                </div>
              </div>

              {/* Description */}
              <p className="text-xs text-muted leading-relaxed flex-1">{demo.desc}</p>

              {/* Video or placeholder */}
              {demo.video ? (
                <video
                  src={demo.video}
                  controls
                  className="w-full rounded-lg border border-line"
                  style={{ maxHeight: 200 }}
                />
              ) : (
                <div className="border border-dashed border-line rounded-lg h-32 flex flex-col items-center justify-center gap-2 bg-surface2">
                  <PlayCircle size={22} className="text-line" />
                  <span className="text-[10px] text-muted uppercase tracking-wider">Coming soon</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
