import React, { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, AlertCircle, X, GitCompare, RotateCcw } from 'lucide-react'
import { useQCRun } from '../../hooks/useQCRun'
import { useAppStore } from '../../store/appStore'

const ACCEPTED = { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/vnd.ms-excel': ['.xls'] }

interface Props {
  compact?: boolean
}

export function FileUpload({ compact = false }: Props) {
  const { upload, isUploading, uploadError } = useQCRun()
  const { filename, rowCount, columnCount, clearFile, setActiveTab, sessionRestored, sessionRestoredAt, dismissSessionRestore } = useAppStore()

  const onDrop = useCallback(
    (files: File[]) => { if (files[0]) upload(files[0]) },
    [upload],
  )

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxFiles: 1,
    disabled: isUploading,
  })

  const rejected = fileRejections[0]?.errors[0]?.message

  if (filename && !isUploading && compact) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 px-3 py-2 bg-surface2 border border-line rounded-lg text-sm">
          <FileText size={14} className="text-accent shrink-0" />
          <span className="text-tx truncate flex-1 text-xs">{filename}</span>
          <span className="text-muted text-xs shrink-0">{rowCount?.toLocaleString()}r</span>
          <button
            onClick={clearFile}
            title="Remove file"
            className="text-muted hover:text-critical transition-colors shrink-0 ml-1"
          >
            <X size={12} />
          </button>
        </div>
        <button
          onClick={() => setActiveTab('Wave Compare')}
          className="w-full flex items-center gap-1.5 px-3 py-1.5 text-[10px] text-muted hover:text-tx border border-dashed border-line rounded-lg transition-colors hover:border-muted"
        >
          <GitCompare size={11} />
          Compare with another file
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {sessionRestored && (
        <div className="flex items-center gap-2 px-3 py-2 bg-accent/10 border border-accent/30 rounded-lg text-xs text-accent">
          <RotateCcw size={11} className="shrink-0" />
          <span className="flex-1">Session restored from {sessionRestoredAt} — upload a new file to replace it.</span>
          <button onClick={dismissSessionRestore} className="text-accent/60 hover:text-accent">
            <X size={11} />
          </button>
        </div>
      )}
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg cursor-pointer transition-all
          flex flex-col items-center justify-center text-center select-none
          ${compact ? 'p-4 gap-2' : 'p-10 gap-4'}
          ${isDragActive ? 'border-accent bg-accent/5 text-accent' : 'border-line hover:border-muted hover:bg-surface2 text-muted'}
          ${isUploading ? 'opacity-50 cursor-wait' : ''}
        `}
      >
        <input {...getInputProps()} />
        <Upload size={compact ? 20 : 32} className={isDragActive ? 'text-accent' : 'text-muted'} />
        {isUploading ? (
          <p className="text-sm">Uploading…</p>
        ) : isDragActive ? (
          <p className="text-sm font-medium">Drop to upload</p>
        ) : (
          <div>
            <p className={`font-medium text-tx ${compact ? 'text-sm' : 'text-base'}`}>
              Drop a file or click to browse
            </p>
            <p className="text-xs text-muted mt-1">CSV · XLSX · XLS</p>
          </div>
        )}
      </div>

      {(uploadError || rejected) && (
        <div className="flex items-center gap-2 text-xs text-critical">
          <AlertCircle size={12} />
          <span>{uploadError ?? rejected}</span>
        </div>
      )}

      {filename && !isUploading && (
        <div className="flex items-center gap-2 px-3 py-2 bg-surface2 border border-line rounded text-xs">
          <FileText size={12} className="text-accent" />
          <span className="text-tx truncate">{filename}</span>
          <span className="text-muted ml-auto shrink-0">{rowCount?.toLocaleString()} rows · {columnCount} cols</span>
        </div>
      )}
    </div>
  )
}
