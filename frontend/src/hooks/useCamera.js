import { useCallback, useEffect, useRef, useState } from 'react'

const CAMERA_KEY = 'pbs.cameraId'

function friendlyCameraError(error) {
  switch (error?.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Camera permission was denied. Allow camera access for this site in Chrome settings, then retry.'
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'No usable camera was found. Close other camera apps and retry.'
    case 'NotReadableError':
      return 'The camera is busy in another app. Close it and retry.'
    default:
      return error?.message || 'Could not start the camera.'
  }
}

export function useCamera() {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [devices, setDevices] = useState([])
  const [deviceId, setDeviceId] = useState(() => localStorage.getItem(CAMERA_KEY) || '')
  const [torchSupported, setTorchSupported] = useState(false)
  const [torchOn, setTorchOn] = useState(false)
  const [resolution, setResolution] = useState({ width: 0, height: 0 })

  const stopTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  const stop = useCallback(() => {
    stopTracks()
    setStatus('idle')
    setTorchOn(false)
  }, [stopTracks])

  const start = useCallback(
    async (requestedId = deviceId) => {
      setError(null)
      setTorchOn(false)

      if (!navigator.mediaDevices?.getUserMedia) {
        setStatus('unsupported')
        setError('This browser cannot open the camera. Use Chrome over HTTPS.')
        return
      }
      if (!window.isSecureContext) {
        setStatus('insecure')
        setError(
          'Camera access needs HTTPS on Android. Open the https:// address of the laptop, or use the native app.',
        )
        return
      }

      stopTracks()
      setStatus('starting')

      const size = { width: { ideal: 1920 }, height: { ideal: 1080 } }
      const attempts = []
      if (requestedId) {
        attempts.push({ video: { deviceId: { exact: requestedId }, ...size }, audio: false })
      } else {
        attempts.push({
          video: { facingMode: { ideal: 'environment' }, ...size },
          audio: false,
        })
      }
      attempts.push(
        { video: { facingMode: 'environment' }, audio: false },
        { video: true, audio: false },
      )

      let stream = null
      let lastError = null
      for (const constraints of attempts) {
        try {
          stream = await navigator.mediaDevices.getUserMedia(constraints)
          break
        } catch (err) {
          lastError = err
          if (err?.name === 'NotAllowedError' || err?.name === 'SecurityError') break
        }
      }

      if (!stream) {
        setStatus(
          lastError?.name === 'NotAllowedError' ? 'denied' : 'error',
        )
        setError(friendlyCameraError(lastError))
        return
      }

      streamRef.current = stream
      const video = videoRef.current
      if (video) {
        video.srcObject = stream
        try {
          await video.play()
        } catch {
          /* autoplay is muted+inline, this is only a warning */
        }
      }

      const track = stream.getVideoTracks()[0]
      try {
        const capabilities = track.getCapabilities?.() || {}
        if (capabilities.focusMode?.includes('continuous')) {
          await track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] })
        }
        setTorchSupported(Boolean(capabilities.torch))
      } catch {
        setTorchSupported(false)
      }

      setStatus('ready')
      setResolution({
        width: video?.videoWidth || 0,
        height: video?.videoHeight || 0,
      })

      try {
        const all = await navigator.mediaDevices.enumerateDevices()
        const cameras = all.filter((device) => device.kind === 'videoinput')
        setDevices(cameras)
        const activeId = track.getSettings?.().deviceId || requestedId
        if (activeId) {
          setDeviceId(activeId)
          localStorage.setItem(CAMERA_KEY, activeId)
        }
      } catch {
        /* device labels are optional */
      }
    },
    [deviceId, stopTracks],
  )

  const switchCamera = useCallback(
    async (nextId) => {
      setDeviceId(nextId)
      localStorage.setItem(CAMERA_KEY, nextId)
      await start(nextId)
    },
    [start],
  )

  const toggleTorch = useCallback(async () => {
    const track = streamRef.current?.getVideoTracks?.()[0]
    if (!track) return
    const next = !torchOn
    try {
      await track.applyConstraints({ advanced: [{ torch: next }] })
      setTorchOn(next)
    } catch {
      setError('This camera does not allow torch control in the browser.')
    }
  }, [torchOn])

  useEffect(() => {
    let cancelled = false
    const autoStart = async () => {
      try {
        const permission = await navigator.permissions?.query({ name: 'camera' })
        if (!cancelled && permission?.state === 'granted') start()
      } catch {
        /* Permission API is optional */
      }
    }
    autoStart()
    return () => {
      cancelled = true
      stopTracks()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return {
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
    clearError: () => setError(null),
  }
}
