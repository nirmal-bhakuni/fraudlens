import { useState } from "react";

import Login from "./Login.jsx";
import TransactionDetail from "./TransactionDetail.jsx";
import TransactionList from "./TransactionList.jsx";

const STORAGE_NAME = "fraudlens_api_key";

export default function App() {
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem(STORAGE_NAME) || "");
  const [selectedId, setSelectedId] = useState(null);

  function login(key) {
    sessionStorage.setItem(STORAGE_NAME, key);
    setApiKey(key);
  }

  function logout() {
    sessionStorage.removeItem(STORAGE_NAME);
    setApiKey("");
    setSelectedId(null);
  }

  if (!apiKey) return <Login onLogin={login} />;

  return (
    <div className="page">
      <header className="topbar">
        <h1>FraudLens</h1>
        <button className="link" onClick={logout}>Log out</button>
      </header>
      {selectedId === null ? (
        <TransactionList apiKey={apiKey} onSelect={setSelectedId} onAuthError={logout} />
      ) : (
        <TransactionDetail
          apiKey={apiKey}
          id={selectedId}
          onBack={() => setSelectedId(null)}
          onAuthError={logout}
        />
      )}
    </div>
  );
}