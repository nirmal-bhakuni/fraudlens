import { useState } from "react";

import { checkKey } from "./api.js";

export default function Login({ onLogin }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await checkKey(key.trim());
      onLogin(key.trim());
    } catch (err) {
      setError(err.status === 401 ? "That API key was not accepted." : err.message);
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <h1>FraudLens</h1>
      <p className="muted">Explainable payment fraud checks. Enter your API key to continue.</p>
      <form onSubmit={submit}>
        <input
          type="password"
          placeholder="API key"
          value={key}
          onChange={(event) => setKey(event.target.value)}
          autoFocus
        />
        <button type="submit" disabled={busy || key.trim() === ""}>
          {busy ? "Checking..." : "Log in"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
}