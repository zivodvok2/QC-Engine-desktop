import React, { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { ONBOARDING_STEPS } from '../../data/onboarding'

const STORAGE_KEY = 'servallab_onboarding_done'

export function OnboardingTooltip() {
  const [visible, setVisible] = useState(false)
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) setVisible(true)
  }, [])

  const close = () => {
    localStorage.setItem(STORAGE_KEY, '1')
    setVisible(false)
  }

  if (!visible) return null

  const current = ONBOARDING_STEPS[step]
  const isLast = step === ONBOARDING_STEPS.length - 1

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="card w-full max-w-md p-6 space-y-4 animate-slide-up shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between">
          <span className="text-3xl">{current.icon}</span>
          <button onClick={close} className="text-muted hover:text-tx transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div>
          <h2 className="font-display text-lg font-extrabold text-tx mb-2">{current.title}</h2>
          <p className="text-sm text-muted leading-relaxed">{current.body}</p>
        </div>

        {/* Progress dots */}
        <div className="flex items-center gap-1.5">
          {ONBOARDING_STEPS.map((_, i) => (
            <button
              key={i}
              onClick={() => setStep(i)}
              className={`w-1.5 h-1.5 rounded-full transition-all ${i === step ? 'bg-accent w-3' : 'bg-line hover:bg-muted'}`}
            />
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-1">
          <button onClick={close} className="text-xs text-muted hover:text-tx transition-colors">
            Skip tour
          </button>
          <div className="flex gap-2">
            {step > 0 && (
              <button onClick={() => setStep((s) => s - 1)} className="btn-ghost text-xs">
                Back
              </button>
            )}
            {isLast ? (
              <button onClick={close} className="btn-primary text-xs">
                Get started
              </button>
            ) : (
              <button onClick={() => setStep((s) => s + 1)} className="btn-primary text-xs">
                Next
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export function relaunchOnboarding() {
  localStorage.removeItem(STORAGE_KEY)
  window.location.reload()
}
