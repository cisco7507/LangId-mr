#!/usr/bin/env bash
#
# test_langid_stability.sh
#
# For each audio file in a directory, submit it N times to the LangID API,
# collect /jobs/{id}/result, and report per-file consistency.
#
# Requires: bash, curl, jq
#

set -euo pipefail

API_BASE_URL="http://localhost:8080"
RUNS=10
DIR=""
EXT="wav"
POLL_INTERVAL=3       # seconds
TIMEOUT=600           # seconds

usage() {
  cat <<EOF
Usage:
  $(basename "$0") -d /path/to/dir [-n RUNS] [-u API_BASE_URL] [-e EXT]

Options:
  -d, --dir     Directory containing audio files (required)
  -n, --runs    Number of runs per file (default: ${RUNS})
  -u, --url     LangID API base URL (default: ${API_BASE_URL})
  -e, --ext     File extension to test (default: ${EXT}, e.g. wav)

Example:
  $(basename "$0") -d /Users/gsp/audio -n 20 -u http://localhost:8080
EOF
}

# ─────────────────────────────────────────────────────────────
# Parse arguments
# ─────────────────────────────────────────────────────────────
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
    -u|--url)
      API_BASE_URL="$2"
      shift 2
      ;;
    -e|--ext)
      EXT="$2"
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
  echo "ERROR: directory (-d / --dir) is required." >&2
  usage
  exit 1
fi

if [[ ! -d "${DIR}" ]]; then
  echo "ERROR: directory '${DIR}' does not exist." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required but not installed. Install jq and try again." >&2
  exit 1
fi

echo "LangID stability test"
echo "  Directory   : ${DIR}"
echo "  Extension   : .${EXT}"
echo "  Runs / file : ${RUNS}"
echo "  API base    : ${API_BASE_URL}"
echo

# Track summary across files
SUMMARY_LINES=()

# ─────────────────────────────────────────────────────────────
# Helper: submit a single file, poll until done, fetch /result
# Returns JSON on stdout.
# ─────────────────────────────────────────────────────────────
submit_and_get_result() {
  local file="$1"

  # 1) Submit job
  local submit_resp
  submit_resp=$(curl -s -X POST -F "file=@${file}" "${API_BASE_URL}/jobs")

  local job_id
  job_id=$(echo "${submit_resp}" | jq -r '.job_id // empty')

  if [[ -z "${job_id}" ]]; then
    echo "ERROR: Failed to get job_id from submit response: ${submit_resp}" >&2
    return 1
  fi

  # 2) Poll status
  local start_ts
  start_ts=$(date +%s)

  local status="queued"
  local status_resp

  while :; do
    sleep "${POLL_INTERVAL}"

    status_resp=$(curl -s "${API_BASE_URL}/jobs?job_id=${job_id}")
    status=$(echo "${status_resp}" | jq -r '.jobs[0].status // empty')

    if [[ "${status}" == "succeeded" || "${status}" == "failed" || "${status}" == "error" ]]; then
      break
    fi

    local now_ts
    now_ts=$(date +%s)
    if (( now_ts - start_ts > TIMEOUT )); then
      echo "ERROR: Timeout waiting for job ${job_id}" >&2
      return 1
    fi
  done

  if [[ "${status}" != "succeeded" ]]; then
    echo "ERROR: Job ${job_id} ended with status=${status}" >&2
    return 1
  fi

  # 3) Get final result
  local result_json
  result_json=$(curl -s "${API_BASE_URL}/jobs/${job_id}/result")
  echo "${result_json}"
}

# ─────────────────────────────────────────────────────────────
# Main per-file loop
# ─────────────────────────────────────────────────────────────
shopt -s nullglob
files=( "${DIR}"/*.${EXT} )

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No .${EXT} files found in ${DIR}" >&2
  exit 1
fi

for file in "${files[@]}"; do
  basename=$(basename "${file}")
  echo "============================================================"
  echo "FILE: ${basename}"
  echo "============================================================"

  printf "%-4s %-36s %-15s %-11s %-18s %-10s %-10s %s\n" \
    "Run" "JobId" "Language" "Prob" "GateDecision" "Pipeline" "MusicOnly" "TranscriptSnippet"
  printf "%-4s %-36s %-15s %-11s %-18s %-10s %-10s %s\n" \
    "----" "------------------------------------" "--------------" "-----------" "------------------" "----------" "----------" "-----------------"

  # Baseline fields from run #1
  base_language=""
  base_gate_decision=""
  base_pipeline=""
  base_music_only=""
  base_detection_method=""

  file_inconsistent=0

  for (( i=1; i<=RUNS; i++ )); do
    # Submit & fetch result JSON
    result_json=$(submit_and_get_result "${file}") || {
      printf "%-4s %-36s %-15s %-11s %-18s %-10s %-10s %s\n" \
        "${i}" "ERROR" "-" "-" "-" "-" "-" "submission/poll failed"
      file_inconsistent=1
      continue
    }

    job_id=$(echo "${result_json}"         | jq -r '.job_id // "-"')
    language=$(echo "${result_json}"       | jq -r '.language // "none"')
    prob=$(echo "${result_json}"           | jq -r '.probability // 0')
    detection_method=$(echo "${result_json}" | jq -r '.detection_method // "unknown"')
    gate_decision=$(echo "${result_json}"  | jq -r '.gate_decision // "none"')
    music_only=$(echo "${result_json}"     | jq -r '.music_only // false')
    transcript_snippet=$(echo "${result_json}" | jq -r '.transcript_snippet // ""')

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

    # Compare with baseline (run #1)
    if (( i == 1 )); then
      base_language="${language}"
      base_gate_decision="${gate_decision}"
      base_pipeline="${pipeline_mode}"
      base_music_only="${music_only}"
      base_detection_method="${detection_method}"
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

    # Print row (mark inconsistent runs with '*')
    printf "%-4s %-36s %-15s %-11s %-18s %-10s %-10s %s%s\n" \
      "${i}" "${job_id}" "${language}" "${prob}" "${gate_decision}" \
      "${pipeline_mode}" "${music_only}" "${short_tx}" "${consistent_marker}"
  done

  echo

  if (( file_inconsistent == 0 )); then
    echo "RESULT for ${basename}: ✅ CONSISTENT across ${RUNS} runs."
    SUMMARY_LINES+=( "CONSISTENT  ${basename}" )
  else
    echo "RESULT for ${basename}: ❌ INCONSISTENT vs run #1 (see '*' rows above)."
    SUMMARY_LINES+=( "INCONSISTENT ${basename}" )
  fi

  echo
done

# ─────────────────────────────────────────────────────────────
# Final summary ordered by file
# ─────────────────────────────────────────────────────────────
echo "======================= FINAL SUMMARY ======================="
# SUMMARY_LINES entries are: "INCONSISTENT filename" or "CONSISTENT filename"
# We want them ordered by filename; we'll sort on the second column.
printf "%s\n" "${SUMMARY_LINES[@]}" | sort -k2,2 | while read -r status fname; do
  if [[ "${status}" == "INCONSISTENT" ]]; then
    echo "❌ ${fname}  (inconsistencies across runs)"
  else
    echo "✅ ${fname}  (consistent across runs)"
  fi
done
echo "============================================================="