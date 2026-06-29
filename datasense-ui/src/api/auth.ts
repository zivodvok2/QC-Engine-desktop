import { client } from './client'

export interface AuthUser {
  id: number
  email: string
  name: string
  role: string
  totp_enabled?: boolean
}

export interface LoginResponse {
  token: string
  user: AuthUser
}

export interface OtpChallenge {
  otp_required: true
  user_id: number
  demo_otp: string
}

export async function login(email: string, password: string): Promise<LoginResponse | OtpChallenge> {
  const { data } = await client.post<LoginResponse | OtpChallenge>('/api/auth/login', { email, password })
  return data
}

export async function verifyOtp(userId: number, code: string): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>('/api/auth/verify-otp', { user_id: userId, code })
  return data
}

export async function enable2FA(token: string): Promise<AuthUser> {
  const { data } = await client.post<AuthUser>('/api/auth/enable-2fa', null, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return data
}

export async function disable2FA(token: string): Promise<AuthUser> {
  const { data } = await client.post<AuthUser>('/api/auth/disable-2fa', null, {
    headers: { Authorization: `Bearer ${token}` },
  })
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
