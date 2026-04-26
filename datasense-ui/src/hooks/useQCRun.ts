import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as uploadApi from '../api/upload'
import * as qcApi from '../api/qc'
import { useAppStore } from '../store/appStore'
import type { QCConfig } from '../types'

export function useQCRun() {
  const qc = useQueryClient()
  const store = useAppStore()

  // ── Upload ────────────────────────────────────────────────────────────────
  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadApi.uploadFile(file),
    onSuccess: (data) => {
      store.setFile(data)
      // also fetch columns/sample
      qc.invalidateQueries({ queryKey: ['columns', data.file_id] })
    },
  })

  // ── Run QC ────────────────────────────────────────────────────────────────
  const runMutation = useMutation({
    mutationFn: ({ fileId, config }: { fileId: string; config: QCConfig }) =>
      qcApi.runQC(fileId, config),
    onSuccess: (data) => {
      store.setJobId(data.job_id)
    },
  })

  // ── Poll status ───────────────────────────────────────────────────────────
  const statusQuery = useQuery({
    queryKey: ['qc-status', store.jobId],
    queryFn: () => qcApi.getStatus(store.jobId!),
    enabled: !!store.jobId && store.jobStatus !== 'complete' && store.jobStatus !== 'failed',
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'complete' || s === 'failed' ? false : 2000
    },
  })

  useEffect(() => {
    if (!statusQuery.data) return
    const { status, progress, error } = statusQuery.data
    if (status === 'failed') {
      store.setJobError(error ?? 'QC job failed')
    } else {
      store.setJobStatus(status as never, progress)
    }
  }, [statusQuery.data])

  // ── Fetch results when complete ───────────────────────────────────────────
  const resultsQuery = useQuery({
    queryKey: ['qc-results', store.jobId],
    queryFn: () => qcApi.getResults(store.jobId!),
    enabled: !!store.jobId && store.jobStatus === 'complete' && !store.results,
  })

  useEffect(() => {
    if (resultsQuery.data) store.setResults(resultsQuery.data)
  }, [resultsQuery.data])

  // ── Actions ───────────────────────────────────────────────────────────────
  const upload = (file: File) => uploadMutation.mutateAsync(file)

  const run = () => {
    if (!store.fileId) return
    const config = store.groqApiKey
      ? { ...store.config, verbatim_check: { ...store.config.verbatim_check, groq_api_key: store.groqApiKey } }
      : store.config
    return runMutation.mutateAsync({ fileId: store.fileId, config })
  }

  const isRunning =
    runMutation.isPending ||
    store.jobStatus === 'queued' ||
    store.jobStatus === 'running'

  return {
    upload,
    run,
    isUploading: uploadMutation.isPending,
    isRunning,
    uploadError: uploadMutation.error?.message,
    runError: runMutation.error?.message,
    progress: store.jobProgress,
    jobStatus: store.jobStatus,
  }
}
