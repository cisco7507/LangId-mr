#!/usr/bin/env bash
set -euo pipefail

# Defaults
API_BASE_URL="http://localhost:8080"
RUNS=10
POLL_INTERVAL=5
TIMEOUT=600
DIR=""

usage() {
  cat <<EOF
Usage: $(basename "$0") -d DIR [-n RUNS] [-a API_BASE_URL] [-p POLL_INTERVAL] [-t TIMEOUT]

  -d, --dir DIR           Directory containing audio files (required)
  -n, --runs N            Number of runs per file (default: ${RUNS})
  -a, --api URL           LangID API base URL (default: ${API_BASE_URL})
  -p, --poll-interval SEC Poll interval in seconds (default: ${POLL_INTERVAL})
  -t, --timeout SEC       Timeout per file in seconds (default: ${TIMEOUT})

Example:
  $(basename "$0") -d /path/to/wavs -n 10 -a http://localhost:8080
EOF
}

# ----------------- ARG PARSING -----------------
if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dir)
      DIR="$2"
      shift 2
      ;;
    -n|--runs)
      RUNS="$2"
      shift 2
      ;;
    -a|--api)
      API_BASE_URL="$2"
      shift 2
      ;;
    -p|--poll-interval)
      POLL_INTERVAL="$2"
      shift 2
      ;;
    -t|--timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${DIR}" ]]; then
  echo "ERROR: -d|--dir is required." >&2
  usage
  exit 1
fi

if [[ ! -d "${DIR}" ]]; then
  echo "ERROR: Directory does not exist: ${DIR}" >&2
  exit 1
fi

# ----------------- DISCOVER FILES -----------------
shopt -s nullglob
files=( "${DIR}"/*.wav "${DIR}"/*.mp3 "${DIR}"/*.m4a )
shopt -u nullglob

if (( ${#files[@]} == 0 )); then
  echo "No audio files found in ${DIR} (looked for *.wav, *.mp3, *.m4a)" >&2
  exit 1
fi

echo "Directory        : ${DIR}"
echo "API base URL     : ${API_BASE_URL}"
echo "Runs per file    : ${RUNS}"
echo "Poll interval    : ${POLL_INTERVAL}s"
echo "Timeout per file : ${TIMEOUT}s"
echo "Found ${#files[@]} audio file(s):"
for f in "${files[@]}"; do
  echo "  - $(basename "$f")"
done
echo

SUMMARY_LINES=()
MD_REPORT=""

# ----------------- MAIN LOOP PER FILE -----------------
for file in "${files[@]}"; do
  basename=$(basename "${file}")
  echo "============================================================"
  echo "FILE: ${basename}"
  echo "============================================================"

  printf "%-4s %-36s %-15s %-11s %-18s %-10s %-10s %s\n" \
    "Run" "JobId" "Language" "Prob" "GateDecision" "Pipeline" "MusicOnly" "TranscriptSnippet"
  printf "%-4s %-36s %-15s %-11s %-18s %-10s %-10s %s\n" \
    "----" "------------------------------------" "--------------" "-----------" "------------------" "----------" "----------" "-----------------"

  # Baseline fields from the first successful run
  base_language=""
  base_gate_decision=""
  base_pipeline=""
  base_music_only=""
  base_detection_method=""
  baseline_initialized=0

  file_inconsistent=0

  # Arrays to track jobs and results
  declare -a job_ids
  declare -a statuses
  declare -a finished
  declare -a results_json

  echo "Submitting ${RUNS} jobs for ${basename} (in parallel)..."

  # Arrays to track submit pids and temp files for responses
  declare -a submit_pids
  declare -a submit_tmpfiles

  for (( i=1; i<=RUNS; i++ )); do
    tmpfile=$(mktemp)
    submit_tmpfiles[i]="${tmpfile}"

    # Fire-and-forget submit; response is captured to a temp file
    curl -s -X POST -F "file=@${file}" "${API_BASE_URL}/jobs" > "${tmpfile}" &
    submit_pids[i]=$!
  done

  # Wait for all submit calls to finish, then parse responses
  for (( i=1; i<=RUNS; i++ )); do
    pid="${submit_pids[i]:-}"
    tmpfile="${submit_tmpfiles[i]:-}"

    if [[ -n "${pid}" ]]; then
      wait "${pid}" || true
    fi

    if [[ -z "${tmpfile}" || ! -f "${tmpfile}" ]]; then
      echo "ERROR: Missing submit response for run #${i}" >&2
      job_ids[i]=""
      statuses[i]="submit_error"
      finished[i]=1
      file_inconsistent=1
      continue
    fi

    submit_resp=$(cat "${tmpfile}")
    rm -f "${tmpfile}"

    job_id=$(echo "${submit_resp}" | jq -r '.job_id // empty')

    if [[ -z "${job_id}" ]]; then
      echo "ERROR: Failed to get job_id from submit response for run #${i}: ${submit_resp}" >&2
      job_ids[i]=""
      statuses[i]="submit_error"
      finished[i]=1
      file_inconsistent=1
      continue
    fi

    echo "  Run #${i}: queued job_id=${job_id}"

    job_ids[i]="${job_id}"
    statuses[i]="queued"
    finished[i]=0
  done

  echo "All submissions done, polling until all jobs complete..."

  start_ts=$(date +%s)
  while :; do
    all_done=1

    for (( i=1; i<=RUNS; i++ )); do
      if [[ "${finished[i]:-0}" -eq 1 ]]; then
        continue
      fi

      all_done=0
      job_id="${job_ids[i]}"

      if [[ -z "${job_id}" ]]; then
        finished[i]=1
        continue
      fi

      status_resp=$(curl -s "${API_BASE_URL}/jobs?job_id=${job_id}")
      status=$(echo "${status_resp}" | jq -r '.jobs[0].status // empty')

      if [[ "${status}" == "succeeded" || "${status}" == "failed" || "${status}" == "error" ]]; then
        statuses[i]="${status}"
        finished[i]=1

        if [[ "${status}" == "succeeded" ]]; then
          results_json[i]=$(curl -s "${API_BASE_URL}/jobs/${job_id}/result")
        else
          results_json[i]=""
        fi
      fi
    done

    if (( all_done == 1 )); then
      break
    fi

    now_ts=$(date +%s)
    if (( now_ts - start_ts > TIMEOUT )); then
      echo "ERROR: Timeout waiting for jobs for ${basename}" >&2
      for (( i=1; i<=RUNS; i++ )); do
        if [[ "${finished[i]:-0}" -ne 1 ]]; then
          statuses[i]="timeout"
          finished[i]=1
          results_json[i]=""
        fi
      done
      break
    fi

    sleep "${POLL_INTERVAL}"
  done

  # Now that all jobs are finished (or timed out), parse results and print table
  for (( i=1; i<=RUNS; i++ )); do
    job_id="${job_ids[i]:-}"
    status="${statuses[i]:-unknown}"

    if [[ "${status}" != "succeeded" ]]; then
      # Non-successful job is automatically inconsistent
      printf "%-4s %-36s %-15s %-11s %-18s %-10s %-10s %s*\n" \
        "${i}" "${job_id:-ERROR}" "-" "-" "${status}" "-" "-" "job not successful"
      file_inconsistent=1
      continue
    fi

    result_json="${results_json[i]}"

    language=$(echo "${result_json}"           | jq -r '.language // "none"')
    prob=$(echo "${result_json}"              | jq -r '.probability // 0')
    detection_method=$(echo "${result_json}"  | jq -r '.detection_method // "unknown"')
    gate_decision=$(echo "${result_json}"     | jq -r '.gate_decision // "none"')
    music_only=$(echo "${result_json}"        | jq -r '.music_only // false')
    transcript_snippet=$(echo "${result_json}"| jq -r '.transcript_snippet // ""')

    # Derive a simple "pipeline mode"
    pipeline_mode="BASE"
    if [[ "${gate_decision}" == accepted_mid_zone_* ]]; then
      pipeline_mode="MID_ZONE"
    elif [[ "${detection_method}" == *"-vad" ]]; then
      pipeline_mode="VAD"
    fi

    # Strip / shorten transcript for display
    short_tx="${transcript_snippet}"
    if (( ${#short_tx} > 60 )); then
      short_tx="${short_tx:0:57}..."
    fi

    if (( baseline_initialized == 0 )); then
      base_language="${language}"
      base_gate_decision="${gate_decision}"
      base_pipeline="${pipeline_mode}"
      base_music_only="${music_only}"
      base_detection_method="${detection_method}"
      baseline_initialized=1
      consistent_marker=" "
    else
      consistent_marker=" "
      if [[ "${language}" != "${base_language}" \
         || "${gate_decision}" != "${base_gate_decision}" \
         || "${pipeline_mode}" != "${base_pipeline}" \
         || "${music_only}" != "${base_music_only}" \
         || "${detection_method}" != "${base_detection_method}" ]]; then
        consistent_marker="*"
        file_inconsistent=1
      fi
    fi

    printf "%-4s %-36s %-15s %-11s %-18s %-10s %-10s %s%s\n" \
      "${i}" "${job_id}" "${language}" "${prob}" "${gate_decision}" \
      "${pipeline_mode}" "${music_only}" "${short_tx}" "${consistent_marker}"
  done

  echo

  # -------- Accumulate Markdown report for this file --------
  MD_REPORT+=$'### File: '"${basename}"$'\n\n'
  MD_REPORT+=$'| Run | JobId | Status | Language | Probability | DetectionMethod | GateDecision | Pipeline | MusicOnly | TranscriptSnippet | ConsistentWithBaseline |\n'
  MD_REPORT+=$'| --- | ----- | ------ | -------- | ----------- | --------------- | ------------ | -------- | --------- | ----------------- | ---------------------- |\n'

  baseline_initialized_md=0
  base_language_md=""
  base_gate_decision_md=""
  base_pipeline_md=""
  base_music_only_md=""
  base_detection_method_md=""

  for (( i=1; i<=RUNS; i++ )); do
    job_id="${job_ids[i]:-}"
    status="${statuses[i]:-unknown}"

    if [[ "${status}" != "succeeded" ]]; then
      # Non-successful job row in MD
      MD_REPORT+="| ${i} | ${job_id:-ERROR} | ${status} | - | - | - | - | - | - | job not successful | ❌ |"$'\n'
      continue
    fi

    result_json="${results_json[i]}"

    language=$(echo "${result_json}"           | jq -r '.language // "none"')
    prob=$(echo "${result_json}"              | jq -r '.probability // 0')
    detection_method=$(echo "${result_json}"  | jq -r '.detection_method // "unknown"')
    gate_decision=$(echo "${result_json}"     | jq -r '.gate_decision // "none"')
    music_only=$(echo "${result_json}"        | jq -r '.music_only // false')
    transcript_snippet=$(echo "${result_json}"| jq -r '.transcript_snippet // ""')

    pipeline_mode="BASE"
    if [[ "${gate_decision}" == accepted_mid_zone_* ]]; then
      pipeline_mode="MID_ZONE"
    elif [[ "${detection_method}" == *"-vad" ]]; then
      pipeline_mode="VAD"
    fi

    short_tx_md="${transcript_snippet}"
    if (( ${#short_tx_md} > 60 )); then
      short_tx_md="${short_tx_md:0:57}..."
    fi

    if (( baseline_initialized_md == 0 )); then
      base_language_md="${language}"
      base_gate_decision_md="${gate_decision}"
      base_pipeline_md="${pipeline_mode}"
      base_music_only_md="${music_only}"
      base_detection_method_md="${detection_method}"
      baseline_initialized_md=1
      consistent_flag="✅"
    else
      if [[ "${language}" != "${base_language_md}" \
         || "${gate_decision}" != "${base_gate_decision_md}" \
         || "${pipeline_mode}" != "${base_pipeline_md}" \
         || "${music_only}" != "${base_music_only_md}" \
         || "${detection_method}" != "${base_detection_method_md}" ]]; then
        consistent_flag="❌"
      else
        consistent_flag="✅"
      fi
    fi

    MD_REPORT+="| ${i} | ${job_id} | ${status} | ${language} | ${prob} | ${detection_method} | ${gate_decision} | ${pipeline_mode} | ${music_only} | ${short_tx_md} | ${consistent_flag} |"$'\n'
  done

  MD_REPORT+=$'\n'

  if (( file_inconsistent == 0 )); then
    echo "RESULT for ${basename}: ✅ CONSISTENT across ${RUNS} runs."
    SUMMARY_LINES+=( "CONSISTENT  ${basename}" )
  else
    echo "RESULT for ${basename}: ❌ INCONSISTENT across runs (see '*' rows above)."
    SUMMARY_LINES+=( "INCONSISTENT ${basename}" )
  fi

  echo
done

echo "================ OVERALL SUMMARY ================"
for line in "${SUMMARY_LINES[@]}"; do
  echo "${line}"
done

echo
echo "================ MARKDOWN REPORT (copy/paste below) ================"
echo
printf '%s\n' "$MD_REPORT"