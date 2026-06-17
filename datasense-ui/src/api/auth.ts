import { client } from './client'

export interface AuthUser {
  id: number
  email: string
  name: string
  role: string
}

export interface LoginResponse {
  token: string
  user: AuthUser
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>('/api/auth/login', { email, password })
  return data
}

export async function register(email: string, password: string, fullName: string): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>('/api/auth/register', {
    email,
    password,
    full_name: fullName,
  })
  return data
}

export async function me(token: string): Promise<AuthUser> {
  const { data } = await client.get<AuthUser>('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}
