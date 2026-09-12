export function formatCurrency(amount) {
  if (amount === undefined || amount === null) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(amount);
}

export function maskCustomerId(nameOrId) {
  if (!nameOrId) return '•••• 4821';
  // If it matches Customer #XXXX, format cleanly as Customer #XXXX or masked digits
  if (typeof nameOrId === 'string' && nameOrId.includes('#')) {
    const parts = nameOrId.split('#');
    return `•••• •••• ${parts[1] || '4821'}`;
  }
  return `•••• •••• ${String(nameOrId).slice(-4)}`;
}

export function formatDateTime(isoString) {
  if (!isoString) return new Date().toLocaleString();
  try {
    const d = new Date(isoString);
    return d.toLocaleString('en-US', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  } catch (e) {
    return isoString;
  }
}

export function formatTimeOnly(isoString) {
  if (!isoString) return new Date().toLocaleTimeString();
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  } catch (e) {
    return isoString;
  }
}
