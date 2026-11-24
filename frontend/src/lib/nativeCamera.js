/** Capacitor native camera adapter (used only inside the Android shell). */
export async function captureNativePhoto() {
  const { Camera, CameraResultType, CameraSource } = await import('@capacitor/camera')
  const photo = await Camera.getPhoto({
    quality: 92,
    width: 1800,
    allowEditing: false,
    resultType: CameraResultType.Base64,
    source: CameraSource.Camera,
    saveToGallery: false,
  })
  if (!photo.base64String) throw new Error('Camera returned no image')
  const binary = atob(photo.base64String)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return new Blob([bytes], { type: `image/${photo.format || 'jpeg'}` })
}
