import { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export function useGatePathMetrics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await apiFetch('/metrics/gate-paths');
        if (!response.ok) {
          throw new Error(`Failed to fetch gate path metrics: ${response.statusText}`);
        }
        const jsonData = await response.json();
        setData(jsonData);
        setError(null);
        setLastUpdated(new Date());
      } catch (err) {
        console.error('Error fetching gate path metrics:', err);
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
