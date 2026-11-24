import { AlertIcon, CheckIcon, CopyIcon, EditIcon } from './Icons.jsx'

const STATUS = {
  saved: { label: 'Saved', icon: CheckIcon, tone: 'success' },
  duplicate: { label: 'Duplicate', icon: CopyIcon, tone: 'warn' },
  uncertain: { label: 'Review', icon: AlertIcon, tone: 'warn' },
  failed: { label: 'Failed', icon: AlertIcon, tone: 'danger' },
}

function when(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const today = new Date()
  const sameDay =
    date.getDate() === today.getDate() &&
    date.getMonth() === today.getMonth() &&
    date.getFullYear() === today.getFullYear()
  return sameDay
    ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
        ' ' +
        date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function ScanHistory({ items, onEdit }) {
  return (
    <section className="panel compact history-panel">
      <div className="panel-head">
        <div>
          <h2>Recent scans</h2>
          <p className="muted">Latest camera reads</p>
        </div>
      </div>
      {!items?.length ? (
        <p className="empty-note">No scans yet. Start the camera to record bonds.</p>
      ) : (
        <ul className="history-list">
          {items.map((item) => {
            const meta = STATUS[item.status] || STATUS.failed
            const Icon = meta.icon
            return (
              <li className={`history-row ${meta.tone}`} key={item.id}>
                <span className="history-icon">
                  <Icon />
                </span>
                <div className="history-main">
                  <div className="history-top">
                    <strong>{item.serial || 'No serial'}</strong>
                    <span>{when(item.created_at)}</span>
                  </div>
                  <div className="history-sub">
                    <span>{meta.label}</span>
                    {item.confidence != null && <span>{Math.round(item.confidence)}%</span>}
                    {item.reason && <span className="reason">{item.reason}</span>}
                  </div>
                </div>
                {item.bond_id && (
                  <button
                    className="icon-btn small"
                    onClick={() =>
                      onEdit({ id: item.bond_id, serial: item.serial, note: '' })
                    }
                    aria-label={`Edit ${item.serial}`}
                    title="Edit serial"
                  >
                    <EditIcon />
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
