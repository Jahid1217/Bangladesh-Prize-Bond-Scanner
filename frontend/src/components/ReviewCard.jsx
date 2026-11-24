import { useEffect, useState } from 'react'
import { AlertIcon, CheckIcon, XIcon } from './Icons.jsx'
import { imageUrl } from '../api.js'

export default function ReviewCard({ review, onConfirm, onDismiss }) {
  const [serial, setSerial] = useState(review?.serial || '')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setSerial(review?.serial || '')
    setError(null)
  }, [review])

  if (!review) return null

  const submit = async (event) => {
    event.preventDefault()
    if (!serial.trim() || busy) return
    setBusy(true)
    setError(null)
    const failure = await onConfirm(serial.trim())
    setBusy(false)
    if (failure) setError(failure)
  }

  return (
    <form className="review-card" onSubmit={submit}>
      <div className="review-head">
        <span className="review-badge">
          <AlertIcon /> Needs review
        </span>
        {review.confidence != null && (
          <span className="muted">{Math.round(review.confidence)}% confidence</span>
        )}
      </div>
      <p className="review-text">
        {review.reason || 'The OCR result was not clear enough to save automatically.'}
      </p>
      <div className="review-body">
        {review.hasImage && (
          <a
            className="review-shot"
            href={imageUrl(review.attemptId)}
            target="_blank"
            rel="noreferrer"
            title="Open captured frame"
          >
            <img src={imageUrl(review.attemptId)} alt="Captured serial" />
          </a>
        )}
        <div className="review-fields">
          <label htmlFor="review-serial">Serial number</label>
          <input
            id="review-serial"
            value={serial}
            onChange={(event) => setSerial(event.target.value)}
            inputMode="numeric"
            autoComplete="off"
            placeholder="e.g. 0786345"
            disabled={busy}
          />
          {error && <div className="field-error">{error}</div>}
          <div className="review-actions">
            <button className="btn primary" type="submit" disabled={busy || !serial.trim()}>
              <CheckIcon /> {busy ? 'Saving…' : 'Save serial'}
            </button>
            <button className="btn ghost" type="button" onClick={onDismiss} disabled={busy}>
              <XIcon /> Discard
            </button>
          </div>
        </div>
      </div>
      <p className="hint">Auto scanning is paused until this read is saved or discarded.</p>
    </form>
  )
}
