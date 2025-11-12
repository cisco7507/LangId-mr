import React, { useEffect, useRef, useState } from "react";
import { API_BASE } from "./config";

export default function JobResultModal({ jobResult, onClose }) {
  const modalRef = useRef(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="fixed inset-0 bg-gray-600/50 flex items-center justify-center" role="dialog" aria-modal="true">
      <div ref={modalRef} className="relative mx-auto p-5 border w-11/12 md:w-1/2 lg:w-1/3 shadow-lg rounded-md bg-white">
        <div className="mt-3 text-center">
          <h3 className="text-lg leading-6 font-medium text-gray-900">{title}</h3>
          <div className="mt-2 px-7 py-3">
            <pre className="whitespace-pre-wrap break-words text-left bg-gray-50 rounded p-3 text-sm">
              {loading ? "Loading…" : error ? error : JSON.stringify(result, null, 2)}
            </pre>
          </div>
          <div className="items-center px-4 py-3">
            <button
              id="ok-btn"
              className="px-4 py-2 bg-blue-500 text-white text-base font-medium rounded-md w-full shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
              onClick={onClose}
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}