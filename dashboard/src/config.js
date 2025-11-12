const apiBase =
  process.env.REACT_APP_API_URL ||
  (window.API_URL ?? "http://localhost:8080"); // fallback for manual override

export const API_BASE = apiBase.replace(/\/+$/, "");
