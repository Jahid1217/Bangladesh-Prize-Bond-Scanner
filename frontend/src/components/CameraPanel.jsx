import { useCallback, useEffect, useRef, useState } from 'react'
import { api, imageUrl, isNativePlatform } from '../api.js'
import { useCamera } from '../hooks/useCamera.js'
import {
  GUIDE,
  QUALITY,
  analyzeVideo,
  captureBlob,
  hammingDistance,
} from '../lib/quality.js'
import { captureNativePhoto } from '../lib/nativeCamera.js'
import {
  AlertIcon,
  BoltIcon,
  CameraIcon,
  CheckIcon,
  CopyIcon,
  RefreshIcon,
} from './Icons.jsx'
import ReviewCard from './ReviewCard.jsx'

const AUTO_KEY = 'pbs.autoScan'

const RESULT_META = {
  saved: { label: 'Saved', tone: 'success', icon: CheckIcon },
  duplicate: { label: 'Duplicate', tone: 'warn', icon: CopyIcon },
  uncertain: { label: 'Needs review', tone: 'warn', icon: AlertIcon },
  failed: { label: 'No serial found', tone: 'danger', icon: AlertIcon },
}

function ResultStrip({ result }) {
  if (!result) {
    return (
      <div className="last-result empty">
        <div className="result-icon">
          <CameraIcon />
        </div>
        <div className="result-main">
          <span className="result-label">Last detected serial</span>
          <strong className="result-serial">—</strong>
          <small>Point the guide at the serial number to begin.</small>
        </div>
      </div>
    )
  }
  const meta = RESULT_META[result.status] || RESULT_META.failed
  const Icon = meta.icon
  const detail = result.status === 'failed' || result.confidence == null
    ? result.reason || 'Adjust the bond and try again'
    : `${Math.round(result.confidence)}% confidence`

  return (
    <div className={`last-result ${meta.tone}`}>
      <div className="result-icon">
        <Icon />
      </div>
      <div className="result-main">
        <span className="result-label">
          Last scan · {meta.label}
          {result.ocr_status === 'skipped' ? ' · ignored repeat frame' : ''}
        </span>
        <strong className="result-serial">{result.serial || '—'}</strong>
        <small>{detail}</small>
      </div>
      {result.attempt?.image_path && (
        <a
          className="btn ghost small"
          href={imageUrl(result.attempt.id)}
          target="_blank"
          rel="noreferrer"
        >
          View frame
        </a>
      )}
    </div>
  )
}

export default function CameraPanel({
  lastResult,
  review,
  paused,
  onResult,
  onConfirmReview,
  onDismissReview,
  onOpenSettings,
}) {
  const native = isNativePlatform()
  const {
    videoRef,
    status,
    error,
    devices,
    deviceId,
    resolution,
    torchSupported,
    torchOn,
    start,
    stop,
    switchCamera,
    toggleTorch,
    clearError,
  } = useCamera()

  const [autoScan, setAutoScan] = useState(
    () => localStorage.getItem(AUTO_KEY) !== 'false',
  )
  const [busy, setBusy] = useState(false)
  const [quality, setQuality] = useState(null)
  const [notice, setNotice] = useState(null)
  const [liveSize, setLiveSize] = useState({ width: 0, height: 0 })
  const [failedFrame, setFailedFrame] = useState(null)
  const [failedFrameUrl, setFailedFrameUrl] = useState(null)
  const fileInputRef = useRef(null)

  const busyRef = useRef(false)
  const lastHashRef = useRef(null)
  const lastHashAtRef = useRef(0)
  const cooldownRef = useRef(0)

  useEffect(() => {
    if (!failedFrame) {
      setFailedFrameUrl(null)
      return undefined
    }
    const url = URL.createObjectURL(failedFrame)
    setFailedFrameUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [failedFrame])

  const upload = useCallback(
    async (blob) => {
      if (busyRef.current) return
      busyRef.current = true
      setBusy(true)
      setNotice(null)
      try {
        const result = await api.scan(blob)
        if (result.status !== 'skipped') {
          setFailedFrame(result.status === 'failed' ? blob : null)
          onResult(result)
        }
        cooldownRef.current =
          Date.now() + (result.status === 'saved' || result.status === 'duplicate' ? 1600 : 900)
      } catch (err) {
        setNotice(err.message)
        cooldownRef.current = Date.now() + 2500
      } finally {
        busyRef.current = false
        setBusy(false)
      }
    },
    [onResult],
  )

  const pickPhoto = useCallback(async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    try {
      await upload(file)
    } catch (err) {
      setNotice(err.message)
    }
  }, [upload])

  const manualCapture = useCallback(async () => {
    const video = videoRef.current
    if (!video || status !== 'ready' || review) return
    try {
      const blob = await captureBlob(video)
      await upload(blob)
    } catch (err) {
      setNotice(err.message)
    }
  }, [videoRef, status, review, upload])

  const nativeCapture = useCallback(async () => {
    try {
      const blob = await captureNativePhoto()
      await upload(blob)
    } catch (err) {
      setNotice(err.message || 'Native camera is not available.')
    }
  }, [upload])

  useEffect(() => {
    if (status !== 'ready') {
      setQuality(null)
      return undefined
    }
    const tick = async () => {
      const video = videoRef.current
      if (!video || video.readyState < 2) return
      const next = analyzeVideo(video)
      setQuality(next)
      if (!autoScan || paused || busyRef.current) return
      if (Date.now() < cooldownRef.current) return
      if (!next?.ready) return
      const distance = hammingDistance(next.hash, lastHashRef.current)
      if (distance <= QUALITY.sameFrameBits && Date.now() - lastHashAtRef.current < 5000) {
        return
      }
      lastHashRef.current = next.hash
      lastHashAtRef.current = Date.now()
      try {
        const blob = await captureBlob(video)
        await upload(blob)
      } catch (err) {
        setNotice(err.message)
      }
    }
    tick()
    const timer = setInterval(tick, 750)
    return () => clearInterval(timer)
  }, [status, autoScan, paused, upload, videoRef])

  const toggleAuto = () => {
    const next = !autoScan
    setAutoScan(next)
    localStorage.setItem(AUTO_KEY, String(next))
  }

  const activeCameras = devices.filter((device) => device.kind === 'videoinput')
  const ratio =
    liveSize.width && liveSize.height
      ? `${liveSize.width} / ${liveSize.height}`
      : resolution.width && resolution.height
        ? `${resolution.width} / ${resolution.height}`
        : '4 / 3'

  const liveHint = quality?.hint || 'Point the guide at the serial number'
  const sharpness = Math.min(100, Math.round(((quality?.sharpness || 0) / 30) * 100))

  return (
    <section className="panel camera-panel">
      <div className="panel-head">
        <div>
          <h2>Camera scanner</h2>
          <p className="muted">Rear camera · serial guide</p>
        </div>
        <span className={`scan-state ${autoScan && !paused ? 'active' : ''}`}>
          <span className="dot" />
          {review
            ? 'Review paused'
            : autoScan
              ? paused
                ? 'Paused'
                : 'Auto'
              : 'Manual'}
        </span>
      </div>

      {native ? (
        <div className="native-camera">
          <div className="native-visual">
            <CameraIcon width={34} height={34} />
            <span>Native Android camera</span>
          </div>
          <p className="muted">
            Capture a photo of the serial. For continuous live scanning, open the
            HTTPS address of the laptop in Chrome.
          </p>
          <button
            className="btn primary block"
            onClick={nativeCapture}
            disabled={busy || Boolean(review)}
          >
            <CameraIcon /> {busy ? 'Scanning…' : 'Capture bond photo'}
          </button>
        </div>
      ) : status === 'insecure' || status === 'unsupported' ? (
        <div className="camera-message">
          <AlertIcon width={28} height={28} />
          <h3>Camera blocked by the browser</h3>
          <p>{error}</p>
          <div className="button-row">
            <button className="btn primary" onClick={() => start()}>
              <RefreshIcon /> Retry
            </button>
            <button className="btn ghost" onClick={() => fileInputRef.current?.click()}>
              <CameraIcon /> Take photo instead
            </button>
            <button className="btn ghost" onClick={onOpenSettings}>
              Server settings
            </button>
          </div>
          {!window.isSecureContext && (
            <p className="hint">
              Open the HTTPS address printed by the backend, accept the certificate,
              then allow camera access.
            </p>
          )}
        </div>
      ) : status === 'denied' || status === 'error' ? (
        <div className="camera-message">
          <AlertIcon width={28} height={28} />
          <h3>Camera unavailable</h3>
          <p>{error}</p>
          <div className="button-row">
            <button
              className="btn primary"
              onClick={() => {
                clearError()
                start()
              }}
            >
              <RefreshIcon /> Try again
            </button>
            <button className="btn ghost" onClick={() => fileInputRef.current?.click()}>
              <CameraIcon /> Take photo instead
            </button>
            <button className="btn ghost" onClick={onOpenSettings}>
              Server settings
            </button>
          </div>
        </div>
      ) : status === 'idle' ? (
        <div className="camera-message">
          <CameraIcon width={30} height={30} />
          <h3>Camera is off</h3>
          <p>Start the rear camera, then hold the bond serial inside the guide.</p>
          <button className="btn primary" onClick={() => start()}>
            <CameraIcon /> Start camera
          </button>
        </div>
      ) : (
        <div className="camera-viewport" style={{ aspectRatio: ratio }}>
          <video
            ref={videoRef}
            className="camera-video"
            muted
            playsInline
            autoPlay
            onLoadedMetadata={(event) =>
              setLiveSize({
                width: event.currentTarget.videoWidth,
                height: event.currentTarget.videoHeight,
              })
            }
          />
          {status === 'starting' && (
            <div className="camera-loading">Starting camera…</div>
          )}
          <div
            className="guide-frame"
            style={{
              left: `${GUIDE.x * 100}%`,
              top: `${GUIDE.y * 100}%`,
              width: `${GUIDE.w * 100}%`,
              height: `${GUIDE.h * 100}%`,
            }}
          >
            <span className="corner tl" />
            <span className="corner tr" />
            <span className="corner bl" />
            <span className="corner br" />
            <span className="guide-label">Serial letters and digits</span>
          </div>
          <div className="camera-hud">
            <span className={`live-pill ${autoScan && !paused ? 'on' : ''}`}>
              <span className="dot" />
              {busy ? 'Reading…' : autoScan && !paused ? 'Auto scanning' : 'Paused'}
            </span>
            <span className={`quality-pill ${quality?.ready ? 'ok' : ''}`}>
              {quality?.ready ? 'Ready' : liveHint}
            </span>
          </div>
          <div className="camera-footer">
            <div className="quality-bar">
              <div
                className={`quality-fill ${quality?.ready ? 'ok' : ''}`}
                style={{ width: `${sharpness}%` }}
              />
            </div>
            <span>{liveHint}</span>
          </div>
        </div>
      )}

      {!native && status === 'ready' && (
        <div className="camera-controls">
          <button
            className={`auto-switch ${autoScan ? 'on' : ''}`}
            onClick={toggleAuto}
            aria-pressed={autoScan}
          >
            <span className="switch"><span /></span>
            <BoltIcon /> Auto scan
          </button>
          <button
            className="btn primary"
            onClick={manualCapture}
            disabled={busy || Boolean(review)}
          >
            <CameraIcon /> {busy ? 'Reading…' : 'Capture now'}
          </button>
          {torchSupported && (
            <button
              className={`btn ghost ${torchOn ? 'active' : ''}`}
              onClick={toggleTorch}
              title="Toggle torch"
            >
              Light
            </button>
          )}
          {activeCameras.length > 1 && (
            <select
              className="camera-select"
              value={deviceId}
              onChange={(event) => switchCamera(event.target.value)}
              aria-label="Camera"
            >
              {activeCameras.map((device, index) => (
                <option value={device.deviceId} key={device.deviceId || index}>
                  {device.label || `Camera ${index + 1}`}
                </option>
              ))}
            </select>
          )}
          <button className="btn ghost" onClick={stop}>
            Stop
          </button>
        </div>
      )}

      {(notice || (error && status === 'ready')) && (
        <div className="inline-alert">
          <AlertIcon /> {notice || error}
        </div>
      )}

      <ResultStrip result={lastResult} />

      {lastResult?.status === 'failed' && failedFrameUrl && (
        <details className="failed-frame">
          <summary>View failed frame</summary>
          <img src={failedFrameUrl} alt="Camera image sent to the scanner" />
          {lastResult?.raw_text && (
            <p className="ocr-raw">
              OCR read: <code>{lastResult.raw_text}</code>
            </p>
          )}
          <a className="btn ghost small" href={failedFrameUrl} download="failed-serial-frame">
            Download frame
          </a>
        </details>
      )}

      <ReviewCard
        review={review}
        onConfirm={onConfirmReview}
        onDismiss={onDismissReview}
      />

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="visually-hidden"
        onChange={pickPhoto}
      />

      <p className="camera-tip">
        Fill the guide with the printed serial. Hold steady for a moment — clear
        frames save automatically; unsure reads wait for confirmation.
      </p>
    </section>
  )
}
