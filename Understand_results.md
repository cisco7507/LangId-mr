# Language Gate Result Analysis

## Context
- **Jobs analyzed:** `node-a-5df5527f-50a3-4bf8-aaa3-708ee5b08cc9` and `node-a-d88aadcb-5c35-4e74-b7a7-55e80c60a15b`
- **Audio source:** Both jobs reference identical uploads stored at `langid_service/storage/node-a-5df5527f-50a3-4bf8-aaa3-708ee5b08cc9.wav` and `langid_service/storage/node-a-d88aadcb-5c35-4e74-b7a7-55e80c60a15b.wav` (SHA-1 `7d566a79eb76bfb7a065e1c459a8e4c9a537ce7e`). The original recording corresponds to `1MBM0023000H_ATS-51.wav` from the stability harness.
- **Why the comparison matters:** Even when the waveform is identical, our EN/FR gate can diverge because the first-pass Whisper transcript may or may not include enough stopwords (frequent grammatical function words). The speechiness heuristic keys off those stopword ratios to decide whether to trust the initial decode or escalate to a VAD-assisted retry.

## Log Timelines With Commentary

### Job node-a-5df5527f-50a3-4bf8-aaa3-708ee5b08cc9 (High-confidence accept)
- `2025-11-30 18:28:11.691 | ... | create_job_local`  
  _Comment:_ Upload stored and moved into `storage/` under the job-specific filename.
- `2025-11-30 18:28:11.746 | ... | process_one:30 - Processing job ...`  
  _Comment:_ Worker pulled the job from the queue; no retries yet.
- `2025-11-30 18:28:11.843 | DEBUG | job=... | detect_lang_en_fr_only:278 - Lang gate pipeline start`  
  _Comment:_ Gate begins by extracting the first 30 s probe and loading Whisper with `vad_filter=False`.
- `2025-11-30 18:29:50.831 | INFO | ...:289 - detect(probe): autodetect=fr p=0.91`  
  _Comment:_ Greedy pass (beam_size=1, best_of=1) predicted French with probability 0.91.
- `2025-11-30 18:29:50.831 | DEBUG | ...:295 - Gate transcript`  
  _Comment:_ Captured the raw Whisper transcript, which already contains many conversational tokens.
- `2025-11-30 18:29:50.831 | DEBUG | ...:301 - Gate tokens`  
  _Comment:_ Shows tokenization after splitting by `TOKEN_SPLIT_RE`; required for stopword math.
- `2025-11-30 18:29:50.832 | DEBUG | ...:305 - Stopword ratios`  
  _Comment:_ Computed French stopword ratio of 0.28, English ratio 0.00—well above `MIN_STOPWORD_FOR_SPEECH` (0.10).
- `2025-11-30 18:29:50.832 | INFO | ...:333 - Autodetect high confidence with speechy transcript: lang=fr p=0.91 tokens=65 en_ratio=0.00 fr_ratio=0.28`  
  _Comment:_ Speechiness heuristic passed: token_count (65) ≥ 6 and dominant stopword ratio ≥ 0.10, so the pipeline accepted without VAD.
- `2025-11-30 18:29:55.906 | INFO | job=- | process_one:170 - Job ... succeeded`  
  _Comment:_ Worker committed the result payload and marked the job done (method `autodetect`).

### Job node-a-d88aadcb-5c35-4e74-b7a7-55e80c60a15b (VAD-assisted accept)
- `2025-11-30 18:28:11.735 | INFO | ... | create_job_local`  
  _Comment:_ Same upload stored under a different job ID only milliseconds later.
- `2025-11-30 18:28:26.593 | INFO | job=- | process_one:30 - Processing job ...`  
  _Comment:_ Another worker thread acquired the job and loaded the cached audio into memory.
- `2025-11-30 18:28:26.786 | DEBUG | job=... | detect_lang_en_fr_only:278 - Lang gate pipeline start`  
  _Comment:_ Probe extraction identical to the other job; both share the same 30 s slice.
- `2025-11-30 18:29:42.871 | INFO | job=... | ...:289 - detect(probe): autodetect=fr p=0.91`  
  _Comment:_ The non-VAD decode again judged the clip as French with probability 0.91.
- `2025-11-30 18:29:42.871 | DEBUG | ...:295 - Gate transcript`  
  _Comment:_ Transcript captured, but this time Whisper produced mostly proper nouns / tags with very few function words.
- `2025-11-30 18:29:42.871 | DEBUG | ...:301 - Gate tokens`  
  _Comment:_ Token list reveals the scarcity of stopwords, causing the downstream ratio to fall below thresholds.
- `2025-11-30 18:29:42.871 | DEBUG | ...:305 - Stopword ratios`  
  _Comment:_ Dominant ratio dropped under `MIN_STOPWORD_FOR_SPEECH`; despite high probability, lexical evidence looked unspeechy.
- `2025-11-30 18:29:42.871 | INFO | ...:351 - High prob but transcript not speechy enough ...`  
  _Comment:_ Speechiness guardrail fired. Without enough stopwords, we don’t trust the first pass and must retry with VAD.
- `2025-11-30 18:29:42.871 | DEBUG | ...:360 - Speechiness failed`  
  _Comment:_ Diagnostic detail logging the failing ratios vs. the `0.10` threshold.
- `2025-11-30 18:29:42.872 | INFO | ...:424 - Initial detection insufficient; re-trying with VAD on probe.`  
  _Comment:_ Pipeline schedules a second Whisper pass with `vad_filter=True` to remove silence/background energy.
- `2025-11-30 18:29:42.872 | DEBUG | ...:425 - Scheduling VAD retry`  
  _Comment:_ Captures the parameters (probability, detected language) that triggered the retry decision.
- `2025-11-30 18:29:44.276 | INFO | ...:430 - detect(probe, VAD): autodetect=fr p=0.95`  
  _Comment:_ VAD-assisted pass increased the posterior to 0.95 because the decoder saw only speechy frames.
- `2025-11-30 18:29:51.779 | DEBUG | ...:438 - VAD transcript`  
  _Comment:_ Shows the cleaned-up transcript produced after VAD, now rich in stopwords.
- `2025-11-30 18:29:51.779 | INFO | ...:459 - Autodetect successful [via VAD]: lang=fr, p=0.95 (threshold=0.60)`  
  _Comment:_ Gate accepts the VAD result; `method` flips to `autodetect-vad`, and `gate_decision` records `vad_retry`.
- `2025-11-30 18:29:51.780 | DEBUG | ...:462 - VAD acceptance detail`  
  _Comment:_ Persists token counts and stopword ratios for the VAD transcript.
- `2025-11-30 18:29:56.780 | INFO | job=- | process_one:170 - Job ... succeeded`  
  _Comment:_ Worker serializes the result JSON (with `use_vad=True`) and marks the job complete.

## Root Cause (Deep Dive)
1. **Decoder non-determinism:** The first probe uses `beam_size=1`/`best_of=1` for latency. With those greedy hyperparameters, `faster-whisper` may return slightly different transcripts for the same waveform across invocations. Concurrent inference exacerbates this because multiple jobs share the same model instance, affecting temperature fallback and sampling order. In our case, one run emitted abundant French stopwords, the other emitted mostly proper nouns or music markers.
2. **Stopword ratio (speechiness heuristic):** After tokenization (`TOKEN_SPLIT_RE`), we compute `stopword_ratio = stopword_hits / total_tokens` for our curated EN/FR stopword sets. The guardrail requires ≥6 tokens and ≥0.10 ratio for high-confidence shortcuts. This protects against music-only clips that still get high `language_probability`. Job `node-a-5df...` passed because the transcript contained 65 tokens with 28% French stopwords. Job `node-a-d88...` failed because the ratio dipped below 0.10, so we deliberately refused to trust the first decode.
3. **VAD (voice activity detection) retry logic:** When speechiness fails—or when probability drops into mid/low zones—the gate calls Whisper again with `vad_filter=True`. VAD trims non-speech energy, so the second decode focuses on voiced segments and typically increases stopword ratios and probabilities. That is exactly what happened for `node-a-d88...`: probability jumped from 0.91 to 0.95, the transcript became speechier, and the gate accepted with `method="autodetect-vad"`.
4. **Fallback safeguards:** If VAD also failed (e.g., probability < 0.60), we would enter the fallback scoring probe (`pick_en_or_fr_by_scoring`) which transcribes the probe in forced-English and forced-French modes, comparing average log probabilities. Neither job needed this final tier because VAD succeeded.

## Glossary of Terms Referenced
- **Probe:** Fixed-duration slice (30 seconds at 16 kHz) sampled from the start of the clip to keep gating latency bounded.
- **Stopword:** Highly frequent function word (e.g., *le, la, et, mais*). High stopword ratios correlate with conversational speech; low ratios suggest tags, noise markers, or music annotations.
- **Token:** The smallest text unit we analyze after transcription. We split the transcript using `TOKEN_SPLIT_RE`, lowercase everything, and drop empty strings, so an utterance like “Well, it's” becomes `["well", "it's"]`. Token counts feed directly into the speechiness heuristic and stopword ratios.
- **Speechiness heuristic:** The combination of minimum token count and stopword ratio thresholds used to auto-accept high-confidence detections without resorting to VAD.
- **VAD (Voice Activity Detection):** An energy-based pre-processing step that removes non-speech segments so Whisper focuses on voiced regions, improving transcription quality in noisy or music-heavy inputs.
- **Fallback scoring probe:** Cheap LangID routine that forces Whisper to decode the same probe twice (once per language) with `beam_size=1/best_of=1` and compares mean `avg_logprob` to pick the least-worst language when all other heuristics fail.

## Conclusion
Both jobs consumed identical audio, but subtle differences in the greedy Whisper transcript triggered different branches of the gate: one satisfied the speechiness heuristic immediately, the other required a VAD retry. The guardrails are behaving as intended—forcing additional scrutiny whenever the lexical distribution looks music-heavy or sparse, even if the raw language probability is high.

---

## Additional Example: Standalone Job `standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611`

- **Audio:** Uploaded by the standalone harness from `CA330538-51.wav`, stored at `langid_service/storage/standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611.wav`.
- **Timeline:**
  - `19:04:47.690` — upload persisted locally (log line 388).
  - `19:05:01.013` — worker started processing the job (line 447) and entered the gate at `19:05:01.051` (line 448).
  - `19:05:15.895` — first probe (no VAD) produced `language=en`, `p=0.62` with a transcript token count of 11 and English stopword ratio of 0.27 (lines 485‑489).
  - `19:05:21.379` — worker marked the job succeeded (line 503), finalizing the snippet “Well, it's for the one, uh, V is very, very…”.
- **Log excerpt:**
  ```
  2025-11-30 19:04:47.690 | INFO  | job=- | langid_service.app.main:create_job_local:351 - Enqueued upload for job standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611: /Users/gsp/Projects/LangId-mr/langid_service/storage/standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611.wav
  2025-11-30 19:05:01.013 | INFO  | job=- | langid_service.app.worker.runner:process_one:30 - Processing job standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611
  2025-11-30 19:05:01.051 | DEBUG | job=standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611 | langid_service.app.lang_gate:detect_lang_en_fr_only:304 - Lang gate pipeline start
  2025-11-30 19:05:15.895 | INFO  | job=standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611 | langid_service.app.lang_gate:detect_lang_en_fr_only:315 - detect(probe): autodetect=en p=0.62
  2025-11-30 19:05:15.895 | DEBUG | job=standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611 | langid_service.app.lang_gate:detect_lang_en_fr_only:321 - Gate transcript
  2025-11-30 19:05:15.895 | DEBUG | job=standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611 | langid_service.app.lang_gate:detect_lang_en_fr_only:327 - Gate tokens
  2025-11-30 19:05:15.895 | DEBUG | job=standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611 | langid_service.app.lang_gate:detect_lang_en_fr_only:331 - Stopword ratios
  2025-11-30 19:05:15.895 | INFO  | job=standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611 | langid_service.app.lang_gate:detect_lang_en_fr_only:399 - Autodetect mid-zone accepted (EN): p=0.62, en_ratio=0.27, fr_ratio=0.00, tokens=11
  2025-11-30 19:05:21.379 | INFO  | job=- | langid_service.app.worker.runner:process_one:170 - Job standalone-aa4acbe9-a2c8-4a20-a170-f27a12cad611 succeeded
  ```
- **Gate Behavior:** Because the probability sat in the mid-zone (0.60 ≤ p < 0.79) and the stopword ratio cleared the English threshold (0.27 ≥ 0.15 with zero French stopwords), the guard accepted via the EN mid-zone heuristic without VAD. No retries or fallback scoring were required.
- **Result JSON excerpt:**
  ```json
  {
    "language": "en",
    "probability": 0.6249,
    "detection_method": "autodetect",
    "gate_decision": "accepted_mid_zone_en",
    "gate_meta": {
      "token_count": 11,
      "stopword_ratio_en": 0.2727,
      "stopword_ratio_fr": 0.0,
      "vad_used": false
    },
    "text": "Well, it's for the one, uh, V is very, very"
  }
  ```
- **Takeaway:** Even at relatively modest probabilities (~0.62), the mid-zone heuristic can confidently pass English clips when the lexical footprint is speech-like (sufficient tokens plus a healthy stopword ratio). This example also shows how filler words (“well”, “uh”) help satisfy the heuristic without invoking VAD, keeping latency low.
