import { jsPDF } from 'jspdf';

const formatReceiptTimestamp = (dateInput) => {
  if (!dateInput) return '—';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const day = d.getDate();
  const month = months[d.getMonth()];
  const year = d.getFullYear();
  let hours = d.getHours();
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12 || 12;
  return `${day} ${month} ${year} • ${hours}:${minutes} ${ampm}`;
};

export function generateTellerReceiptPdf(receiptData) {
  // Physical 80mm width thermal receipt, compact height (95mm)
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: [80, 95]
  });

  const pageWidth = 80;
  const leftMargin = 7;
  const rightMargin = 73;
  const centerX = pageWidth / 2;

  let y = 10;

  // Header
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10.5);
  doc.setTextColor(18, 53, 91); // #12355B
  doc.text('AI SMART BANKING KIOSK', centerX, y, { align: 'center' });

  y += 5;
  doc.setFontSize(8);
  doc.setTextColor(100, 116, 139); // #64748B
  doc.text('TELLER TRANSACTION ACKNOWLEDGEMENT', centerX, y, { align: 'center' });

  y += 5;
  // Divider
  doc.setDrawColor(203, 213, 225); // #CBD5E1
  doc.setLineWidth(0.3);
  doc.line(leftMargin, y, rightMargin, y);

  y += 6;

  // Helper row
  const drawRow = (label, value, isAmount = false) => {
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8);
    doc.setTextColor(71, 85, 105);
    doc.text(label, leftMargin, y);

    doc.setFont('helvetica', isAmount ? 'bold' : 'normal');
    doc.setFontSize(isAmount ? 9 : 8);
    doc.setTextColor(isAmount ? 15 : 30, isAmount ? 23 : 41, isAmount ? 42 : 59);
    doc.text(String(value), rightMargin, y, { align: 'right' });
    y += 5.5;
  };

  const customerName = receiptData?.customer_name || receiptData?.customer_display_name || receiptData?.customerId || 'Valued Customer';
  const formattedAmount = 'INR ' + Number(receiptData?.amount || 0).toLocaleString('en-IN');
  const formattedType = String(receiptData?.transaction_type || 'Transaction')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
  const issuedAt = formatReceiptTimestamp(receiptData?.issued_at);

  // Exact 4 fields requested: Customer, Transaction, Amount, Issued
  drawRow('Customer', customerName);
  drawRow('Transaction', formattedType);
  drawRow('Amount', formattedAmount, true);
  drawRow('Issued', issuedAt);

  y += 1;
  // Divider
  doc.setDrawColor(203, 213, 225);
  doc.setLineWidth(0.3);
  doc.line(leftMargin, y, rightMargin, y);

  y += 6;
  // Handwritten Teller Signature Section
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(71, 85, 105);
  doc.text('Teller Signature', leftMargin, y);

  y += 14;
  doc.setDrawColor(15, 23, 42);
  doc.setLineWidth(0.4);
  doc.line(leftMargin, y, leftMargin + 48, y);

  return doc;
}
