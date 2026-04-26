import { client } from './client'
import type { EDAResponse, LogicRule, LogicValidateResponse } from '../types'

export interface EDARequest {
  file_id: string
  x_col: string
  y_cols: string[]
  color_col?: string
  chart_type: 'bar' | 'line' | 'scatter' | 'histogram' | 'heatmap' | 'box'
  agg_func: string
}

export async function runEDA(req: EDARequest): Promise<EDAResponse> {
  const { data } = await client.post<EDAResponse>('/api/eda', req)
  return data
}

export async function validateLogic(
  fileId: string,
  rules: LogicRule[],
): Promise<LogicValidateResponse> {
  const { data } = await client.post<LogicValidateResponse>('/api/logic/validate', {
    file_id: fileId,
    rules,
  })
  return data
}
