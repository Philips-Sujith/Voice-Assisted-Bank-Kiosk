const TRANSACTION_DISPLAY_LABELS = Object.freeze({
  deposit: 'Deposit',
  withdraw: 'Withdrawal',
  send_money: 'Send Money',
  balance_check: 'Balance Check',
  open_account: 'Open Account',
  unknown: 'Unknown Transaction',
})

export function getTransactionLabel(transactionType) {
  if (typeof transactionType !== 'string') return TRANSACTION_DISPLAY_LABELS.unknown
  const normalized = transactionType.trim().toLowerCase()
  return TRANSACTION_DISPLAY_LABELS[normalized] || TRANSACTION_DISPLAY_LABELS.unknown
}
