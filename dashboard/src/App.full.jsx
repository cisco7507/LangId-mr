// Full application backup — heavy App moved here temporarily to unblock dev server.
// Restore by swapping imports in `src/main.jsx` when ready to debug transforms.

import React, { useState, useEffect, useMemo } from "react";
import JobResultModal from "./JobResultModal.jsx";
import { apiFetch } from "./api";
import { fetchMetricsJson } from "./metricsApi";

function StatusBadge({ status }) {
  const base =
    "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  const styles = {
    queued: "bg-slate-100 text-slate-800",
    processing: "bg-blue-100 text-blue-800",
    succeeded: "bg-emerald-100 text-emerald-800",
    failed: "bg-rose-100 text-rose-800",
  };
  const label = status ? status.charAt(0).toUpperCase() + status.slice(1) : "";
  return <span className={`${base} ${styles[status] || "bg-slate-100"}`}>{label}</span>;
}

function ProgressBar({ value }) {
  const v = typeof value === "number" ? Math.max(0, Math.min(100, value)) : 0;
  return (
    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
      <div
        className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all"
        style={{ width: `${v}%` }}
      />
    </div>
  );
}

function App() {
  const [jobs, setJobs] = useState([]);
  const [selectedJobs, setSelectedJobs] = useState([]);
  const [selectedJobResult, setSelectedJobResult] = useState(null);
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    const fetchData = () => {
      apiFetch("/jobs")
        .then((response) => response.json())
        .then((data) => setJobs(data.jobs || []))
        .catch((error) => console.error("Error fetching jobs:", error));
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const loadMetrics = () => {
      fetchMetricsJson()
        .then((data) => {
          setMetrics(data);
        })
        .catch(() => {});
    };
    loadMetrics();
    const interval = setInterval(loadMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <div className="mx-auto max-w-7xl px-2 sm:px-4 py-4 sm:py-6">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold">LangID Job Dashboard</h1>
          <p className="text-sm text-slate-600">Development-only backup of the full App.</p>
        </header>

        <section>
          <p className="text-sm">Jobs: {jobs.length}</p>
          <p className="text-sm">Workers: {metrics?.workers?.configured ?? "-"}</p>
        </section>

        {selectedJobResult && (
          <JobResultModal jobResult={selectedJobResult} onClose={() => setSelectedJobResult(null)} />
        )}
      </div>
    </div>
  );
}

export default App;
