// All calls to the backend live here, so the pages stay simple.
const BASE = "/api";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// FastAPI sends errors as {detail: "text"} or, for bad input, {detail: [{loc, msg}, ...]}.
function detailToText(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  }
  return "Unexpected error";
}

async function request(apiKey, path, options = {}) {
  let response;
  try {
    response = await fetch(BASE + path, {
      ...options,
      headers: { "X-API-Key": apiKey, "Content-Type": "application/json" },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the API. Is it running?");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = detailToText(body.detail);
    } catch {
      // the body was not JSON: keep the default message
    }
    throw new ApiError(response.status, message);
  }
  return response.json();
}

export const checkKey = (key) => request(key, "/auth/check");

export function listTransactions(key, params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([name, value]) => {
    if (value !== "" && value !== null && value !== undefined) query.set(name, value);
  });
  return request(key, `/transactions?${query}`);
}

export const getTransaction = (key, id) => request(key, `/transactions/${id}`);

export const explainTransaction = (key, id, question) =>
  request(key, `/transactions/${id}/explain`, {
    method: "POST",
    body: JSON.stringify(question ? { question } : {}),
  });