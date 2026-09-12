/**
 * Local Kiosk Thermal Receipt Printing Service
 * Communicates with local python-escpos REST bridge running on http://localhost:5000
 */

export async function printReceipt(receiptData) {
  try {
    const response = await fetch('http://localhost:5000/api/print', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(receiptData)
    });

    if (!response.ok) {
      throw new Error(`Local print service HTTP error ${response.status}`);
    }

    const result = await response.json();
    return {
      success: true,
      hardwareConnected: result.hardware_connected,
      message: result.message,
      preview: result.preview_data
    };
  } catch (err) {
    console.warn('[PrintService] Local python-escpos bridge offline, fallback to browser print preview:', err);
    return {
      success: false,
      hardwareConnected: false,
      message: 'Local ESC/POS print service unreachable. Rendering browser receipt preview.',
      fallbackBrowserPrint: true
    };
  }
}
