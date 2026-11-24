import { useState } from 'react'
import { BondIcon } from './Icons.jsx'

export default function ManualEntry({ onSave }) {
  const [serial, setSerial] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  const submit = async (event) => {
    event.preventDefault()
    if (!serial.trim() || busy) return
    setBusy(true)
    setMessage(null)
    const error = await onSave(serial.trim(), note.trim())
    setBusy(false)
    if (error) {
      setMessage({ type: 'error', text: error })
      return
    }
    setSerial('')
    setNote('')
    setMessage({ type: 'ok', text: 'Serial saved' })
  }

  return (
    <section className="panel compact">
      <div className="panel-head">
        <div>
          <h2>Manual entry</h2>
          <p className="muted">Correction or typed serial</p>
        </div>
        <BondIcon />
      </div>
      <form className="stack" onSubmit={submit}>
        <label htmlFor="manual-serial">Serial number</label>
        <input
          id="manual-serial"
          value={serial}
          onChange={(event) => setSerial(event.target.value)}
          placeholder="0786345"
          inputMode="numeric"
          autoComplete="off"
          disabled={busy}
        />
        <label htmlFor="manual-note">Note (optional)</label>
        <input
          id="manual-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Owner / bundle"
          maxLength={200}
          disabled={busy}
        />
        {message && (
          <div className={message.type === 'error' ? 'field-error' : 'field-ok'}>
            {message.text}
          </div>
        )}
        <button className="btn primary block" disabled={busy || !serial.trim()}>
          {busy ? 'Saving…' : 'Add serial'}
        </button>
      </form>
    </section>
  )
}
