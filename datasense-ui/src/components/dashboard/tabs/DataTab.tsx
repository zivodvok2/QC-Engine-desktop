import React, { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Play, CheckCircle2, ArrowRight, RotateCcw, AlertCircle } from 'lucide-react'
import { useAppStore } from '../../../store/appStore'
import { useQCRun } from '../../../hooks/useQCRun'
import { FileUpload } from '../../upload/FileUpload'
import { saveQCResults } from '../../../api/projects'

const UPLOAD_ROLES = new Set(['qc_executive', 'operations_manager', 'qc_officer'])

interface Props {
  projectId: number
  onViewResults?: () => void
}

export function DataTab({ projectId, onViewResults }: Props) {
  const { authUser, authToken, fileId, filename, jobId, jobStatus, jobProgress, jobError, results, clearFile } = useAppStore()
  const token = authToken ?? ''
  const qc = useQueryClient()
  const { run, isRunning } = useQCRun()

  const [savedJobId, setSavedJobId] = useState<string | null>(null)
  const savingRef = useRef(false)

  const canUpload = authUser && UPLOAD_ROLES.has(authUser.role)

  const saveMut = useMutation({
    mutationFn: () => {
      if (!fileId || !filename) throw new Error('No file loaded')
      return saveQCResults(projectId, fileId, filename, token, undefined, jobId ?? undefined)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dash-quality', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-upload-log', projectId] })
      qc.invalidateQueries({ queryKey: ['dash-summary'] })
      setSavedJobId(jobId)
    },
    onSettled: () => {
      savingRef.current = false
    },
  })

  // Auto-save the moment a run completes — no manual "Save" click needed.
  useEffect(() => {
    if (jobStatus !== 'complete' || !jobId || !fileId) return
    if (jobId === savedJobId || savingRef.current) return
    savingRef.current = true
    saveMut.mutate()
  }, [jobStatus, jobId, fileId])

  if (!canUpload) {
    return (
      <div className="card p-8 text-center text-muted text-sm">
        You don't have permission to upload data for this project.
      </div>
    )
  }

  const justSaved = jobStatus === 'complete' && jobId === savedJobId

  return (
    <div className="space-y-4">
      {!fileId && <FileUpload />}

      {fileId && jobStatus === 'idle' && (
        <div className="card p-4 flex items-center justify-between gap-3">
          <div className="text-sm text-tx truncate">{filename}</div>
          <button onClick={run} className="btn-primary flex items-center gap-2 shrink-0">
            <Play size={14} /> Run Checks
          </button>
        </div>
      )}

      {(isRunning || jobStatus === 'queued' || jobStatus === 'running') && (
        <div className="card p-4 space-y-2">
          <div className="flex items-center gap-2 text-sm text-tx">
            <Loader2 size={14} className="animate-spin text-accent" />
            {jobStatus === 'queued' ? 'Queued…' : `Running checks… ${jobProgress}%`}
          </div>
          <div className="w-full bg-line rounded-full h-1.5">
            <div className="bg-accent h-1.5 rounded-full transition-all" style={{ width: `${jobProgress || 10}%` }} />
          </div>
        </div>
      )}

      {jobStatus === 'failed' && (
        <div className="card p-4 flex items-center gap-2 text-sm text-critical">
          <AlertCircle size={14} />
          {jobError ?? 'QC run failed.'}
        </div>
      )}

      {jobStatus === 'complete' && results && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm text-tx">
            {saveMut.isPending ? (
              <>
                <Loader2 size={14} className="animate-spin text-accent" /> Saving results to project…
              </>
            ) : justSaved ? (
              <>
                <CheckCircle2 size={14} className="text-accent" /> Saved to project
              </>
            ) : saveMut.isError ? (
              <>
                <AlertCircle size={14} className="text-critical" /> {String(saveMut.error)}
              </>
            ) : null}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="card2 p-3 text-center">
              <p className="label mb-0.5">Total Flags</p>
              <p className="text-lg font-bold font-display text-tx">{results.total_flags}</p>
            </div>
            {Object.entries(results.flagged_by_severity).map(([sev, count]) => (
              <div key={sev} className="card2 p-3 text-center">
                <p className="label mb-0.5 capitalize">{sev}</p>
                <p className={`text-lg font-bold font-display ${
                  sev === 'critical' ? 'text-critical' : sev === 'warning' ? 'text-warning' : 'text-muted'
                }`}>
                  {count}
                </p>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <button onClick={clearFile} className="btn-ghost flex items-center gap-1.5 text-xs">
              <RotateCcw size={12} /> Upload another file
            </button>
            {onViewResults && (
              <button onClick={onViewResults} className="btn-ghost flex items-center gap-1.5 text-xs">
                View in Quality Report tab <ArrowRight size={12} />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
