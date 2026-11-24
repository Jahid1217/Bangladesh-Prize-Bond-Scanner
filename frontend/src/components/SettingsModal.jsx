import { useState } from 'react'
import { getServerUrl, setServerUrl } from '../api.js'
import { XIcon } from './Icons.jsx'

export default function SettingsModal({ health, offline, onClose, onSaved }) {
  const [url, setUrl] = useState(getServerUrl())
  const [status, setStatus] = useState(null)
  const [testing, setTesting] = useState(false)

  const test = async () => {
    setTesting(true)
    setStatus(null)
    try {
      const response = await fetch(`${url.trim().replace(/\/+$/, '')}/api/health`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const body = await response.json()
      setStatus({
        ok: true,
        text: `Connected. OCR ${body.ocr.available ? 'ready' : 'unavailable'} · ${body.database.bonds} bonds`,
      })
    } catch (err) {
      setStatus({ ok: false, text: err.message || 'Connection failed' })
    } finally {
      setTesting(false)
    }
  }

  const save = () => {
    setServerUrl(url)
    onSaved()
    onClose()
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose} role="presentation">
      <div
        className="modal"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        <div className="modal-head">
          <div>
            <h2 id="settings-title">Settings &amp; diagnostics</h2>
            <p className="muted">Local network configuration</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <XIcon />
          </button>
        </div>

        <div className="stack">
          <label htmlFor="server-url">Backend address</label>
          <input
            id="server-url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="http://192.168.0.10:8000"
            spellCheck={false}
          />
          <p className="hint">
            Leave empty when the dashboard is served by the backend. Set it for the
            Android app or a separately hosted frontend, e.g.
            <code> https://192.168.0.10:8443</code>.
          </p>
          <div className="button-row">
            <button className="btn" onClick={test} disabled={testing}>
              {testing ? 'Testing…' : 'Test connection'}
            </button>
            <button className="btn primary" onClick={save}>
              Save
            </button>
          </div>
          {status && (
            <div className={status.ok ? 'field-ok' : 'field-error'}>{status.text}</div>
          )}
        </div>

        <dl className="engine-list settings-details">
          <div>
            <dt>Backend</dt>
            <dd>{offline ? 'Offline' : health ? 'Connected' : 'Unknown'}</dd>
          </div>
          <div>
            <dt>OCR languages</dt>
            <dd>{health?.ocr?.active_languages || '—'}</dd>
          </div>
          <div>
            <dt>OCR command</dt>
            <dd className="mono ellipsis" title={health?.ocr?.command}>
              {health?.ocr?.command || '—'}
            </dd>
          </div>
          <div>
            <dt>Serial pattern</dt>
            <dd className="mono">{health?.config?.serial_pattern || '—'}</dd>
          </div>
          <div>
            <dt>Target</dt>
            <dd>{health?.config?.target ?? '—'} bonds</dd>
          </div>
          <div>
            <dt>Database</dt>
            <dd className="mono ellipsis" title={health?.database?.path}>
              {health?.database?.path || '—'}
            </dd>
          </div>
        </dl>
        <p className="hint">
          Camera access on Android requires HTTPS. Run
          <code> ./scripts/generate_cert.sh</code> then
          <code> python backend/run.py --ssl</code>.
        </p>
      </div>
    </div>
  )
}
