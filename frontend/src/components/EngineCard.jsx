export default function EngineCard({ health, offline }) {
  const ocr = health?.ocr
  const config = health?.config
  return (
    <section className="panel compact engine-card">
      <div className="panel-head">
        <div>
          <h2>Engine</h2>
          <p className="muted">Local OCR &amp; storage</p>
        </div>
        <span className={`tiny-dot ${offline ? 'off' : ocr?.available ? 'on' : 'warn'}`} />
      </div>
      <dl className="engine-list">
        <div>
          <dt>OCR</dt>
          <dd>
            {offline
              ? 'Backend unreachable'
              : ocr?.available
                ? `Tesseract ${ocr.version || ''}`
                : ocr?.error || 'Unavailable'}
          </dd>
        </div>
        <div>
          <dt>Languages</dt>
          <dd>{ocr?.active_languages || '—'}</dd>
        </div>
        <div>
          <dt>Auto-save at</dt>
          <dd>{config ? `${config.auto_save_confidence}% confidence` : '—'}</dd>
        </div>
        <div>
          <dt>Database</dt>
          <dd className="mono ellipsis" title={health?.database?.path}>
            {health?.database?.path || '—'}
          </dd>
        </div>
        <div>
          <dt>Timezone</dt>
          <dd>{config?.timezone || 'Asia/Dhaka'}</dd>
        </div>
      </dl>
      <p className="hint">
        Uncertain reads are never saved automatically. Confirm them in the camera
        panel.
      </p>
    </section>
  )
}
