import { useCallback, useEffect, useRef, useState } from 'react'
import { api, getServerUrl, isNativePlatform } from './api.js'
import CameraPanel from './components/CameraPanel.jsx'
import EditBondModal from './components/EditBondModal.jsx'
import EngineCard from './components/EngineCard.jsx'
import ExportPanel from './components/ExportPanel.jsx'
import { AlertIcon, BondIcon, CheckIcon, RefreshIcon, SettingsIcon, CopyIcon } from './components/Icons.jsx'
import ManualEntry from './components/ManualEntry.jsx'
import ScanHistory from './components/ScanHistory.jsx'
import SettingsModal from './components/SettingsModal.jsx'
import StatsGrid from './components/StatsGrid.jsx'

const TOAST_ICON = { success: CheckIcon, warning: CopyIcon, danger: AlertIcon }

export default function App() {
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [scans, setScans] = useState([])
  const [lastResult, setLastResult] = useState(null)
  const [review, setReview] = useState(null)
  const [editing, setEditing] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [offline, setOffline] = useState(false)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  const showToast = useCallback((type, message) => {
    setToast({ type, message })
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 3500)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [nextStats, nextHealth] = await Promise.all([api.stats(), api.health()])
      setStats(nextStats)
      setHealth(nextHealth)
      setOffline(false)
    } catch {
      setOffline(true)
    }
  }, [])

  const loadScans = useCallback(async () => {
    try {
      const data = await api.scans(12)
      setScans(data.items || [])
    } catch {
      /* history is non-critical */
    }
  }, [])

  useEffect(() => {
    refresh()
    loadScans()
    const timer = window.setInterval(refresh, 20000)
    return () => window.clearInterval(timer)
  }, [refresh, loadScans])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [refresh])

  useEffect(() => {
    if (isNativePlatform() && !getServerUrl()) setSettingsOpen(true)
    return () => window.clearTimeout(toastTimer.current)
  }, [])

  const handleResult = useCallback(
    (result) => {
      setLastResult(result)
      if (result.stats) setStats(result.stats)
      if (result.status === 'uncertain') {
        setReview({
          attemptId: result.attempt?.id,
          serial: result.serial || '',
          confidence: result.confidence,
          reason: result.reason,
          hasImage: Boolean(result.attempt?.image_path),
        })
      } else if (result.status === 'saved') {
        showToast('success', `Saved ${result.serial}`)
      } else if (result.status === 'duplicate') {
        showToast('warning', `${result.serial} is already saved`)
      }
      if (['saved', 'duplicate', 'uncertain', 'failed'].includes(result.status)) {
        loadScans()
      }
    },
    [loadScans, showToast],
  )

  const confirmReview = useCallback(
    async (serial) => {
      if (!review) return null
      try {
        const result = await api.createBond({
          serial,
          attempt_id: review.attemptId,
        })
        if (result.stats) setStats(result.stats)
        setReview(null)
        setLastResult((previous) =>
          previous
            ? { ...previous, status: result.status, serial, reason: null }
            : previous,
        )
        showToast(
          result.status === 'duplicate' ? 'warning' : 'success',
          result.status === 'duplicate'
            ? `${serial} is already saved`
            : `Saved ${serial}`,
        )
        loadScans()
        return null
      } catch (err) {
        if (err.status === 409) {
          return err.detail?.message || 'This serial is already recorded.'
        }
        return err.message
      }
    },
    [review, loadScans, showToast],
  )

  const manualSave = useCallback(
    async (serial, note) => {
      try {
        const result = await api.createBond({ serial, note: note || null })
        if (result.stats) setStats(result.stats)
        showToast('success', `Saved ${result.serial}`)
        loadScans()
        return null
      } catch (err) {
        if (err.status === 409) {
          return err.detail?.message || 'This serial is already recorded.'
        }
        return err.message
      }
    },
    [loadScans, showToast],
  )

  const saveEdit = useCallback(
    async (id, serial, note) => {
      try {
        await api.updateBond(id, {
          ...(note !== undefined ? { note } : {}),
          serial,
        })
        setEditing(null)
        showToast('success', 'Serial corrected')
        refresh()
        loadScans()
        return null
      } catch (err) {
        if (err.status === 409) {
          return err.detail?.message || 'That serial already exists.'
        }
        return err.message
      }
    },
    [loadScans, refresh, showToast],
  )

  const statusLabel = offline
    ? 'Backend offline'
    : !health
      ? 'Connecting…'
      : health.ocr?.available
        ? 'Scanning ready'
        : 'OCR unavailable'

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">
            <BondIcon width={22} height={22} />
          </span>
          <div>
            <h1>Prize Bond Scanner</h1>
            <p>Bangladesh 100 Taka · local-first</p>
          </div>
        </div>
        <div className="header-actions">
          <span
            className={`backend-pill ${offline ? 'offline' : health?.ocr?.available ? 'online' : 'warn'}`}
          >
            <span className="dot" />
            {statusLabel}
          </span>
          <button
            className="icon-btn"
            onClick={() => setSettingsOpen(true)}
            aria-label="Open settings"
          >
            <SettingsIcon />
          </button>
        </div>
      </header>

      {offline && (
        <div className="offline-banner">
          <AlertIcon />
          <span>Cannot reach the laptop backend. Check Wi-Fi and the server address.</span>
          <button className="btn ghost small" onClick={refresh}>
            <RefreshIcon /> Retry
          </button>
        </div>
      )}

      <StatsGrid stats={stats} />

      <main className="workspace">
        <CameraPanel
          lastResult={lastResult}
          review={review}
          paused={Boolean(review)}
          onResult={handleResult}
          onConfirmReview={confirmReview}
          onDismissReview={() => setReview(null)}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        <aside className="sidebar">
          <ManualEntry onSave={manualSave} />
          <ExportPanel stats={stats} disabled={offline} />
          <ScanHistory
            items={scans}
            onEdit={(item) =>
              setEditing({
                id: item.bond_id,
                serial: item.bond_serial || item.serial,
              })
            }
          />
          <EngineCard health={health} offline={offline} />
        </aside>
      </main>

      <footer className="app-footer">
        <span>Works offline on your Wi-Fi · data stays in SQLite on the laptop.</span>
        <span>Target {stats?.target?.toLocaleString() || '2,000'} bonds</span>
      </footer>

      {editing && (
        <EditBondModal
          bond={editing}
          onClose={() => setEditing(null)}
          onSave={saveEdit}
        />
      )}
      {settingsOpen && (
        <SettingsModal
          health={health}
          offline={offline}
          onClose={() => setSettingsOpen(false)}
          onSaved={() => {
            setOffline(false)
            refresh()
          }}
        />
      )}

      {toast && (
        <div className={`toast ${toast.type}`} role="status">
          {(() => {
            const Icon = TOAST_ICON[toast.type] || CheckIcon
            return <Icon />
          })()}
          <span>{toast.message}</span>
          <button className="toast-close" onClick={() => setToast(null)} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}
    </div>
  )
}
