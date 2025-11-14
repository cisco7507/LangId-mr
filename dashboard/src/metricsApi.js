import { apiFetch } from "./api";

export async function fetchMetricsJson() {
  const response = await apiFetch("/metrics/json");
  if (!response.ok) {
    throw new Error(`Failed to fetch metrics: ${response.status}`);
  }
  return response.json();
}
