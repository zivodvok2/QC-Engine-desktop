import React, { useState } from 'react'
import { X, LogIn, UserPlus, Loader2, ShieldCheck } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { login, register, verifyOtp } from '../../api/auth'

type Tab = 'login' | 'register'

export function LoginModal() {
  const { closeLogin, loginUser } = useAppStore()
  const [tab, setTab] = useState<Tab>('login')

  // login fields
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // register fields
  const [rName, setRName] = useState('')
  const [rEmail, setREmail] = useState('')
  const [rPassword, setRPassword] = useState('')
  const [rPassword2, setRPassword2] = useState('')

  // 2FA OTP step
  const [otpUserId, setOtpUserId] = useState<number | null>(null)
  const [demoOtp, setDemoOtp] = useState('')
  const [otpCode, setOtpCode] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(email.trim().toLowerCase(), password)
      if ('otp_required' in res) {
        setOtpUserId(res.user_id)
        setDemoOtp(res.demo_otp)
      } else {
        loginUser(res.user, res.token)
      }
    } catch (err) {
      setError((err as Error).message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    if (otpUserId === null) return
    setError('')
    setLoading(true)
    try {
      const res = await verifyOtp(otpUserId, otpCode.trim())
      loginUser(res.user, res.token)
    } catch (err) {
      setError((err as Error).message || 'Invalid code')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (rPassword !== rPassword2) { setError('Passwords do not match'); return }
    if (rPassword.length < 8) { setError('Password must be at least 8 characters'); return }
    setLoading(true)
    try {
      const res = await register(rEmail.trim().toLowerCase(), rPassword, rName.trim())
      loginUser(res.user, res.token)
    } catch (err) {
      setError((err as Error).message || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const switchTab = (t: Tab) => { setTab(t); setError(''); setSuccess('') }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) closeLogin() }}
    >
      <div className="bg-surface border border-line rounded-xl w-full max-w-sm shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <div className="flex items-center gap-2">
            {otpUserId !== null
              ? <ShieldCheck size={15} className="text-accent" />
              : tab === 'login'
                ? <LogIn size={15} className="text-accent" />
                : <UserPlus size={15} className="text-accent" />}
            <span className="font-display font-bold text-sm text-tx">
              {otpUserId !== null ? 'Two-factor verification' : tab === 'login' ? 'Sign in to Servalab' : 'Create an account'}
            </span>
          </div>
          <button
            onClick={closeLogin}
            className="p-1.5 text-muted hover:text-tx hover:bg-surface2 rounded transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        {otpUserId !== null && (
          <form onSubmit={handleVerifyOtp} className="p-5 space-y-4">
            <p className="text-xs text-muted">
              Enter the 6-digit code to finish signing in. This is a demo deployment with no email
              server yet, so the code is shown below instead of being emailed.
            </p>
            <p className="text-xs text-accent bg-accent/10 border border-accent/30 rounded-lg px-3 py-2">
              Demo code: <span className="font-mono font-bold">{demoOtp}</span>
            </p>
            <div>
              <label className="label mb-1 block">Verification code</label>
              <input
                type="text"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                placeholder="000000"
                inputMode="numeric"
                maxLength={6}
                required
                autoFocus
                className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors tracking-widest"
              />
            </div>
            {error && (
              <p className="text-xs text-critical bg-critical/10 border border-critical/30 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
              {loading ? 'Verifying…' : 'Verify'}
            </button>
            <button
              type="button"
              onClick={() => { setOtpUserId(null); setOtpCode(''); setDemoOtp(''); setError('') }}
              className="text-[11px] text-muted text-center w-full underline underline-offset-2"
            >
              Back to sign in
            </button>
          </form>
        )}

        {otpUserId === null && (
        <>
        {/* Tab bar */}
        <div className="flex border-b border-line">
          {(['login', 'register'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => switchTab(t)}
              className={`flex-1 py-2.5 text-xs font-medium transition-colors ${
                tab === t
                  ? 'text-accent border-b-2 border-accent'
                  : 'text-muted hover:text-tx'
              }`}
            >
              {t === 'login' ? 'Sign In' : 'Register'}
            </button>
          ))}
        </div>

        {/* Login form */}
        {tab === 'login' && (
          <form onSubmit={handleLogin} className="p-5 space-y-4">
            <p className="text-xs text-muted">
              Use your Servalab account to save QC results to projects and access the dashboard.
            </p>
            <div className="space-y-3">
              <div>
                <label className="label mb-1 block">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                />
              </div>
              <div>
                <label className="label mb-1 block">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                />
              </div>
            </div>
            {error && (
              <p className="text-xs text-critical bg-critical/10 border border-critical/30 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <LogIn size={14} />}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
            <p className="text-[11px] text-muted text-center">
              No account?{' '}
              <button type="button" onClick={() => switchTab('register')} className="text-accent underline underline-offset-2">
                Register here
              </button>
            </p>
          </form>
        )}

        {/* Register form */}
        {tab === 'register' && (
          <form onSubmit={handleRegister} className="p-5 space-y-4">
            <p className="text-xs text-muted">
              New accounts are set to a basic role. An admin will assign your full access level.
            </p>
            <div className="space-y-3">
              <div>
                <label className="label mb-1 block">Full name</label>
                <input
                  type="text"
                  value={rName}
                  onChange={(e) => setRName(e.target.value)}
                  placeholder="Your name"
                  required
                  className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                />
              </div>
              <div>
                <label className="label mb-1 block">Email</label>
                <input
                  type="email"
                  value={rEmail}
                  onChange={(e) => setREmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                />
              </div>
              <div>
                <label className="label mb-1 block">Password</label>
                <input
                  type="password"
                  value={rPassword}
                  onChange={(e) => setRPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  required
                  className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                />
              </div>
              <div>
                <label className="label mb-1 block">Confirm password</label>
                <input
                  type="password"
                  value={rPassword2}
                  onChange={(e) => setRPassword2(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full bg-surface2 border border-line rounded-lg px-3 py-2 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                />
              </div>
            </div>
            {error && (
              <p className="text-xs text-critical bg-critical/10 border border-critical/30 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
            {success && (
              <p className="text-xs text-accent bg-accent/10 border border-accent/30 rounded-lg px-3 py-2">
                {success}
              </p>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
              {loading ? 'Creating account…' : 'Create account'}
            </button>
            <p className="text-[11px] text-muted text-center">
              Already have an account?{' '}
              <button type="button" onClick={() => switchTab('login')} className="text-accent underline underline-offset-2">
                Sign in
              </button>
            </p>
          </form>
        )}
        </>
        )}
      </div>
    </div>
  )
}
