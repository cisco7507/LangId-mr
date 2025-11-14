// src/App.js
import React, { useState, useEffect, useMemo } from "react";
import JobResultModal from "./JobResultModal";
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

  // Select all checkbox
  const handleSelectAllClick = (event) => {
    if (event.target.checked) {
      const allJobIds = jobs.map((job) => job.job_id);
      setSelectedJobs(allJobIds);
    } else {
      setSelectedJobs([]);
    }
  };

  // Individual checkbox click
  const handleCheckboxClick = (event, jobId) => {
    event.stopPropagation();
    if (event.target.checked) {
      setSelectedJobs((prevSelected) => [...prevSelected, jobId]);
    } else {
      setSelectedJobs((prevSelected) => prevSelected.filter((id) => id !== jobId));
    }
  };

  // Row click → fetch job result if succeeded
  const handleRowClick = (job) => {
    if (job.status === "succeeded") {
      // We pass the job itself; JobResultModal refetches details
      setSelectedJobResult({ job_id: job.job_id });
    }
  };

  const handleCloseModal = () => {
    setSelectedJobResult(null);
  };

  // Delete selected jobs
  const handleDeleteClick = () => {
    if (selectedJobs.length === 0) return;

    apiFetch(`/jobs`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_ids: selectedJobs }),
    })
      .then((response) => {
        if (response.ok) {
          setJobs((prevJobs) => prevJobs.filter((job) => !selectedJobs.includes(job.job_id)));
          setSelectedJobs([]);
        } else {
          console.error('Failed to delete jobs');
        }
      })
      .catch((error) => console.error('Error deleting jobs:', error));
  };

  // Periodically refresh job list
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

  // Periodically fetch metrics JSON
  useEffect(() => {
    const loadMetrics = () => {
      fetchMetricsJson()
        .then((data) => {
          setMetrics(data);
        });
    };

    loadMetrics();
    const interval = setInterval(loadMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  const stats = useMemo(() => {
    const total = jobs.length;
    const succeeded = jobs.filter((j) => j.status === "succeeded").length;
    const failed = jobs.filter((j) => j.status === "failed").length;
    const processing = jobs.filter((j) => j.status === "processing").length;
    return { total, succeeded, failed, processing };
  }, [jobs]);

  const metricsSummary = useMemo(() => {
    if (!metrics) return null;
    const jobsTotal = metrics.jobs?.total ?? 0;
    const failed = metrics.jobs?.by_status?.failed ?? 0;
    const errorRate = jobsTotal > 0 ? (failed / jobsTotal) * 100 : 0;

    const queued = metrics.jobs?.queued ?? 0;
    const recentCompleted = metrics.jobs?.recent_completed_5m ?? 0;
    const avgProcessing =
      metrics.timing?.avg_processing_seconds_last_50 ?? 0;

    const workersConfigured = metrics.workers?.configured ?? null;

    return {
      errorRate,
      queued,
      recentCompleted,
      avgProcessing,
      workersConfigured,
    };
  }, [metrics]);

  const probabilityColor = (p) => {
    if (typeof p !== "number") return "bg-slate-700 text-slate-50";
    if (p >= 0.9) return "bg-emerald-500/20 text-emerald-200 border border-emerald-500/40";
    if (p >= 0.7) return "bg-sky-500/20 text-sky-200 border border-sky-500/40";
    if (p >= 0.4) return "bg-amber-500/20 text-amber-200 border border-amber-500/40";
    return "bg-rose-500/20 text-rose-200 border border-rose-500/40";
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-2 sm:px-4 py-4 sm:py-6">
        {/* Top bar */}
        <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
              LangID Job Dashboard
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Monitor EN/FR language detection jobs and inspect detailed results.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            <span>API online</span>
          </div>
        </header>

        {/* Metrics overview */}
        <section className="mb-6 grid gap-4 md:grid-cols-3">
          {/* Workload */}
          <div className="grid grid-cols-2 gap-3">
            <StatCard label="Total jobs" value={stats.total} />
            <StatCard
              label="Queued"
              value={metricsSummary?.queued ?? 0}
              accent="info"
            />
            <StatCard
              label="Processing"
              value={stats.processing}
              accent="info"
            />
            <StatCard
              label="Succeeded"
              value={stats.succeeded}
              accent="success"
            />
          </div>

          {/* Quality */}
          <div className="grid grid-cols-1 gap-3">
            <StatCard
              label="Failed"
              value={stats.failed}
              accent="danger"
            />
            <StatCard
              label="Error rate"
              value={`${(metricsSummary?.errorRate ?? 0).toFixed(1)}%`}
              accent="danger"
            />
          </div>

          {/* Performance & capacity */}
          <div className="grid grid-cols-1 gap-3">
            <StatCard
              label="Avg processing (last 50)"
              value={
                metricsSummary
                  ? `${metricsSummary.avgProcessing.toFixed(2)}s`
                  : "—"
              }
            />
            <StatCard
              label="Completed (last 5m)"
              value={metricsSummary?.recentCompleted ?? 0}
              accent="success"
            />
            {metricsSummary?.workersConfigured != null && (
              <StatCard
                label="Workers configured"
                value={metricsSummary.workersConfigured}
              />
            )}
          </div>
        </section>

    {/* Jobs table & actions */}
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 shadow-sm backdrop-blur">
          <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">
            <div className="flex items-center justify-between gap-3">
              <span>Jobs</span>
              <button
                className="inline-flex items-center gap-2 rounded-md bg-rose-500 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:bg-rose-900/40 disabled:text-slate-500"
                disabled={selectedJobs.length === 0}
                onClick={handleDeleteClick}
              >
                <span className="inline-block h-2 w-2 rounded-full bg-white/70" />
                Delete selected
                {selectedJobs.length > 0 && (
                  <span className="ml-1 rounded-full bg-rose-600 px-2 py-0.5 text-[10px]">
                    {selectedJobs.length}
                  </span>
                )}
              </button>
            </div>
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
                      onChange={handleSelectAllClick}
                      checked={selectedJobs.length === jobs.length && jobs.length > 0}
                    />
                  </th>
                  <th className="px-4 py-3">Job ID</th>
                  <th className="px-4 py-3">File</th>
                  <th className="px-4 py-3">Language</th>
                  <th className="px-4 py-3">Prob.</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="px-4 py-3">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {jobs.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-8 text-center text-sm text-slate-500"
                    >
                      No jobs yet. Submit audio to the LangID API to see them appear here.
                    </td>
                  </tr>
                )}
                {jobs.map((job) => {
                  const isClickable = job.status === "succeeded";
                  return (
                    <tr
                      key={job.job_id}
                      onClick={() => isClickable && handleRowClick(job)}
                      className={
                        "transition hover:bg-slate-800/60 " +
                        (isClickable ? "cursor-pointer" : "cursor-default")
                      }
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
                          checked={selectedJobs.includes(job.job_id)}
                          onClick={(event) => event.stopPropagation()}
                          onChange={(event) => handleCheckboxClick(event, job.job_id)}
                        />
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-200 truncate">
                        {job.job_id}
                      </td>
                      <td
                        className="px-4 py-3 text-xs text-slate-300 max-w-xs truncate"
                        title={job.original_filename || job.filename || job.job_id}
                      >
                        {job.original_filename || job.filename || ""}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {job.language ? (
                          <span className="inline-flex items-center rounded-full bg-slate-800 px-2 py-0.5 text-[11px] font-medium text-slate-100">
                            {job.language.toUpperCase()}
                          </span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {typeof job.probability === "number" ? (
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${probabilityColor(
                              job.probability
                            )}`}
                          >
                            {(job.probability * 100).toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={job.status} />
                      </td>
                      <td className="px-4 py-3">
                        <ProgressBar value={job.progress} />
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">
                        {job.created_at}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">
                        {job.updated_at}
                      </td>
                      <td className="px-4 py-3 text-xs text-rose-300">
                        <div className="max-h-12 overflow-y-auto whitespace-normal break-words">
                          {job.error}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {selectedJobResult && (
          <JobResultModal jobResult={selectedJobResult} onClose={handleCloseModal} />
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, accent }) {
  const accentClasses = {
    success: "border-emerald-500/40 bg-emerald-950/40",
    danger: "border-rose-500/40 bg-rose-950/40",
    info: "border-sky-500/40 bg-sky-950/40",
  };
  return (
    <div
      className={`rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3 shadow-sm ${
        accent ? accentClasses[accent] ?? "" : ""
      }`}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold text-slate-50">{value}</p>
    </div>
  );
}

export default App;