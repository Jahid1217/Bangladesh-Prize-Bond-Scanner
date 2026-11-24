import { BondIcon, CopyIcon, AlertIcon, BoltIcon, CameraIcon, SheetIcon } from './Icons.jsx'

const EMPTY = {
  total_unique: 0,
  total_scanned: 0,
  duplicate_attempts: 0,
  failed_ocr_attempts: 0,
  remaining: 2000,
  today_unique: 0,
  target: 2000,
  progress_percent: 0,
  uncertain_attempts: 0,
}

export default function StatsGrid({ stats }) {
  const data = stats || EMPTY
  const cards = [
    {
      label: 'Unique bonds',
      value: data.total_unique,
      icon: BondIcon,
      tone: 'accent',
      hint: `${data.progress_percent}% of ${data.target}`,
    },
    {
      label: 'Total scans',
      value: data.total_scanned,
      icon: CameraIcon,
      hint: `${data.today_unique} added today`,
    },
    {
      label: 'Duplicates',
      value: data.duplicate_attempts,
      icon: CopyIcon,
      tone: data.duplicate_attempts ? 'warn' : '',
      hint: 'Rejected attempts',
    },
    {
      label: 'Failed OCR',
      value: data.failed_ocr_attempts,
      icon: AlertIcon,
      tone: data.failed_ocr_attempts ? 'danger' : '',
      hint: data.uncertain_attempts
        ? `${data.uncertain_attempts} awaiting review`
        : 'Rescan or review',
    },
    {
      label: 'Remaining',
      value: data.remaining,
      icon: BoltIcon,
      hint: `Target ${data.target}`,
    },
    {
      label: 'Saved today',
      value: data.today_unique,
      icon: SheetIcon,
      hint: 'Unique entries',
    },
  ]

  return (
    <section className="stats" aria-label="Scan statistics">
      {cards.map(({ label, value, icon: Icon, tone = '', hint }) => (
        <article className={`stat-card ${tone}`} key={label}>
          <div className="stat-head">
            <span>{label}</span>
            <Icon />
          </div>
          <strong>{Number(value).toLocaleString()}</strong>
          <small>{hint}</small>
        </article>
      ))}
      <div className="progress-card" aria-label="Target progress">
        <div className="progress-label">
          <span>Target progress</span>
          <span>
            {data.total_unique.toLocaleString()} / {data.target.toLocaleString()}
          </span>
        </div>
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: `${Math.min(100, data.progress_percent || 0)}%` }}
          />
        </div>
      </div>
    </section>
  )
}
