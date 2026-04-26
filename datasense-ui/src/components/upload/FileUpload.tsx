import React, { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, AlertCircle } from 'lucide-react'
import { useQCRun } from '../../hooks/useQCRun'
import { useAppStore } from '../../store/appStore'

const ACCEPTED = { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/vnd.ms-excel': ['.xls'] }

interface Props {
  compact?: boolean
}

export function FileUpload({ compact = false }: Props) {
  const { upload, isUploading, uploadError } = useQCRun()
  const { filename, rowCount, columnCount } = useAppStore()

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
      <div className="flex items-center gap-2 px-3 py-2 bg-surface2 border border-line rounded-lg text-sm">
        <FileText size={14} className="text-accent shrink-0" />
        <span className="text-tx truncate flex-1">{filename}</span>
        <span className="text-muted text-xs shrink-0">{rowCount?.toLocaleString()} rows</span>
      </div>
    )
  }

  return (
    <div className="space-y-2">
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
