import jsQR from 'jsqr';
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode';

/**
 * Loads a File or Blob into an HTMLImageElement
 */
function loadImage(fileOrBlob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(fileOrBlob);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = (err) => {
      URL.revokeObjectURL(url);
      reject(err);
    };
    img.src = url;
  });
}

/**
 * Scan for QR Finder Patterns (1:1:3:1:1 ratio) to locate QR bounding box
 */
function findFinderPatternBounds(rgba, width, height) {
  const centers = [];
  const step = Math.max(2, Math.floor(height / 400));

  for (let y = 0; y < height; y += step) {
    const stateCounts = [0, 0, 0, 0, 0];
    let currentState = 0;

    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 4;
      // Fast luminance
      const lum = (rgba[idx] * 299 + rgba[idx + 1] * 587 + rgba[idx + 2] * 114) / 1000;
      const isBlack = lum < 128;

      if (isBlack) {
        if ((currentState & 1) === 1) currentState++;
        stateCounts[currentState]++;
      } else {
        if ((currentState & 1) === 0) {
          if (currentState === 4) {
            const total = stateCounts[0] + stateCounts[1] + stateCounts[2] + stateCounts[3] + stateCounts[4];
            if (total >= 7) {
              const moduleSize = total / 7.0;
              const maxVariance = moduleSize * 0.75;
              if (
                Math.abs(moduleSize - stateCounts[0]) < maxVariance &&
                Math.abs(moduleSize - stateCounts[1]) < maxVariance &&
                Math.abs(3 * moduleSize - stateCounts[2]) < 3 * maxVariance &&
                Math.abs(moduleSize - stateCounts[3]) < maxVariance &&
                Math.abs(moduleSize - stateCounts[4]) < maxVariance
              ) {
                const centerX = x - stateCounts[4] - stateCounts[3] - stateCounts[2] / 2;
                centers.push({ x: centerX, y, moduleSize });
              }
            }
            stateCounts[0] = stateCounts[2];
            stateCounts[1] = stateCounts[3];
            stateCounts[2] = stateCounts[4];
            stateCounts[3] = 1;
            stateCounts[4] = 0;
            currentState = 3;
            continue;
          }
          currentState++;
        }
        stateCounts[currentState]++;
      }
    }
  }

  if (centers.length < 3) return null;

  const xs = centers.map((c) => c.x);
  const ys = centers.map((c) => c.y);
  const avgModule = centers.reduce((sum, c) => sum + c.moduleSize, 0) / centers.length;

  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
    avgModule
  };
}

/**
 * Crops a sub-region from a canvas and adds a white quiet-zone border
 */
function cropWithQuietZone(srcCanvas, box, padding = 40, border = 24) {
  const x1 = Math.max(0, Math.floor(box.minX - padding));
  const y1 = Math.max(0, Math.floor(box.minY - padding));
  const x2 = Math.min(srcCanvas.width, Math.ceil(box.maxX + padding));
  const y2 = Math.min(srcCanvas.height, Math.ceil(box.maxY + padding));
  const cropW = Math.max(10, x2 - x1);
  const cropH = Math.max(10, y2 - y1);

  const outCanvas = document.createElement('canvas');
  outCanvas.width = cropW + border * 2;
  outCanvas.height = cropH + border * 2;
  const ctx = outCanvas.getContext('2d', { willReadFrequently: true });

  // Pure white quiet zone
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, outCanvas.width, outCanvas.height);
  ctx.drawImage(srcCanvas, x1, y1, cropW, cropH, border, border, cropW, cropH);

  return outCanvas;
}

/**
 * Attempts decoding using native browser BarcodeDetector if available
 */
async function tryNativeBarcodeDetector(source) {
  if (typeof window !== 'undefined' && 'BarcodeDetector' in window) {
    try {
      const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
      const barcodes = await detector.detect(source);
      if (barcodes && barcodes.length > 0 && barcodes[0].rawValue) {
        return barcodes[0].rawValue;
      }
    } catch (e) {
      // Ignore and fallback
    }
  }
  return null;
}

/**
 * Robust Multi-Pass Client-Side QR Detection and Decoding Pipeline.
 * Handles:
 * - High-resolution screenshots with surrounding browser UI, text, whitespace
 * - Full receipts with QR anywhere on the page
 * - Cropped and uncropped QR codes
 * - Rotated, scaled, or low-contrast images
 */
export async function robustDecodeQR(fileOrBlob) {
  const img = await loadImage(fileOrBlob);
  const { naturalWidth: origW, naturalHeight: origH } = img;
  const width = origW || img.width;
  const height = origH || img.height;

  // 1. Pass 1: Try Native BarcodeDetector directly on the high-res image
  const nativeResult = await tryNativeBarcodeDetector(img);
  if (nativeResult) {
    console.log('[QR Decoder] Pass 1 (Native BarcodeDetector): Success');
    return nativeResult;
  }

  // 2. Prepare high-resolution canvas (preserve module detail, never downscale to 300px!)
  let scale = 1;
  const maxDim = 2048;
  if (width > maxDim || height > maxDim) {
    scale = maxDim / Math.max(width, height);
  }
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

  let imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);

  // 3. Pass 2: Direct jsQR decode at full resolution
  let code = jsQR(imgData.data, canvas.width, canvas.height, { inversionAttempts: 'attemptBoth' });
  if (code && code.data) {
    console.log('[QR Decoder] Pass 2 (Direct jsQR Full-Res): Success');
    return code.data;
  }

  // 4. Pass 3: QR Finder Pattern Region Detection & Auto-Crop
  const finderBox = findFinderPatternBounds(imgData.data, canvas.width, canvas.height);
  if (finderBox) {
    const quietPadding = Math.max(35, Math.round(finderBox.avgModule * 5));
    const croppedCanvas = cropWithQuietZone(canvas, finderBox, quietPadding, 24);

    // Try BarcodeDetector on cropped canvas
    const croppedNative = await tryNativeBarcodeDetector(croppedCanvas);
    if (croppedNative) {
      console.log('[QR Decoder] Pass 3a (Finder Auto-Crop + Native): Success');
      return croppedNative;
    }

    // Try jsQR on cropped canvas
    const croppedCtx = croppedCanvas.getContext('2d', { willReadFrequently: true });
    const croppedData = croppedCtx.getImageData(0, 0, croppedCanvas.width, croppedCanvas.height);
    const croppedCode = jsQR(croppedData.data, croppedCanvas.width, croppedCanvas.height, { inversionAttempts: 'attemptBoth' });
    if (croppedCode && croppedCode.data) {
      console.log('[QR Decoder] Pass 3b (Finder Auto-Crop + jsQR): Success');
      return croppedCode.data;
    }
  }

  // 5. Pass 4: Multi-Region Candidate Crops (Common screenshot & receipt layouts)
  const candidateRegions = [
    // Central 70%
    { minX: canvas.width * 0.15, maxX: canvas.width * 0.85, minY: canvas.height * 0.15, maxY: canvas.height * 0.85 },
    // Central 85%
    { minX: canvas.width * 0.075, maxX: canvas.width * 0.925, minY: canvas.height * 0.075, maxY: canvas.height * 0.925 },
    // Receipt Lower-Center (QR typically below header)
    { minX: canvas.width * 0.1, maxX: canvas.width * 0.9, minY: canvas.height * 0.2, maxY: canvas.height * 0.95 },
    // Receipt Upper-Center
    { minX: canvas.width * 0.1, maxX: canvas.width * 0.9, minY: canvas.height * 0.05, maxY: canvas.height * 0.8 }
  ];

  for (let i = 0; i < candidateRegions.length; i++) {
    const reg = candidateRegions[i];
    const regCanvas = cropWithQuietZone(canvas, reg, 10, 20);
    const regCtx = regCanvas.getContext('2d', { willReadFrequently: true });
    const regData = regCtx.getImageData(0, 0, regCanvas.width, regCanvas.height);
    const regCode = jsQR(regData.data, regCanvas.width, regCanvas.height, { inversionAttempts: 'attemptBoth' });
    if (regCode && regCode.data) {
      console.log(`[QR Decoder] Pass 4.${i + 1} (Candidate Region Crop): Success`);
      return regCode.data;
    }
  }

  // 6. Pass 5: Contrast Enhancement & Grayscale Thresholding
  const grayCanvas = document.createElement('canvas');
  grayCanvas.width = canvas.width;
  grayCanvas.height = canvas.height;
  const grayCtx = grayCanvas.getContext('2d', { willReadFrequently: true });
  const grayData = grayCtx.createImageData(canvas.width, canvas.height);
  const src = imgData.data;
  const dst = grayData.data;

  let minLum = 255;
  let maxLum = 0;
  for (let i = 0; i < src.length; i += 4) {
    const lum = (src[i] * 299 + src[i + 1] * 587 + src[i + 2] * 114) / 1000;
    if (lum < minLum) minLum = lum;
    if (lum > maxLum) maxLum = lum;
  }
  const range = Math.max(1, maxLum - minLum);

  for (let i = 0; i < src.length; i += 4) {
    const lum = (src[i] * 299 + src[i + 1] * 587 + src[i + 2] * 114) / 1000;
    const stretched = ((lum - minLum) / range) * 255;
    const val = stretched > 128 ? 255 : 0;
    dst[i] = val;
    dst[i + 1] = val;
    dst[i + 2] = val;
    dst[i + 3] = 255;
  }
  grayCtx.putImageData(grayData, 0, 0);

  const grayCode = jsQR(grayData.data, grayCanvas.width, grayCanvas.height, { inversionAttempts: 'attemptBoth' });
  if (grayCode && grayCode.data) {
    console.log('[QR Decoder] Pass 5 (Contrast Stretched / Thresholded): Success');
    return grayCode.data;
  }

  // 7. Pass 6: Rotation Fallback (90 deg, 180 deg, 270 deg)
  for (const angle of [90, 180, 270]) {
    const rotCanvas = document.createElement('canvas');
    if (angle === 90 || angle === 270) {
      rotCanvas.width = canvas.height;
      rotCanvas.height = canvas.width;
    } else {
      rotCanvas.width = canvas.width;
      rotCanvas.height = canvas.height;
    }
    const rotCtx = rotCanvas.getContext('2d', { willReadFrequently: true });
    rotCtx.translate(rotCanvas.width / 2, rotCanvas.height / 2);
    rotCtx.rotate((angle * Math.PI) / 180);
    rotCtx.drawImage(canvas, -canvas.width / 2, -canvas.height / 2);

    const rotData = rotCtx.getImageData(0, 0, rotCanvas.width, rotCanvas.height);
    const rotCode = jsQR(rotData.data, rotCanvas.width, rotCanvas.height, { inversionAttempts: 'attemptBoth' });
    if (rotCode && rotCode.data) {
      console.log(`[QR Decoder] Pass 6 (Rotation ${angle}°): Success`);
      return rotCode.data;
    }
  }

  // 8. Pass 7: Fallback to Html5Qrcode with dedicated sized element
  try {
    let tempContainer = document.getElementById('qr-robust-decoder-host');
    if (!tempContainer) {
      tempContainer = document.createElement('div');
      tempContainer.id = 'qr-robust-decoder-host';
      // Crucial: Give it large clientWidth/clientHeight so it NEVER downsamples to 300px!
      tempContainer.style.position = 'fixed';
      tempContainer.style.left = '-9999px';
      tempContainer.style.top = '-9999px';
      tempContainer.style.width = '1920px';
      tempContainer.style.height = '1080px';
      tempContainer.style.visibility = 'hidden';
      document.body.appendChild(tempContainer);
    }

    const html5Scanner = new Html5Qrcode('qr-robust-decoder-host', {
      formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
      verbose: false,
      experimentalFeatures: {
        useBarCodeDetectorIfSupported: true
      }
    });

    const fileToScan = fileOrBlob instanceof File ? fileOrBlob : new File([fileOrBlob], 'qr_upload.png', { type: 'image/png' });
    const fallbackResult = await html5Scanner.scanFile(fileToScan, false);
    html5Scanner.clear();

    if (fallbackResult) {
      console.log('[QR Decoder] Pass 7 (Html5Qrcode Engine): Success');
      return fallbackResult;
    }
  } catch (e) {
    // End of pipeline
  }

  return null;
}
