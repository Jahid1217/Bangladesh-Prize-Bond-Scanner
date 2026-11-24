import { DownloadIcon, SheetIcon } from './Icons.jsx'
import { exportUrl } from '../api.js'

export default function ExportPanel({ stats, disabled }) {
  const count = stats?.total_unique ?? 0

  return (
    <section className="panel compact">
      <div className="panel-head">
        <div>
          <h2>Export database</h2>
          <p className="muted">{count.toLocaleString()} unique serials</p>
        </div>
        <SheetIcon />
      </div>
      <div className="export-list">
        <a
          className={`btn primary block ${disabled ? 'disabled' : ''}`}
          href={disabled ? undefined : exportUrl.xlsx()}
          target="_blank"
          rel="noreferrer"
        >
          <DownloadIcon /> Download Excel (.xlsx)
        </a>
        <a
          className={`btn block ${disabled ? 'disabled' : ''}`}
          href={disabled ? undefined : exportUrl.csv()}
          target="_blank"
          rel="noreferrer"
        >
          <DownloadIcon /> Download CSV
        </a>
      </div>
      <p className="hint">
        Includes serial, Bangla digits, scan time, source and confidence. Files
        are also stored in the laptop&apos;s <code>exports/</code> folder.
      </p>
    </section>
  )
}
