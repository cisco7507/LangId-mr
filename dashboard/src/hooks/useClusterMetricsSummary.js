import { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export function useClusterMetricsSummary() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await apiFetch('/cluster/metrics-summary');
        if (!response.ok) {
          throw new Error(`Failed to fetch cluster metrics: ${response.statusText}`);
        }
        const jsonData = await response.json();
        setData(jsonData);
        setError(null);
        setLastUpdated(new Date());
      } catch (err) {
        console.error('Error fetching cluster metrics:', err);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);

    return () => clearInterval(interval);
  }, []);

  return { data, loading, error, lastUpdated };
}
