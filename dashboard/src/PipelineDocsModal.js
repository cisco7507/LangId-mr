import React, { useEffect, useRef } from "react";

export default function PipelineDocsModal({ open, onClose }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const node = dialogRef.current;
    if (!node) return;

    const onEsc = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onEsc);
    setTimeout(() => node.querySelector("#pipeline-close-btn")?.focus(), 0);

    return () => {
      document.removeEventListener("keydown", onEsc);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur"
      role="dialog"
      aria-modal="true"
    >
      <div
        ref={dialogRef}
        className="mx-2 max-h-[90vh] w-full max-w-3xl overflow-hidden rounded-xl border border-slate-700 bg-slate-900/95 shadow-2xl"
      >
  <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-50">
              LangID audio processing pipeline
            </h2>
            <p className="text-[11px] text-slate-400">
              How your audio becomes structured JSON in the dashboard.
            </p>
          </div>
          <button
            id="pipeline-close-btn"
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-600 bg-slate-800 px-2 py-1 text-[11px] font-medium text-slate-100 hover:bg-slate-700"
          >
            Close
          </button>
        </div>

        <div className="scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-slate-900 overflow-y-auto px-4 py-3 text-[13px] leading-relaxed text-slate-100 max-h-[70vh]">
          {/* 1. High-level overview */}
          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
              1. High-level overview
            </h3>
            <p>
              At a high level, each job goes through these stages before you see it in the
              dashboard:
            </p>
            <ol className="list-decimal space-y-1 pl-5 text-slate-200">
              <li>
                <strong>Input</strong> – Client uploads an audio file or provides a URL.
              </li>
              <li>
                <strong>Pre-processing</strong> – Audio is decoded and normalized to mono 16 kHz.
              </li>
              <li>
                <strong>Language gate (EN/FR only)</strong> – Decide whether the audio is English
                or French using direct model output, VAD retry, and scoring fallback.
              </li>
              <li>
                <strong>Transcription</strong> – Generate a transcript of the speech.
              </li>
              <li>
                <strong>Translation (optional)</strong> – If enabled, translate between EN and FR.
              </li>
              <li>
                <strong>Result packaging &amp; metrics</strong> – Build the final JSON, store it
                with the job, and update metrics.
              </li>
            </ol>
            <p className="text-[11px] text-slate-400">
              The JSON shown under <span className="font-mono">Raw model output</span> in the
              result modal is a direct view of the data produced at the end of this pipeline.
            </p>
          </section>

          {/* Video walkthrough (local MP4) */}
          <div className="mt-3">
            <div className="rounded-md border border-slate-700 bg-slate-950/80 p-3">
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-slate-300">
                Video walkthrough
              </p>
              <p className="mb-2 text-[11px] text-slate-400">
                A short video illustrating the full pipeline and EN/FR decision tree.
              </p>
              <video
                controls
                className="h-auto w-full rounded-md border border-slate-700 bg-black"
              >
                <source src="/pipeline.mp4" type="video/mp4" />
                Your browser does not support the video tag.
              </video>
            </div>
          </div>

          {/* Top-level pipeline diagram (static export from Mermaid) */}
          <div className="mt-3">
            <div className="rounded-md border border-slate-700 bg-slate-950/80 p-2 text-center text-[11px] text-slate-400">
              <p className="mb-2 font-medium uppercase tracking-wide text-slate-300">
                Top-level pipeline
              </p>
              <p className="mb-2">
                Diagram placeholder – export the Mermaid diagram from <span className="font-mono">PIPELINE.md</span>
                as <span className="font-mono">pipeline-overview.svg</span> and place it in
                <span className="font-mono"> dashboard/public/</span> to see it here.
              </p>
              <img
                src="/pipeline-overview.svg"
                alt="Top-level pipeline diagram: audio input to pre-processing to language gate to transcription to optional translation to result JSON and metrics."
                className="mx-auto max-h-72 w-full max-w-[720px] rounded border border-slate-700 bg-slate-950 object-contain"
              />
            </div>
          </div>

          {/* 2. Stages in more detail */}
          <section className="mt-4 space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
              2. Stages in more detail
            </h3>

            <p className="text-[12px] font-semibold text-slate-200">2.1 Input</p>
            <p>
              The client sends an audio file or a public URL. We validate the input (size,
              extension, basic checks) and persist a <span className="font-mono">Job</span> row
              with a UUID <span className="font-mono">id</span>,
              <span className="font-mono">status=&quot;queued&quot;</span>,
              <span className="font-mono">input_path</span>,
              <span className="font-mono">original_filename</span>, timestamps, and metadata.
            </p>

            <p className="text-[12px] font-semibold text-slate-200">2.2 Pre-processing</p>
            <p>
              Audio is loaded and converted to a uniform format: mono, 16 kHz sample rate, float32
              samples. We compute duration in seconds, later exposed as
              <span className="font-mono"> raw.info.duration</span>.
            </p>

            <p className="text-[12px] font-semibold text-slate-200">2.3 Language gate (EN/FR only)</p>
            <p>
              The language gate ensures we only accept English/French content and handles noisy or
              ambiguous cases. It combines direct autodetect, optional strict EN/FR rejection, a
              VAD retry on speech-only audio, and an EN-vs-FR scoring fallback. The final
              <span className="font-mono">language</span> and
              <span className="font-mono">probability</span> you see in the JSON come from this
              gate.
            </p>

            {/* Language gate decision tree diagram (static export from Mermaid) */}
            <div className="mt-3">
              <div className="rounded-md border border-slate-700 bg-slate-950/80 p-2 text-center text-[11px] text-slate-400">
                <p className="mb-2 font-medium uppercase tracking-wide text-slate-300">
                  Language gate decision tree
                </p>
                <p className="mb-2">
                  Diagram placeholder – export the EN/FR gate Mermaid diagram as
                  <span className="font-mono"> language-gate-decision-tree.svg</span> into
                  <span className="font-mono"> dashboard/public/</span> to see it here.
                </p>
                <img
                  src="/language-gate-decision-tree.svg"
                  alt="Decision tree diagram for the EN/FR language gate, including strict rejection, VAD retry, and fallback paths."
                  className="mx-auto max-h-80 w-full max-w-[720px] rounded border border-slate-700 bg-slate-950 object-contain"
                />
              </div>
            </div>

            <p className="text-[12px] font-semibold text-slate-200">2.4 Transcription</p>
            <p>
              Once the language is chosen, we run a transcription pass. The model returns the full
              transcript as <span className="font-mono">raw.text</span>. A shorter
              human-friendly snippet is exposed as <span className="font-mono">text</span> (or
              <span className="font-mono">transcript_snippet</span>) and shown in the dashboard.
            </p>

            <p className="text-[12px] font-semibold text-slate-200">2.5 Optional translation</p>
            <p>
              In deployments where translation is enabled, if the target language differs from the
              detected language we call a translation function. The
              <span className="font-mono"> translated</span> field indicates whether a
              translation step ran.
            </p>

            <p className="text-[12px] font-semibold text-slate-200">2.6 Result packaging &amp; metrics</p>
            <p>
              After language detection, transcription and optional translation, we build the final
              JSON, store it in the job record, and serve it from
              <span className="font-mono"> GET /jobs/&lt;job_id&gt;/result</span>. Metrics derived
              from these jobs power the dashboard cards (workload, processing time, error rate).
            </p>
          </section>

          {/* 3. Mapping JSON fields to pipeline stages */}
          <section className="mt-4 space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
              3. Mapping JSON fields to pipeline stages
            </h3>
            <p className="text-[11px] text-slate-400">
              This mirrors the legend in the modal and explains where each field comes from.
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-[11px]">
                <thead>
                  <tr className="bg-slate-900">
                    <th className="border border-slate-800 px-2 py-1 text-left font-medium text-slate-300">
                      Field
                    </th>
                    <th className="border border-slate-800 px-2 py-1 text-left font-medium text-slate-300">
                      Stage
                    </th>
                    <th className="border border-slate-800 px-2 py-1 text-left font-medium text-slate-300">
                      Meaning
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">language</td>
                    <td className="border border-slate-800 px-2 py-1">Language gate</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Final language code (<span className="font-mono">"en"</span>,
                      <span className="font-mono"> "fr"</span>).
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">probability</td>
                    <td className="border border-slate-800 px-2 py-1">Language gate</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Confidence in <span className="font-mono">language</span>, between 0 and 1.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">text</td>
                    <td className="border border-slate-800 px-2 py-1">Transcription</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Short human-friendly transcript snippet.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">processing_ms</td>
                    <td className="border border-slate-800 px-2 py-1">Result packaging</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Total processing time for this job in milliseconds.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">original_filename</td>
                    <td className="border border-slate-800 px-2 py-1">Input</td>
                    <td className="border border-slate-800 px-2 py-1">
                      File name you uploaded (or derived from the URL).
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">translated</td>
                    <td className="border border-slate-800 px-2 py-1">Translation</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Whether an additional translation step was applied.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">raw.text</td>
                    <td className="border border-slate-800 px-2 py-1">Transcription</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Full transcript returned by the model.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">raw.info.language</td>
                    <td className="border border-slate-800 px-2 py-1">Model internals</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Language predicted directly by the model.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">
                      raw.info.language_probability
                    </td>
                    <td className="border border-slate-800 px-2 py-1">Model internals</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Confidence for <span className="font-mono">raw.info.language</span>.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">raw.info.duration</td>
                    <td className="border border-slate-800 px-2 py-1">Pre-processing</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Original audio duration in seconds.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">
                      raw.info.duration_after_vad
                    </td>
                    <td className="border border-slate-800 px-2 py-1">VAD</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Duration of speech-only audio after voice activity detection.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">
                      raw.info.all_language_probs
                    </td>
                    <td className="border border-slate-800 px-2 py-1">Model internals</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Optional probability distribution over candidate languages.
                    </td>
                  </tr>
                  <tr>
                    <td className="border border-slate-800 px-2 py-1 font-mono">raw.info.vad_options</td>
                    <td className="border border-slate-800 px-2 py-1">VAD</td>
                    <td className="border border-slate-800 px-2 py-1">
                      Configuration options used by the VAD module.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section className="mt-4 space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
              4. Example: clean English audio (happy path)
            </h3>
            <p>
              For a short, clean English clip, the pipeline typically follows the happy path: the
              model predicts <span className="font-mono">"en"</span> with high probability, the
              gate accepts with method <span className="font-mono">autodetect</span>, and
              transcription runs once.
            </p>
            <pre className="text-[11px]"><code>{`{
  "language": "en",
  "probability": 0.99,
  "text": "So welcome back to the headspace journey, and today 21,",
  "raw": {
    "text": "So welcome back to the headspace journey, and today 21,",
    "info": {
      "language": "en",
      "language_probability": 1.0,
      "duration": 15.0,
      "duration_after_vad": 15.0,
      "all_language_probs": null,
      "vad_options": null
    }
  },
  "translated": false
}`}</code></pre>
          </section>

          <section className="mt-4 space-y-1 text-[11px] text-slate-400">
            <p>
              Backend implementation details live in the FastAPI service (e.g.
              <span className="font-mono"> app/lang_gate.py</span>,
              <span className="font-mono"> app/schemas.py</span> and the worker code that
              orchestrates each stage).
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
