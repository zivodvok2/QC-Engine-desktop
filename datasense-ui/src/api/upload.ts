import { client } from './client'
import type { UploadResponse, ColumnsResponse } from '../types'

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<UploadResponse>('/api/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getColumns(fileId: string): Promise<ColumnsResponse> {
  const { data } = await client.get<ColumnsResponse>(`/api/columns/${fileId}`)
  return data
}
