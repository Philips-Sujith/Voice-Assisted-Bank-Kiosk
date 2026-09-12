import { jsPDF } from 'jspdf'
import QRCode from 'qrcode'
import { getTransactionLabel } from '../constants/transactions.js'

function formatCurrency(amount) {
  if (amount == null || amount === '' || Number.isNaN(Number(amount))) return 'INR 0'
  return `INR ${Number(amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

function formatReceiptTimestamp(dateInput) {
  if (!dateInput) return '—'
  const d = new Date(dateInput)
  if (Number.isNaN(d.getTime())) return String(dateInput)
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const day = d.getDate()
  const month = months[d.getMonth()]
  const year = d.getFullYear()
  let hours = d.getHours()
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const ampm = hours >= 12 ? 'PM' : 'AM'
  hours = hours % 12 || 12
  return `${day} ${month} ${year} • ${hours}:${minutes} ${ampm}`
}

function getIssuedAtFromPayload(qrPayload) {
  try {
    const tokenData = JSON.parse(atob(qrPayload))
    return tokenData.timestamp || tokenData.issued_at
  } catch {
    return null
  }
}

function getFormattedTransaction(transactionType) {
  if (!transactionType) return 'Transaction'
  const label = getTransactionLabel(transactionType)
  if (label && label !== 'Other Services') return label
  return String(transactionType)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase())
}

export async function createReceiptPdf({
  customerName,
  transactionType,
  amount,
  issuedAt,
  expiresAt,
  qrPayload,
}) {
  if (!qrPayload) {
    throw new Error('Secure receipt data is unavailable.')
  }

  const qrDataUrl = await QRCode.toDataURL(qrPayload, {
    errorCorrectionLevel: 'M',
    margin: 1,
    width: 500,
    color: { dark: '#0f172a', light: '#ffffff' },
  })

  // Physical 80mm width thermal receipt, matching the Teller Receipt design language
  const PAGE_WIDTH = 80
  const PAGE_HEIGHT = 126
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: [PAGE_WIDTH, PAGE_HEIGHT],
  })

  const leftMargin = 7
  const rightMargin = 73
  const centerX = PAGE_WIDTH / 2

  let y = 10

  // 1. Header Section
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(10.5)
  doc.setTextColor(18, 53, 91) // #12355B
  doc.text('AI SMART BANKING KIOSK', centerX, y, { align: 'center' })

  y += 5
  doc.setFontSize(8)
  doc.setTextColor(100, 116, 139) // #64748B
  doc.text('TRANSACTION RECEIPT', centerX, y, { align: 'center' })

  y += 4.5
  // Divider 1
  doc.setDrawColor(203, 213, 225) // #CBD5E1
  doc.setLineWidth(0.3)
  doc.line(leftMargin, y, rightMargin, y)

  y += 5.5

  // 2. Transaction Details (Two-Column Layout)
  const drawRow = (label, value, isAmount = false) => {
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8)
    doc.setTextColor(71, 85, 105) // #475569
    doc.text(label, leftMargin, y)

    doc.setFont('helvetica', isAmount ? 'bold' : 'normal')
    doc.setFontSize(isAmount ? 9 : 8)
    doc.setTextColor(isAmount ? 15 : 30, isAmount ? 23 : 41, isAmount ? 42 : 59) // #0f172a or #1e293b

    const strValue = String(value ?? '—')
    const maxValWidth = 46
    const lines = doc.splitTextToSize(strValue, maxValWidth)

    if (lines.length <= 1) {
      doc.text(strValue, rightMargin, y, { align: 'right' })
      y += 5.2
    } else {
      let rowY = y
      for (let i = 0; i < lines.length; i++) {
        doc.text(lines[i], rightMargin, rowY, { align: 'right' })
        rowY += 4
      }
      y = rowY + 1.2
    }
  }

  const resolvedCustomer = customerName || 'Authenticated Customer'
  const resolvedTransaction = getFormattedTransaction(transactionType)
  const resolvedAmount = formatCurrency(amount)
  const resolvedIssued = formatReceiptTimestamp(issuedAt || getIssuedAtFromPayload(qrPayload) || new Date().toISOString())
  const resolvedExpires = formatReceiptTimestamp(expiresAt)

  drawRow('Customer', resolvedCustomer)
  drawRow('Transaction', resolvedTransaction)
  drawRow('Amount', resolvedAmount, true)
  drawRow('Issued', resolvedIssued)
  drawRow('Valid Until', resolvedExpires)

  y += 1.0
  // Divider 2
  doc.setDrawColor(203, 213, 225) // #CBD5E1
  doc.setLineWidth(0.3)
  doc.line(leftMargin, y, rightMargin, y)

  y += 5.0

  // 3. QR Section (Centered with clear quiet zone)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(8)
  doc.setTextColor(18, 53, 91) // #12355B
  doc.text('SCAN AT TELLER', centerX, y, { align: 'center' })

  y += 3.5
  const qrSize = 30
  const qrX = (PAGE_WIDTH - qrSize) / 2
  doc.addImage(qrDataUrl, 'PNG', qrX, y, qrSize, qrSize)

  y += qrSize + 3.5
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(7.2)
  doc.setTextColor(100, 116, 139) // #64748B
  doc.text('Present this receipt at the teller counter.', centerX, y, { align: 'center' })

  y += 4.0
  // Divider 3
  doc.setDrawColor(203, 213, 225) // #CBD5E1
  doc.setLineWidth(0.3)
  doc.line(leftMargin, y, rightMargin, y)

  y += 5.5

  // 4. Handwritten Customer Signature Section
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(8)
  doc.setTextColor(71, 85, 105) // #475569
  doc.text('Customer Signature', leftMargin, y)

  y += 13.0
  doc.setDrawColor(15, 23, 42) // #0F172A
  doc.setLineWidth(0.4)
  doc.line(leftMargin, y, leftMargin + 48, y)

  return doc.output('blob')
}

export async function downloadReceiptPdf(receiptData) {
  const blob = await createReceiptPdf(receiptData)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `customer_receipt_${receiptData?.tokenId || Date.now()}.pdf`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
