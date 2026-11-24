// The guide frame is expressed as a fraction of the camera frame so the crop
// sent to the server is exactly what the user sees inside the overlay.
export const GUIDE = { x: 0.055, y: 0.36, w: 0.89, h: 0.2 }

export const QUALITY = {
  minSharpness: 7,
  minContrast: 8,
  minBrightness: 45,
  maxBrightness: 238,
  sameFrameBits: 4,
}

let scratch
function canvasContext(width, height) {
  if (!scratch) {
    scratch = document.createElement('canvas')
    scratch.width = 220
    scratch.height = 220
  }
  scratch.width = width
  scratch.height = height
  const ctx = scratch.getContext('2d', { willReadFrequently: true })
  ctx.imageSmoothingEnabled = true
  return ctx
}

export function cropRect(video) {
  const width = video.videoWidth
  const height = video.videoHeight
  if (!width || !height) return { sx: 0, sy: 0, sw: 0, sh: 0 }

  // The centered, object-fit: cover preview can clip the source on either axis.
  const viewWidth = video.clientWidth || width
  const viewHeight = video.clientHeight || height
  const scale = Math.max(viewWidth / width, viewHeight / height)
  const visibleWidth = viewWidth / scale
  const visibleHeight = viewHeight / scale
  return {
    sx: Math.round((width - visibleWidth) / 2 + visibleWidth * GUIDE.x),
    sy: Math.round((height - visibleHeight) / 2 + visibleHeight * GUIDE.y),
    sw: Math.round(visibleWidth * GUIDE.w),
    sh: Math.round(visibleHeight * GUIDE.h),
  }
}

function hex64(bits) {
  return bits.toString(16).padStart(16, '0')
}

/** Downscaled 8x8 average hash used to ignore repeated frames. */
function averageHash(ctx, width, height) {
  const size = 8
  const data = ctx.getImageData(0, 0, width, height).data
  const cells = new Float32Array(size * size)
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4
      const luma = 0.299 * data[index] + 0.587 * data[index + 1] + 0.114 * data[index + 2]
      const cx = Math.min(size - 1, Math.floor((x / width) * size))
      const cy = Math.min(size - 1, Math.floor((y / height) * size))
      cells[cy * size + cx] += luma
    }
  }
  const average = cells.reduce((sum, value) => sum + value, 0) / cells.length
  let bits = 0n
  cells.forEach((value, index) => {
    if (value > average) bits |= 1n << BigInt(index)
  })
  return hex64(bits)
}

export function hammingDistance(a, b) {
  if (!a || !b) return 64
  let diff = BigInt(`0x${a}`) ^ BigInt(`0x${b}`)
  let count = 0
  while (diff) {
    count += Number(diff & 1n)
    diff >>= 1n
  }
  return count
}

/** Measures sharpness/brightness of the guide crop and produces a frame hash. */
export function analyzeVideo(video) {
  const { sx, sy, sw, sh } = cropRect(video)
  if (!sw || !sh) return null

  const width = 180
  const height = Math.max(12, Math.round((sh / sw) * width))
  const ctx = canvasContext(width, height)
  ctx.drawImage(video, sx, sy, sw, sh, 0, 0, width, height)
  const { data } = ctx.getImageData(0, 0, width, height)

  let sum = 0
  let sumSquares = 0
  let laplacian = 0
  const count = width * height
  const luma = new Float32Array(count)
  for (let i = 0; i < count; i += 1) {
    const p = i * 4
    const value = 0.299 * data[p] + 0.587 * data[p + 1] + 0.114 * data[p + 2]
    luma[i] = value
    sum += value
    sumSquares += value * value
  }
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = y * width + x
      const center = luma[i] * 4 - luma[i - 1] - luma[i + 1] - luma[i - width] - luma[i + width]
      laplacian += Math.abs(center)
    }
  }
  const brightness = sum / count
  const variance = sumSquares / count - brightness * brightness
  const sharpness = laplacian / count

  const hash = averageHash(ctx, width, height)
  const ready =
    sharpness >= QUALITY.minSharpness &&
    variance >= QUALITY.minContrast ** 2 &&
    brightness >= QUALITY.minBrightness &&
    brightness <= QUALITY.maxBrightness

  return {
    brightness,
    contrast: Math.sqrt(Math.max(0, variance)),
    sharpness,
    ready,
    hash,
    hint: !ready
      ? brightness < QUALITY.minBrightness
        ? 'Too dark — add light'
        : sharpness < QUALITY.minSharpness
          ? 'Hold steady / move closer'
          : 'Fill the frame with the serial'
      : 'Ready',
  }
}

export function captureBlob(video, maxWidth = 1600, quality = 0.86) {
  const { sx, sy, sw, sh } = cropRect(video)
  const canvas = document.createElement('canvas')
  const width = Math.min(sw, maxWidth)
  canvas.width = width
  canvas.height = Math.max(1, Math.round((sh / sw) * width))
  const ctx = canvas.getContext('2d')
  ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Could not capture frame'))),
      'image/jpeg',
      quality,
    )
  })
}
