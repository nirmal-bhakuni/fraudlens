import { useEffect, useState } from "react";

import { listTransactions } from "./api.js";
import { DecisionBadge, formatMoney, formatTime } from "./format.jsx";

const EMPTY_FILTERS = {
  flagged: "", decision: "", date_from: "", date_to: "", min_amount: "", max_amount: "",
};
const PAGE_SIZE = 15;

export default function TransactionList({ apiKey, onSelect, onAuthError }) {
  const [form, setForm] = useState(EMPTY_FILTERS);       // what the person is typing
  const [applied, setApplied] = useState(EMPTY_FILTERS); // what the table uses
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Runs again whenever the applied filters or the page change.
  useEffect(() => {
    let cancelled = false; // ignore an old answer that arrives late
    setLoading(true);
    setError("");
    listTransactions(apiKey, { ...applied, limit: PAGE_SIZE, offset })
      .then((result) => { if (!cancelled) setData(result); })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) onAuthError();
        else setError(err.message);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apiKey, applied, offset]);

  const change = (name) => (event) => setForm({ ...form, [name]: event.target.value });

  function apply(event) {
    event.preventDefault();
    setOffset(0);
    setApplied(form);
  }

  function reset() {
    setForm(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setOffset(0);
  }

  const total = data ? data.total : 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <section>
      <form className="filters" onSubmit={apply}>
        <label>Flagged
          <select value={form.flagged} onChange={change("flagged")}>
            <option value="">All</option>
            <option value="true">Flagged</option>
            <option value="false">Not flagged</option>
          </select>
        </label>
        <label>Decision
          <select value={form.decision} onChange={change("decision")}>
            <option value="">All</option>
            <option>Approve</option>
            <option>Review</option>
            <option>Decline</option>
          </select>
        </label>
        <label>From
          <input type="date" value={form.date_from} onChange={change("date_from")} />
        </label>
        <label>To
          <input type="date" value={form.date_to} onChange={change("date_to")} />
        </label>
        <label>Min amount
          <input type="number" min="0" step="any" value={form.min_amount} onChange={change("min_amount")} />
        </label>
        <label>Max amount
          <input type="number" min="0" step="any" value={form.max_amount} onChange={change("max_amount")} />
        </label>
        <button type="submit">Apply</button>
        <button type="button" className="secondary" onClick={reset}>Reset</button>
      </form>

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Loading...</p>}

      {data && data.items.length === 0 && !loading && !error && (
        <p className="muted">No transactions match. To add demo data, run: python scripts\seed_demo.py</p>
      )}

      {data && data.items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Time</th><th>Amount</th><th>Category</th>
                <th>Score</th><th>Decision</th><th>Rules</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((tx) => (
                <tr key={tx.id} onClick={() => onSelect(tx.id)} className="clickable">
                  <td>{tx.id}</td>
                  <td>{formatTime(tx.timestamp)}</td>
                  <td>{formatMoney(tx.amount)}</td>
                  <td>{tx.category}</td>
                  <td>{tx.risk_score.toFixed(3)}</td>
                  <td><DecisionBadge decision={tx.decision} /></td>
                  <td>{tx.rules_triggered.join(", ") || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pager">
        <span className="muted">{from}-{to} of {total}</span>
        <button className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
          Previous
        </button>
        <button className="secondary" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
          Next
        </button>
      </div>
    </section>
  );
}