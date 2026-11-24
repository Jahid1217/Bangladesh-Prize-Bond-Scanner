# Camera and Android setup

## Why HTTPS is required

Chrome (and every modern browser) allows `navigator.mediaDevices.getUserMedia`
only in a **secure context**:

- `https://...` — yes
- `http://localhost` — yes (laptop only)
- `http://192.168.x.x` — **no**, the promise is rejected / API is hidden

That is why the project serves the dashboard over HTTPS with a self-signed
certificate for the phone. This is the recommended path and gives true live
automatic scanning on the Vivo V21.

## Vivo V21 steps (browser mode)

1. Connect the phone and laptop to the same Wi-Fi.
2. On the laptop:
   ```bash
   ./scripts/generate_cert.sh
   ./scripts/start.sh --ssl
   ```
3. Note the `Phone:` URL, e.g. `https://192.168.1.12:8443`.
4. Open it in **Chrome** on the phone.
5. Certificate warning → **Advanced** → **Proceed to 192.168.1.12 (unsafe)**.
   The connection is still encrypted; the warning only says the certificate is
   not signed by a public CA.
6. Tap **Start camera** → **Allow**.
7. Hold the bond so the printed serial sits inside the dashed guide.

The browser remembers the permission for that origin. If it was denied:

Chrome ⋮ → Settings → Site settings → Camera → find the laptop address → Allow,
then reload the dashboard.

### Better than a warning: mkcert

If you want no warning (and trust for a Capacitor WebView), install a local CA:

```bash
sudo apt install mkcert libnss3-tools
mkcert -install
cd certs
mkcert -cert-file server.crt -key-file server.key <laptop-ip> localhost 127.0.0.1
```

Install the generated root CA (`mkcert -CAROOT` → `rootCA.pem`) on the phone
(Settings → Security → Encryption & credentials → Install a certificate → CA
certificate). Then start the server with `--ssl` as usual.

## Autofocus, light and framing

- The Vivo V21 rear camera autofocuses automatically. Web pages cannot tap-to-
  focus, so keep the phone 15–25 cm away and let it settle.
- Avoid direct glare on the glossy bond. Slight angle + diffuse room light is
  best. The torch button appears if the browser exposes torch control.
- The serial guide is 20% of the frame height. Fill it with the printed serial
  line; do not include the denomination or large blank areas.
- The dashboard shows a sharpness bar and a hint ("Hold steady", "Too dark").
  Frames below the quality gate are not uploaded.
- Use **Auto scan** for batches. It checks a frame every 750 ms, skips repeated
  images, and pauses automatically when a read needs review.
- A bond must leave the guide before it can be scanned again; identical frames
  are ignored for 5 seconds on the phone and 2.5 seconds on the server.

## Review and duplicate behaviour

- Green result → saved automatically.
- Amber "Needs review" → the OCR was not confident enough. Correct the serial in
  the card and save, or discard. **Nothing uncertain is written as a bond.**
- Amber "Duplicate" → the serial already exists; the attempt is counted in the
  dashboard but no second row is created.
- Red "No serial found" → the frame had no valid 7-digit serial. Move closer or
  improve lighting.

## Capacitor Android shell (optional)

Use this if browser camera access is unreliable on your device, or you want an
installable APK. The shell loads the same React UI and talks to the laptop API.

### What is included

- `frontend/capacitor.config.json` (app id `bd.prizebond.scanner`, `webDir: dist`)
- `frontend/src/lib/nativeCamera.js` — uses `@capacitor/camera` for a native
  single-shot photo and sends it to the same OCR endpoint
- UI automatically switches to a "Capture bond photo" panel when it detects
  `Capacitor.isNativePlatform()`

The native camera plugin opens the system camera for each shot; it does **not**
provide the live preview/auto-capture loop. For continuous scanning, use the
browser HTTPS mode. For a native live preview you can add
`@capacitor-community/camera-preview` and call `captureSample()` from an
interval; the backend and UI do not need changes.

### Build

```bash
cd frontend
npm install
npm install @capacitor/android
npx cap add android
npm run build
npx cap sync android
npx cap open android
```

Build the APK in Android Studio (Build → Build Bundle(s)/APK(s) → Build APK),
or:

```bash
cd android && ./gradlew assembleDebug
```

### Pointing the app at the laptop

On first launch the app opens Settings because no backend URL is known. Enter:

```
https://192.168.1.12:8443
```

The value is stored in `localStorage`. Android WebView does not allow bypassing
an untrusted certificate, so either:

1. use a `mkcert` certificate and install the CA on the phone (recommended), or
2. use an HTTP backend and enable cleartext traffic:
   - `frontend/capacitor.config.json` already sets
     `android.allowMixedContent: true`
   - add `android:usesCleartextTraffic="true"` to the `<application>` tag in
     `android/app/src/main/AndroidManifest.xml`
   - enter `http://192.168.1.12:8000` in Settings

Cleartext sends the serials unencrypted on your LAN; HTTPS is better.

## Hardware notes

- Vivo V21 rear camera: 64 MP main sensor, autofocus. `getUserMedia` typically
  delivers 1920×1080 at 30 fps; that is plenty for the OCR crop.
- The phone must stay on the same network as the laptop. Mobile data does not
  matter because the app never calls the internet.
- Keep the laptop awake (`Settings → Power → Blank screen: Never`) for long
  scanning sessions.
- Use the laptop charger during a 2,000-bond run.
- A cheap phone stand improves consistency; you can also lay bonds flat under a
  desk lamp and hold the phone above them.

## Troubleshooting

| Problem | Cause / fix |
| --- | --- |
| `Camera blocked by the browser` with HTTPS warning | Use the printed `https://` URL and accept the certificate |
| `getUserMedia is undefined` | Insecure origin, or a browser other than Chrome/Edge |
| Camera starts but is black | Another app owns the camera; close it. On desktop, check the lens cover. |
| Auto scan never fires | Quality bar not green: too dark/blurry; fill the guide; or review card is open |
| Every scan says duplicate | The serial is genuinely saved, or you are rescanning the same bond; check recent history |
| Serial is one digit short/long | Clean the guide, avoid cutting the first/last digit; the strict 7-digit validator rejects partial reads |
| Review thumbnail 404 | The captured frame was cleaned up, or captures directory is not writable |
| Native app cannot reach laptop | Add the CA / enable cleartext as above, and use the laptop LAN IP (not `localhost`) |
