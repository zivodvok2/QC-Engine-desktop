import React, { useState } from 'react'
import { X, LogIn, Loader2 } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { login } from '../../api/auth'

export function LoginModal() {
  const { closeLogin, loginUser } = useAppStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(email.trim().toLowerCase(), password)
      loginUser(res.user, res.token)
    } catch (err) {
      setError((err as Error).message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) closeLogin() }}
    >
      <div className="bg-surface border border-line rounded-xl w-full max-w-sm shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <div className="flex items-center gap-2">
            <LogIn size={15} className="text-accent" />
            <span className="font-display font-bold text-sm text-tx">Sign in to Servalab</span>
          </div>
          <button
            onClick={closeLogin}
            className="p-1.5 text-muted hover:text-tx hover:bg-surface2 rounded transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <p className="text-xs text-muted">
            Use your Servalab dashboard account. Signing in lets you save QC results to projects.
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
            <a
              href="http://localhost:8502"
              target="_blank"
              rel="noreferrer"
              className="text-accent underline underline-offset-2"
            >
              Register on the dashboard
            </a>
          </p>
        </form>
      </div>
    </div>
  )
}
