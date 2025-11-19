import React, { useEffect, useRef, useState, useMemo } from "react";
import PipelineDocsModal from "./PipelineDocsModal.jsx";
import { API_BASE } from "./config";

const METHOD_DISPLAY = {
  autodetect: {
    label: "Autodetect",
    hint: "Accepted on the first pass",
  },
  "autodetect-vad": {
    label: "Autodetect + VAD",
    hint: "Accepted after VAD retry",
  },
  fallback: {
    label: "EN/FR fallback",
    hint: "Forced decision between EN and FR",
  },
};

export default function JobResultModal({ jobResult, onClose }) {
  const modalRef = useRef(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const [showPipelineDocs, setShowPipelineDocs] = useState(false);
  const [audioError, setAudioError] = useState(null);

  const derived = useMemo(() => {
    if (!result) return null;
    const language = result.language ?? "unknown";
    const probability = typeof result.probability === "number" ? result.probability : null;
    const processingMs = result.processing_ms;
    const transcript = result.transcript_snippet;
    const raw = result.raw ?? null;
    const originalFilename = result.original_filename ?? null;
    const detectionMethod =
      result.detection_method ??
      raw?.detection_method ??
      raw?.lang_gate?.method ??
      null;
    const langGate = raw?.lang_gate ?? null;
    return { language, probability, processingMs, transcript, raw, originalFilename, detectionMethod, langGate };
  }, [result]);

  // Fetch result when a (new) job arrives
  useEffect(() => {
    if (!jobResult) return;

    setResult(null);
    setError(null);
    setLoading(true);

    const ac = new AbortController();
    (async () => {
      try {
        const res = await fetch(
          `${API_BASE}/jobs/${jobResult.job_id}/result`,
          { signal: ac.signal, headers: { Accept: "application/json" } }
        );
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        const data = await res.json();
        setResult(data);
      } catch (e) {
        if (e.name !== "AbortError") setError(String(e));
      } finally {
        setLoading(false);
      }
    })();

    return () => ac.abort();
  }, [jobResult]);

  // Focus & escape/Tab trap
  useEffect(() => {
    if (!jobResult) return;
    const node = modalRef.current;
    const onEsc = (e) => e.key === "Escape" && onClose();
    const trap = (e) => {
      if (e.key !== "Tab") return;
      const els = node.querySelectorAll(
        'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
      );
      const first = els[0], last = els[els.length - 1];
      if (e.shiftKey ? document.activeElement === first : document.activeElement === last) {
        (e.shiftKey ? last : first).focus();
        e.preventDefault();
      }
    };
    document.addEventListener("keydown", onEsc);
    node.addEventListener("keydown", trap);
    document.body.style.overflow = "hidden";
    setTimeout(() => node.querySelector("#ok-btn")?.focus(), 0);

    return () => {
      document.removeEventListener("keydown", onEsc);
      node.removeEventListener("keydown", trap);
      document.body.style.overflow = "unset";
    };
  }, [jobResult, onClose]);

  if (!jobResult) return null;
  const title = error ? "Job Result (Error)" : "Job Result";

  const languageBadge = derived && (
    <LanguageBadge language={derived.language} />
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur"
      role="dialog"
      aria-modal="true"
    >
      <div
        ref={modalRef}
        className="relative mx-auto w-11/12 max-w-2xl rounded-xl border border-slate-200 bg-white p-5 shadow-2xl"
      >
        <div className="mt-1 text-left">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
              <p className="mt-1 text-xs text-slate-600">
                Click anywhere outside or press Escape to close.
              </p>
            </div>
            {languageBadge}
          </div>

          {/* Main content */}
          <div className="mt-4 space-y-4">
            {/* Loading / error state */}
            {loading && (
              <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
                Loading result…
              </div>
            )}

            {error && !loading && (
              <div className="rounded-md border border-rose-500/10 bg-rose-50 px-3 py-2 text-xs text-rose-800">
                {error}
              </div>
            )}

            {derived && !loading && !error && (
              <>
                {/* Summary row */}
                <div className="grid gap-3 md:grid-cols-5">
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      Job ID
                    </p>
                    <p className="mt-1 truncate font-mono text-xs text-slate-900">
                      {result.job_id}
                    </p>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      File
                    </p>
                    <p
                      className="mt-1 truncate text-xs text-slate-900"
                      title={derived.originalFilename || result.job_id}
                    >
                      {derived.originalFilename || "—"}
                    </p>
                  </div>

                  {/* Audio player */}
                  <div className="rounded-lg border border-slate-200 bg-white p-3 md:col-span-5">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      Audio
                    </p>
                    <div className="mt-2">
                      {result ? (
                        <>
                          <audio
                            key={result.job_id}
                            controls
                            className="w-full"
                            src={`${API_BASE}/jobs/${result.job_id}/audio`}
                            onError={() => setAudioError("Failed to load audio")}
                          >
                            Your browser does not support the audio element.
                          </audio>
                          <div className="mt-2 flex items-center justify-between gap-3">
                            <a
                              className="text-xs text-sky-600 underline"
                              href={`${API_BASE}/jobs/${result.job_id}/audio`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Open / download audio
                            </a>
                            {audioError && (
                              <span className="text-xs text-rose-600">{audioError}</span>
                            )}
                          </div>
                        </>
                      ) : (
                        <span className="text-xs text-slate-500">No audio available</span>
                      )}
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      Probability
                    </p>
                    <div className="mt-1 flex items-center justify-between text-xs text-slate-900">
                      <span>
                        {derived.probability != null
                          ? `${(derived.probability * 100).toFixed(1)}%`
                          : "—"}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-1.5 rounded-full bg-gradient-to-r from-emerald-400 to-sky-400"
                        style={{
                          width:
                            derived.probability != null
                              ? `${Math.max(0, Math.min(100, derived.probability * 100))}%`
                              : "0%",
                        }}
                      />
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      Processing time
                    </p>
                    <p className="mt-1 text-xs text-slate-900">
                      {derived.processingMs != null
                        ? `${(derived.processingMs / 1000).toFixed(2)} s`
                        : "—"}
                    </p>
                  </div>

                  <DetectionMethodCard
                    method={derived.detectionMethod}
                    langGate={derived.langGate}
                  />
                </div>

                {/* Transcript snippet */}
                {derived.transcript && (
                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-slate-600">
                      Transcript snippet
                    </p>
                    <p className="mt-1 text-sm text-slate-700">
                      {derived.transcript}
                    </p>
                  </div>
                )}

                {/* Raw JSON toggle */}
                {derived.raw && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                      onClick={() => setShowRaw((prev) => !prev)}
                    >
                      <span>Raw model output</span>
                      <span className="text-[10px] uppercase tracking-wide text-slate-600">
                        {showRaw ? "Hide" : "Show"}
                      </span>
                    </button>
                    {showRaw && (
                      <div className="max-h-72 overflow-auto border-t border-slate-200 px-3 py-2 text-[11px] leading-relaxed text-slate-700 space-y-2">
                        <div className="rounded-md bg-slate-50 p-2 text-[10px] text-slate-700">
                          <p className="mb-1 font-semibold text-slate-900">How to read this JSON</p>
                          <ul className="list-disc space-y-0.5 pl-4">
                            <li><span className="font-mono">language</span>: ISO language code predicted for the audio (e.g. <span className="font-mono">"en"</span>, <span className="font-mono">"fr"</span>).</li>
                            <li><span className="font-mono">probability</span>: Confidence for <span className="font-mono">language</span>, from 0 to 1.</li>
                            <li><span className="font-mono">text</span>: Transcript snippet of what was detected in the audio.</li>
                            <li><span className="font-mono">raw.text</span>: Full transcript returned by the underlying model.</li>
                            <li><span className="font-mono">raw.info.language</span>: Language code reported by the model internals.</li>
                            <li><span className="font-mono">raw.info.language_probability</span>: Confidence for that internal language, from 0 to 1.</li>
                            <li><span className="font-mono">raw.info.duration</span>: Total audio duration in seconds.</li>
                            <li><span className="font-mono">raw.info.duration_after_vad</span>: Duration after voice activity detection (speech-only part) in seconds.</li>
                            <li><span className="font-mono">raw.info.all_language_probs</span>: If present, probability distribution over all candidate languages.</li>
                            <li><span className="font-mono">raw.info.vad_options</span>: Voice activity detection parameters used for this run (if any).</li>
                            <li><span className="font-mono">raw.lang_gate</span>: Snapshot of the EN/FR gate decision (language, probability, method) before packaging.</li>
                            <li><span className="font-mono">translated</span>: Whether a translation step was applied on top of the original audio.</li>
                          </ul>
                          <button
                            type="button"
                            className="mt-2 text-[10px] font-medium text-emerald-600 underline hover:text-emerald-500"
                            onClick={() => setShowPipelineDocs(true)}
                          >
                            Open full pipeline documentation
                          </button>
                        </div>
                        <pre className="whitespace-pre-wrap break-words font-mono">
                          {JSON.stringify(derived.raw, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          <div className="mt-4 flex justify-end gap-2 px-1">
            <button
              id="ok-btn"
              className="rounded-md bg-slate-100 px-4 py-2 text-sm font-medium text-slate-900 shadow-sm hover:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400"
              onClick={onClose}
            >
              Close
            </button>
          </div>
        </div>
      </div>
      <PipelineDocsModal open={showPipelineDocs} onClose={() => setShowPipelineDocs(false)} />
    </div>
  );
}

function LanguageBadge({ language }) {
  let label = "Unknown";
  let classes = "bg-slate-100 text-slate-800";

  if (language === "en") {
    label = "English";
    classes = "bg-emerald-100 text-emerald-800 border border-emerald-200";
  } else if (language === "fr") {
    label = "French";
    classes = "bg-sky-100 text-sky-800 border border-sky-200";
  }

  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${classes}`}>
      <span className="mr-1 inline-block h-2 w-2 rounded-full bg-current" />
      {label}
    </span>
  );
}

function DetectionMethodCard({ method, langGate }) {
  const display = METHOD_DISPLAY[method] ?? {
    label: method ?? "Unknown",
    hint: "Language gate branch",
  };
  const confidence =
    typeof langGate?.probability === "number" ? `${(langGate.probability * 100).toFixed(1)}%` : "—";
  const gateLanguage = langGate?.language ?? "—";

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-600">
        Detection method
      </p>
      <p className="mt-1 text-xs font-semibold text-slate-900">{display.label}</p>
      <p className="text-[10px] text-slate-600">{display.hint}</p>
      <div className="mt-2 space-y-0.5 text-[11px] text-slate-700">
        <p>Gate language: {gateLanguage}</p>
        <p>Gate confidence: {confidence}</p>
      </div>
    </div>
  );
}
