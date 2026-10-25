export function formatMoney(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

// The backend sends local clock times without a timezone. We show them as they are.
export function formatTime(iso) {
  return String(iso).replace("T", " ").slice(0, 19);
}

export function DecisionBadge({ decision }) {
  return <span className={`badge badge-${decision.toLowerCase()}`}>{decision}</span>;
}