import { useState, useEffect } from "react";
import { apiFetch } from "../api";

export interface GatePathMetricsResponse {
  total_decisions: number;
  by_gate_path: Record<string, number>;
  percentages: Record<string, number>;
}

interface GatePathMetricsHook {
  data: GatePathMetricsResponse | null;
  loading: boolean;
  error: Error | null;
  lastUpdated: Date | null;
}

export function useGatePathMetrics(): GatePathMetricsHook {
  const [data, setData] = useState<GatePathMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchMetrics = async () => {
      try {
        const response = await apiFetch("/metrics/gate-paths");
        if (!response.ok) {
          throw new Error(`Failed to fetch gate path metrics: ${response.statusText}`);
        }
        const jsonData = (await response.json()) as GatePathMetricsResponse;

        if (!isMounted) {
          return;
        }

        setData(jsonData);
        setError(null);
        setLastUpdated(new Date());
      } catch (err) {
        console.error("Error fetching gate path metrics:", err);
        if (!isMounted) {
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10_000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return { data, loading, error, lastUpdated };
}
