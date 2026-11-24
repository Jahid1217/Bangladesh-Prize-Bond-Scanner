# OCR pipeline and tuning

The goal is not "always return a number" — it is **"never silently save a wrong
number"**. A wrong serial in the Excel sheet is worse than a manual review.

## Pipeline

```
JPEG frame
  │
  ├─ decode + resize (max width 1500 px, upscale small crops)
  ├─ grayscale → CLAHE → unsharp mask
  ├─ deskew (0.6°–12° only)
  │
  ├─ variant 1: Otsu threshold
  ├─ variant 2: contrast-stretched grayscale
  └─ variant 3: adaptive Gaussian threshold
        │
        ├─ Tesseract 5, `ben+eng`, OEM 3, PSM 7
        ├─ line text + mean word confidence
        ├─ normalize Bengali/Arabic-Indic digits → ASCII
        └─ regex extraction of 6–8 digit runs, strict validation
              │
              └─ consensus scoring across variants
                    │
                    ├─ accepted → save (UNIQUE insert)
                    ├─ uncertain → save frame + attempt, show review card
                    └─ no_serial → failed attempt only
```

Tesseract reads the whole serial line; the backend does not attempt unreliable
per-digit segmentation. Two independent binarisations agreeing is a much stronger
signal than one high confidence score.

### Variant order and early exit

1. `otsu` always runs.
2. If its best candidate is ≥ 94% confident and valid, it is returned early
   (single-pass path).
3. Otherwise `gray` runs. If both variants agree on the same serial, stop.
4. If they disagree, `adaptive` runs as a tie-breaker.

Average cost is ~0.7 s per frame on an i7-8650U (2–3 Tesseract calls on a
~1500×200 crop). The phone throttles to one frame every 750 ms and never
overlaps requests.

## Digit normalization

- Bengali digits `০১২৩৪৫৬৭৮৯` and Arabic-Indic digits `٠١٢٣٤٥٦٧٨٩` map to `0-9`.
- Bengali text is NFKC-normalized; Latin letters are upper-cased.
- Spaces, hyphens, dots, slashes and OCR punctuation are removed.
- Leading zeros are preserved. Everything is stored as text, never as a number.
- Only letter/digit confusion repair (`O→0`, `I→1`, …) is used to pre-fill a
  review suggestion; it is **never** used to auto-save.

## Validation

Defaults in `backend/app/config.py` target current Bangladesh 100-taka bonds:

```text
PBS_SERIAL_PATTERN       ^[A-Z\u0985-\u09B9\u09DC-\u09DF]{0,2}\d{7}$
PBS_MIN_SERIAL_DIGITS    7
PBS_MAX_SERIAL_DIGITS    7
```

- 7 digits, optional 1–2 letter prefix, leading zeros allowed.
- An 8-digit read such as `59550001` for `5550001` is rejected, not "repaired".
  Validating at 6–8 digits made the engine auto-save that exact misread during
  development; strict length fixed it.
- For older/different series, change all three settings together.

## Decision rule

A read is auto-saved when:

```text
valid serial
AND (
      (≥2 independent variants agree AND confidence ≥ PBS_AUTO_SAVE_CONFIDENCE)
   OR (no rival serial was seen AND confidence ≥ PBS_SINGLE_VARIANT_CONFIDENCE)
)
```

Anything else with a candidate becomes `uncertain`: the image is stored, the
attempt is counted under failed OCR, and the dashboard pauses for confirmation.
If no candidate passes validation, the attempt is `failed`.

Defaults: `PBS_AUTO_SAVE_CONFIDENCE=72`, `PBS_SINGLE_VARIANT_CONFIDENCE=94`.

The "no rival serial" clause matters: if one pass says `1234567` at 96% and
another pass says `1234507`, the result is not auto-saved even though the first
score is high.

## Measured accuracy (included fixtures)

Command:

```bash
python scripts/evaluate_ocr.py --real
```

Environment: Tesseract 5.5.0, `ben+eng`, i7-8650U, synthetic bond strips
generated with Noto Sans Bengali Bold (20 samples, seed 42), plus the 512 px real
press photo in `tests/fixtures/real/`.

| Metric | Result |
| --- | --- |
| Exact synthetic Bengali reads | 16 / 20 (80%) |
| Auto-saved correct | 9 |
| **Auto-saved wrong** | **0** |
| Needs review | 9 |
| No serial found | 2 |
| Average latency | ~700 ms |
| English-digit reads | 4/4 exact (test set) |
| Real 100-taka press photo (512 px) | no serial, correctly refused |

The two "no serial" outcomes were 8-digit insertions that strict validation
rejected. That is intentional: the operator reviews/reshoots instead of getting a
corrupted number.

**Important:** exact-read accuracy is strongly affected by the print font. The
column of the real bond available online is only 512 px wide; at camera
resolution (1920×1080 crop) the same digits are far larger. Measure your own
bonds rather than assuming the synthetic number transfers.

## Measuring your own bonds

1. Put 10–20 real bonds under good light.
2. Use the dashboard's review images, or take photos and save them.
3. Put images + a `manifest.json` in a folder:

   ```json
   [
     { "serial": "0786345", "strip": "tests/fixtures/real/bond1_strip.jpg" }
   ]
   ```

   Paths are relative to the project root. Crop to the serial line, like the
   camera guide does.
4. Run:

   ```bash
   python scripts/evaluate_ocr.py --fixtures /path/to/folder --limit 20
   ```

A non-zero exit status means a wrong serial was auto-saved or accuracy fell below
`--min-exact`.

Single image debugging:

```bash
python scripts/ocr_image.py frame.jpg
```

Outputs the candidate, confidence, agreement, raw Tesseract text, variant list
and timing.

## Tuning

| Goal | Adjustment |
| --- | --- |
| More auto-saves | Lower `PBS_AUTO_SAVE_CONFIDENCE` (e.g. 65). Re-run your sample evaluation; never do this without real samples. |
| Fewer wrong saves | Raise the threshold, raise `PBS_SINGLE_VARIANT_CONFIDENCE`, or keep strict length validation |
| Different serial length | Set `PBS_SERIAL_PATTERN`, `PBS_MIN_SERIAL_DIGITS`, `PBS_MAX_SERIAL_DIGITS` together |
| Different language mix | `PBS_OCR_LANG=eng` for English-only bonds (faster, more accurate) |
| Too slow on an old CPU | Set `PBS_OCR_PSM=7` (default), reduce capture width in `frontend/src/lib/quality.js` (`maxWidth`) |
| Bengali data missing | `sudo apt install tesseract-ocr-ben`; check `/api/health` |

Threshold changes take effect on the next backend start.

## Known limits

- Tesseract's Bengali model is trained on general text, not bond numerals; some
  fonts confuse `২`/`৬` or `৫`/`৯`. Consensus + review catches these.
- Curved or highlighted serials, strong glare and motion blur defeat OCR. Good
  light and a steady, flat bond help more than any threshold.
- Glossy bonds with decorative backgrounds create noise. The guide crop should
  contain the serial line and as little decoration as possible.
- The engine cannot know a serial is "probably" something. It does not guess
  missing digits.
