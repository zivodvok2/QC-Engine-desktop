import { client } from './client'

export interface NLToRuleResponse {
  rule: Record<string, unknown>
  raw: string
}

export interface FeedbackLetterResponse {
  letter: string
}

export interface DataQuestionResponse {
  answer: string
}

export async function nlToRule(
  description: string,
  groqApiKey: string,
  model = 'llama-3.1-8b-instant',
): Promise<NLToRuleResponse> {
  const { data } = await client.post<NLToRuleResponse>('/api/ai/nl-to-rule', {
    description,
    groq_api_key: groqApiKey,
    model,
  })
  return data
}

export async function generateFeedbackLetter(
  interviewerId: string,
  stats: Record<string, unknown>,
  groqApiKey: string,
  model = 'llama-3.1-8b-instant',
): Promise<FeedbackLetterResponse> {
  const { data } = await client.post<FeedbackLetterResponse>('/api/ai/feedback-letter', {
    interviewer_id: interviewerId,
    stats,
    groq_api_key: groqApiKey,
    model,
  })
  return data
}

export async function askDataQuestion(
  fileId: string,
  question: string,
  groqApiKey: string,
  model = 'llama-3.1-8b-instant',
): Promise<DataQuestionResponse> {
  const { data } = await client.post<DataQuestionResponse>('/api/ai/data-question', {
    file_id: fileId,
    question,
    groq_api_key: groqApiKey,
    model,
  })
  return data
}
