import { useEffect, useState } from "react";

import { explainTransaction, getTransaction } from "./api.js";
import { DecisionBadge, formatMoney, formatTime } from "./format.jsx";

export default function TransactionDetail({ apiKey, id, onBack, onAuthError }) {
  const [tx, setTx] = useState(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState(null);
  const [askError, setAskError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getTransaction(apiKey, id)
      .then((data) => { if (!cancelled) setTx(data); })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) onAuthError();
        else setError(err.message);
      });
    return () => { cancelled = true; };
  }, [apiKey, id]);

  async function ask(text) {
    setAsking(true);
    setResult(null);
    setAskError("");
    try {
      setResult(await explainTransaction(apiKey, id, text));
    } catch (err) {
      if (err.status === 401) onAuthError();
      else setAskError(err.message);
    } finally {
      setAsking(false);
    }
  }

  if (error) {
    return (
      <section>
        <button className="link" onClick={onBack}>&larr; Back</button>
        <p className="error">{error}</p>
      </section>
    );
  }
  if (!tx) return <p className="muted">Loading...</p>;

  return (
    <section>
      <button className="link" onClick={onBack}>&larr; Back to transactions</button>

      <div className="card">
        <h2>Transaction {tx.id} <DecisionBadge decision={tx.decision} /></h2>
        <dl>
          <dt>Time</dt><dd>{formatTime(tx.timestamp)}</dd>
          <dt>Amount</dt><dd>{formatMoney(tx.amount)}</dd>
          <dt>Category</dt><dd>{tx.category}</dd>
          <dt>Merchant</dt><dd>{tx.merchant || "-"}</dd>
          <dt>Risk score</dt><dd>{tx.risk_score.toFixed(4)} (0 to 1, higher is riskier)</dd>
          <dt>Model alone said</dt><dd>{tx.model_decision}</dd>
          <dt>Safety rules</dt><dd>{tx.rules_triggered.join(", ") || "none"}</dd>
          <dt>Model version</dt><dd>{tx.model_version}</dd>
        </dl>
        <p className="muted">The ML model and the safety rules made this decision. The AI below only explains it.</p>
      </div>

      <div className="card">
        <h3>Top reasons (from the model)</h3>
        <ul className="reasons">
          {tx.reasons.map((reason) => (
            <li key={reason.feature}>
              <span className={reason.direction === "increases risk" ? "up" : "down"}>
                {reason.direction === "increases risk" ? "\u25B2" : "\u25BC"}
              </span>{" "}
              {reason.text}
              <span className="muted"> ({reason.impact > 0 ? "+" : ""}{reason.impact.toFixed(2)})</span>
            </li>
          ))}
        </ul>
        <p className="muted">Impact is in log-odds units, not percentage points. Reasons explain the model, not real-world causes.</p>
      </div>

      <div className="card">
        <h3>Ask why</h3>
        <div className="ask">
          <button disabled={asking} onClick={() => ask("")}>Explain this decision</button>
          <span className="muted">or ask your own question:</span>
        </div>
        <form className="ask" onSubmit={(event) => { event.preventDefault(); ask(question.trim()); }}>
          <input
            type="text"
            placeholder="For example: why does the hour matter?"
            maxLength={300}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <button type="submit" disabled={asking || question.trim().length < 3}>Ask</button>
        </form>

        {asking && <p className="muted">Searching the knowledge base and asking the AI...</p>}
        {askError && <p className="error">{askError}</p>}

        {result && (
          <div className="answer">
            {!result.answered && <p className="muted">No answer from the knowledge base:</p>}
            {/* Shown as plain text on purpose. React escapes it, so the AI cannot inject HTML. */}
            <p className="answer-text">{result.answer}</p>
            {result.llm_model && <p className="muted">Written by {result.llm_model}. It can still make mistakes. Check the sources.</p>}
            {result.sources.length > 0 && (
              <>
                <h4>Sources given to the AI</h4>
                <ul className="sources">
                  {result.sources.map((source, index) => (
                    <li key={source.source}>
                      <strong>[{index + 1}] {source.title}</strong>{" "}
                      <span className="muted">({source.source}, match {source.score.toFixed(2)})</span>
                      <p>{source.text}</p>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}