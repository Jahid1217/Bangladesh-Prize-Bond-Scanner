import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { XIcon } from './Icons.jsx'

export default function EditBondModal({ bond, onClose, onSave }) {
  const showNote = bond?.note !== undefined
  const [serial, setSerial] = useState(bond?.serial || '')
  const [note, setNote] = useState(bond?.note || '')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState([])

  useEffect(() => {
    setSerial(bond?.serial || '')
    setNote(bond?.note || '')
    setError(null)
    if (!bond?.id) return
    api
      .corrections(bond.id)
      .then((data) => setHistory(data.items || []))
      .catch(() => setHistory([]))
  }, [bond])

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!bond) return null

  const submit = async (event) => {
    event.preventDefault()
    if (!serial.trim() || busy) return
    setBusy(true)
    setError(null)
    const failure = await onSave(
      bond.id,
      serial.trim(),
      showNote ? note.trim() : undefined,
    )
    setBusy(false)
    if (failure) setError(failure)
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose} role="presentation">
      <div
        className="modal"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-title"
      >
        <div className="modal-head">
          <div>
            <h2 id="edit-title">Correct serial</h2>
            <p className="muted">Every change is recorded in the correction history.</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <XIcon />
          </button>
        </div>
        <form className="stack" onSubmit={submit}>
          <label htmlFor="edit-serial">Serial number</label>
          <input
            id="edit-serial"
            value={serial}
            onChange={(event) => setSerial(event.target.value)}
            inputMode="numeric"
            autoFocus
            disabled={busy}
          />
          {showNote && (
            <>
              <label htmlFor="edit-note">Note</label>
              <input
                id="edit-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                maxLength={200}
                disabled={busy}
              />
            </>
          )}
          {error && <div className="field-error">{error}</div>}
          <div className="modal-actions">
            <button className="btn ghost" type="button" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button className="btn primary" type="submit" disabled={busy || !serial.trim()}>
              {busy ? 'Saving…' : 'Save correction'}
            </button>
          </div>
        </form>
        {history.length > 0 && (
          <div className="correction-history">
            <h3>Correction history</h3>
            <ul>
              {history.map((item) => (
                <li key={item.id}>
                  <span className="mono">{item.old_serial}</span>
                  <span aria-hidden>→</span>
                  <span className="mono">{item.new_serial}</span>
                  <time>{new Date(item.corrected_at).toLocaleString()}</time>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
