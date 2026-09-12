import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { printReceipt } from '../../services/printing/printService';
import { generateTellerReceiptPdf } from '../../services/printing/tellerPdfService';
import { Printer, Download, X } from 'lucide-react';

const formatInrAmount = (amt) => {
  const num = Number(amt);
  if (isNaN(num)) return `INR ${amt || '0'}`;
  return `INR ${num.toLocaleString('en-IN')}`;
};

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

const TellerReceiptDocument = ({ receiptData }) => {
  const transactionLabel = String(receiptData?.transaction_type || 'Transaction')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

  const customerName = receiptData?.customer_name || receiptData?.customer_display_name || receiptData?.customerId || 'Valued Customer';
  const amountStr = formatInrAmount(receiptData?.amount);
  const issuedStr = formatReceiptTimestamp(receiptData?.issued_at);

  return (
    <div className="thermal-receipt" id="printable-receipt-section">
      <div className="thermal-receipt__header">
        <div className="thermal-receipt__bank">AI SMART BANKING KIOSK</div>
        <div className="thermal-receipt__title">TELLER TRANSACTION ACKNOWLEDGEMENT</div>
      </div>

      <div className="thermal-receipt__divider" style={{ textAlign: 'center' }}>--------------------------------</div>

      <div className="thermal-receipt__rows">
        <div className="thermal-receipt__row">
          <span>Customer</span>
          <strong>{customerName}</strong>
        </div>
        <div className="thermal-receipt__row">
          <span>Transaction</span>
          <strong>{transactionLabel}</strong>
        </div>
        <div className="thermal-receipt__row thermal-receipt__row--amount">
          <span>Amount</span>
          <strong>{amountStr}</strong>
        </div>
        <div className="thermal-receipt__row">
          <span>Issued</span>
          <strong>{issuedStr}</strong>
        </div>
      </div>

      <div className="thermal-receipt__divider" style={{ textAlign: 'center' }}>--------------------------------</div>

      <div className="thermal-receipt__footer">
        <div style={{ textAlign: 'left', paddingLeft: '2px', marginTop: '6px' }}>
          <div style={{ fontSize: '8pt', fontWeight: 700, color: '#334155' }}>Teller Signature</div>
          <div style={{ marginTop: '24px', borderBottom: '1px solid #0f172a', width: '80%' }}></div>
        </div>
      </div>
    </div>
  );
};

export const ReceiptPreviewModal = ({ isOpen, receiptData, onClose }) => {
  const [printStatus, setPrintStatus] = useState('');
  const [isPrinting, setIsPrinting] = useState(false);
  const [printContainer, setPrintContainer] = useState(null);

  useEffect(() => {
    let container = document.getElementById('print-root');
    if (!container) {
      container = document.createElement('div');
      container.id = 'print-root';
      document.body.appendChild(container);
    }
    setPrintContainer(container);
  }, []);

  if (!isOpen || !receiptData) return null;

  const handleDownloadPdf = () => {
    try {
      const doc = generateTellerReceiptPdf(receiptData);
      const safeName = (receiptData.customer_name || 'receipt').toLowerCase().replace(/[^a-z0-9]/g, '_');
      const filename = `teller_receipt_${safeName}.pdf`;
      doc.save(filename);
      setPrintStatus('✓ Downloaded compact receipt PDF (80mm × 95mm).');
    } catch (err) {
      console.error('[ReceiptPreview] PDF download error:', err);
      setPrintStatus('Error generating PDF.');
    }
  };

  const handlePrintAction = async () => {
    if (isPrinting) return;
    setIsPrinting(true);
    setPrintStatus('Opening thermal receipt print dialog (80mm compact)...');

    try {
      const result = await printReceipt(receiptData);

      if (result.success && result.hardwareConnected) {
        setPrintStatus('✓ Receipt sent to the thermal printer.');
      } else {
        setTimeout(() => window.print(), 250);
      }
    } catch (error) {
      console.error('[ReceiptPreview] Print error:', error);
      setTimeout(() => window.print(), 250);
    } finally {
      setIsPrinting(false);
    }
  };

  return (
    <>
      {/* Portal dedicated print content into #print-root (completely separate from #root) */}
      {printContainer && createPortal(
        <TellerReceiptDocument receiptData={receiptData} />,
        printContainer
      )}

      {/* Screen Modal Overlay */}
      <div className="modal-overlay no-print">
        <div className="modal-card" style={{ maxWidth: 400 }}>
          <div className="modal-header flex justify-between items-center">
            <div>
              <h2 style={{ fontSize: '1.02rem', fontWeight: 700, color: '#12355B' }}>
                Teller Transaction Acknowledgement
              </h2>
              <p style={{ fontSize: '0.76rem', color: '#64748B' }}>
                Compact 80mm Teller Receipt
              </p>
            </div>
            <button onClick={onClose} style={{ color: '#64748B' }} aria-label="Close receipt">
              <X size={18} />
            </button>
          </div>

          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <TellerReceiptDocument receiptData={receiptData} />

            {printStatus && (
              <div className="print-status" role="status">{printStatus}</div>
            )}
          </div>

          <div className="modal-footer no-print flex justify-end gap-2">
            <button className="btn btn-secondary" onClick={onClose}>Close</button>
            <button className="btn btn-outline" onClick={handleDownloadPdf} title="Download compact 80mm PDF">
              <Download size={15} />
              <span>Download PDF</span>
            </button>
            <button className="btn btn-primary" onClick={handlePrintAction} disabled={isPrinting}>
              <Printer size={15} />
              <span>{isPrinting ? 'Printing...' : 'Print Receipt'}</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
};


