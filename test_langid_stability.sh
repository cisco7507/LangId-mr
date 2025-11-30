#!/usr/bin/env bash
#
# test_langid_stability.sh
#
# Repeatedly submit the same audio file to a LangID service and
# check for inconsistencies in the final result fields.
#
# Dependencies: curl, jq
#
# Usage:
#   ./test_langid_stability.sh -f /path/to/audio.wav \
#       -n 20 \
#       -u http://localhost:8080 \
#       -p 5 \
#       -t 600
#

set -euo pipefail

# ---------- Defaults ----------
FILE_PATH=""
RUNS=10
API_BASE="http://localhost:8080"
POLL_INTERVAL=5
TIMEOUT=600

# ---------- Functions ----------

usage() {
  cat <<EOF
Usage: $0 -f FILE [-n RUNS] [-u API_BASE] [-p POLL_INTERVAL] [-t TIMEOUT]

  -f FILE         Path to audio file (required)
  -n RUNS         Number of runs (default: $RUNS)
  -u API_BASE     LangID API base URL (default: $API_BASE)
  -p POLL         Poll interval in seconds (default: $POLL_INTERVAL)
  -t TIMEOUT      Timeout in seconds per job (default: $TIMEOUT)

Requires: curl, jq
EOF
}

error() {
  echo "ERROR: $*" >&2
}

# ---------- Parse args ----------

while getopts ":f:n:u:p:t:h" opt; do
  case "$opt" in
    f) FILE_PATH="$OPTARG" ;;
    n) RUNS="$OPTARG" ;;
    u) API_BASE="$OPTARG" ;;
    p) POLL_INTERVAL="$OPTARG" ;;
    t) TIMEOUT="$OPTARG" ;;
    h) usage; exit 0 ;;
    \?) error "Invalid option: -$OPTARG"; usage; exit 1 ;;
    :) error "Option -$OPTARG requires an argument"; usage; exit 1 ;;
  esac
done

if [[ -z "$FILE_PATH" ]]; then
  error "File path is required (-f)"
  usage
  exit 1
fi

if [[ ! -f "$FILE_PATH" ]]; then
  error "File not found: $FILE_PATH"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  error "curl is required"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  error "jq is required (e.g. brew install jq)"
  exit 1
fi

# Normalize API_BASE (no trailing slash)
API_BASE="${API_BASE%/}"

# ---------- Arrays to store results ----------

declare -a JOB_IDS
declare -a LANGS
declare -a PROBS
declare -a GATE_DECS
declare -a MODES
declare -a MUSIC_ONLYS
declare -a DET_METHODS
declare -a TRANSCRIPTS
declare -a MID_ZONES
declare -a ERRORS

# ---------- Helpers ----------

submit_job() {
  local file="$1"
  local url="$API_BASE/jobs"

  # -s silent, -S show errors, -f fail on HTTP errors
  curl -sS -f -F "file=@${file}" "$url"
}

poll_job_status() {
  local job_id="$1"
  local poll_interval="$2"
  local timeout="$3"

  local status_url="$API_BASE/jobs?job_id=${job_id}"
  local start_ts
  start_ts=$(date +%s)

  while true; do
    local now_ts
    now_ts=$(date +%s)
    local elapsed=$(( now_ts - start_ts ))

    if (( elapsed > timeout )); then
      echo "TIMEOUT"
      return 0
    fi

    local status_json
    status_json=$(curl -sS "$status_url" || true)

    # If empty or malformed, sleep & retry
    if [[ -z "$status_json" ]]; then
      sleep "$poll_interval"
      continue
    fi

    # Assume /jobs?job_id= filters to this job; pick first
    local status
    status=$(echo "$status_json" | jq -r '.jobs[0].status // "unknown"' 2>/dev/null || echo "unknown")

    case "$status" in
      succeeded|failed|error)
        echo "$status"
        return 0
        ;;
      *)
        sleep "$poll_interval"
        ;;
    esac
  done
}

fetch_result() {
  local job_id="$1"
  local url="$API_BASE/jobs/${job_id}/result"
  curl -sS "$url"
}

# Build a compact summary JSON from the result JSON
summarize_result() {
  local json="$1"
  echo "$json" | jq -r '
    {
      job_id: .job_id,
      original_filename: (.original_filename // null),
      language: (
        (try .language catch null)
        // (try .raw.language catch null)
      ),
      probability: (
        (try .probability catch null)
        // (try .raw.probability catch null)
      ),
      gate_decision: (
        (try .gate_decision catch null)
        // (try .raw.gate_decision catch null)
        // (try .raw.raw.lang_gate.gate_decision catch null)
      ),
      music_only: (
        (try .music_only catch false)
        // (try .raw.music_only catch false)
        // (try .raw.raw.music_only catch false)
      ),
      detection_method: (
        (try .detection_method catch null)
        // (try .raw.detection_method catch null)
      ),
      transcript_snippet: (
        (try .transcript_snippet catch "")
      ),
      gate_mid_zone: (
        (try .gate_meta.mid_zone catch false)
        or (try .raw.gate_meta.mid_zone catch false)
        or (try .raw.raw.lang_gate.gate_meta.mid_zone catch false)
      ),
      pipeline_mode: (
        if (
          (try .gate_meta.vad_used catch false)
          or (try .raw.gate_meta.vad_used catch false)
          or (try .raw.raw.lang_gate.gate_meta.vad_used catch false)
          or (try .raw.raw.lang_gate.use_vad catch false)
        ) then "VAD"
        elif (
          (try .gate_meta.mid_zone catch false)
          or (try .raw.gate_meta.mid_zone catch false)
          or (try .raw.raw.lang_gate.gate_meta.mid_zone catch false)
        ) then "MID_ZONE"
        else "NORMAL"
        end
      )
    }
  '
}

# ---------- Main loop ----------

echo "Running $RUNS runs against $API_BASE with file: $FILE_PATH"
echo

for (( i=0; i<RUNS; i++ )); do
  run=$((i+1))
  # Defaults for this run
  JOB_IDS[i]=""
  LANGS[i]=""
  PROBS[i]=""
  GATE_DECS[i]=""
  MODES[i]=""
  MUSIC_ONLYS[i]=""
  DET_METHODS[i]=""
  TRANSCRIPTS[i]=""
  MID_ZONES[i]=""
  ERRORS[i]=""

  # 1) Submit job
  submit_resp=""
  if ! submit_resp=$(submit_job "$FILE_PATH" 2>/dev/null); then
    ERRORS[i]="submit_failed"
    continue
  fi

  job_id=$(echo "$submit_resp" | jq -r '.job_id // empty' 2>/dev/null || echo "")
  if [[ -z "$job_id" ]]; then
    ERRORS[i]="no_job_id"
    continue
  fi
  JOB_IDS[i]="$job_id"

  # 2) Poll
  status=$(poll_job_status "$job_id" "$POLL_INTERVAL" "$TIMEOUT")
  if [[ "$status" == "TIMEOUT" ]]; then
    ERRORS[i]="timeout"
    continue
  elif [[ "$status" != "succeeded" ]]; then
    ERRORS[i]="status_${status}"
    continue
  fi

  # 3) Fetch result
  result_json=""
  if ! result_json=$(fetch_result "$job_id" 2>/dev/null); then
    ERRORS[i]="result_fetch_failed"
    continue
  fi

  # 4) Summarize
  summary_json=$(summarize_result "$result_json")

  lang=$(echo "$summary_json" | jq -r '.language // ""')
  prob=$(echo "$summary_json" | jq -r '.probability // ""')
  gate_dec=$(echo "$summary_json" | jq -r '.gate_decision // ""')
  music_only=$(echo "$summary_json" | jq -r '.music_only // false')
  det_method=$(echo "$summary_json" | jq -r '.detection_method // ""')
  transcript=$(echo "$summary_json" | jq -r '.transcript_snippet // ""')
  mid_zone=$(echo "$summary_json" | jq -r '.gate_mid_zone // false')
  mode=$(echo "$summary_json" | jq -r '.pipeline_mode // "NORMAL"')

  LANGS[i]="$lang"
  PROBS[i]="$prob"
  GATE_DECS[i]="$gate_dec"
  MUSIC_ONLYS[i]="$music_only"
  DET_METHODS[i]="$det_method"
  TRANSCRIPTS[i]="$transcript"
  MID_ZONES[i]="$mid_zone"
  MODES[i]="$mode"
done

# ---------- Print per-run table ----------

printf "\n==================== PER-RUN RESULTS ====================\n\n"
printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
  "Run" "JobId" "Lang" "Prob" "GateDecision" "Mode" "Music" "DetectMethod" "MidZone" "Transcript"
printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
  "----" "--------------------------------------" "--------" "-----------" "--------------------" "----------" "--------" "---------------" "--------" "----------"

for (( i=0; i<RUNS; i++ )); do
  run=$((i+1))
  job_id="${JOB_IDS[i]}"
  err="${ERRORS[i]}"

  if [[ -n "$err" ]]; then
    printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
      "$run" "$job_id" "" "" "" "" "" "" "" "ERROR: $err"
    continue
  fi

  lang="${LANGS[i]}"
  prob="${PROBS[i]}"
  gate_dec="${GATE_DECS[i]}"
  mode="${MODES[i]}"
  music="${MUSIC_ONLYS[i]}"
  det="${DET_METHODS[i]}"
  mid="${MID_ZONES[i]}"
  transcript="${TRANSCRIPTS[i]}"

  printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
    "$run" "$job_id" "$lang" "$prob" "$gate_dec" "$mode" "$music" "$det" "$mid" "$transcript"
done

# ---------- Compare vs run #1 ----------

printf "\n======================= SUMMARY =========================\n"

# Baseline is run 1 (index 0), if no error
if [[ -n "${ERRORS[0]}" || -z "${JOB_IDS[0]}" ]]; then
  echo "Run #1 has an error or no job_id; cannot compute consistency against run #1."
  exit 0
fi

base_lang="${LANGS[0]}"
base_gate="${GATE_DECS[0]}"
base_mode="${MODES[0]}"
base_music="${MUSIC_ONLYS[0]}"
base_det="${DET_METHODS[0]}"

# Track which fields ever differ
fields_diff=()

check_field_diff() {
  local name="$1"
  local base_val="$2"
  local val="$3"
  if [[ "$base_val" != "$val" ]]; then
    fields_diff+=( "$name" )
  fi
}

# We will also collect inconsistent runs
inconsistent_rows=()

for (( i=1; i<RUNS; i++ )); do
  err="${ERRORS[i]}"
  job_id="${JOB_IDS[i]}"

  if [[ -n "$err" || -z "$job_id" ]]; then
    continue
  fi

  lang="${LANGS[i]}"
  gate="${GATE_DECS[i]}"
  mode="${MODES[i]}"
  music="${MUSIC_ONLYS[i]}"
  det="${DET_METHODS[i]}"

  if [[ "$lang" != "$base_lang" || "$gate" != "$base_gate" || "$mode" != "$base_mode" || "$music" != "$base_music" || "$det" != "$base_det" ]]; then
    # record per-field diff
    check_field_diff "Language" "$base_lang" "$lang"
    check_field_diff "GateDecision" "$base_gate" "$gate"
    check_field_diff "PipelineMode" "$base_mode" "$mode"
    check_field_diff "MusicOnly" "$base_music" "$music"
    check_field_diff "DetectionMethod" "$base_det" "$det"
    inconsistent_rows+=( "$i" )
  fi
done

if (( ${#inconsistent_rows[@]} == 0 )); then
  echo "All successful runs are consistent with run #1 on: Language, GateDecision, PipelineMode, MusicOnly, DetectionMethod."
  exit 0
fi

# Deduplicate fields_diff
unique_fields=()
for f in "${fields_diff[@]}"; do
  skip=false
  for uf in "${unique_fields[@]}"; do
    if [[ "$f" == "$uf" ]]; then
      skip=true
      break
    fi
  done
  if ! $skip; then
    unique_fields+=( "$f" )
  fi
done

echo "Found inconsistencies vs run #1 for fields:"
for f in "${unique_fields[@]}"; do
  echo "  $f"
done
echo
echo "Inconsistent runs:"

# Print table of inconsistent runs
printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
  "Run" "JobId" "Lang" "Prob" "GateDecision" "Mode" "Music" "DetectMethod" "MidZone" "Transcript"
printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
  "----" "--------------------------------------" "--------" "-----------" "--------------------" "----------" "--------" "---------------" "--------" "----------"

for idx in "${inconsistent_rows[@]}"; do
  run=$((idx+1))
  job_id="${JOB_IDS[idx]}"
  lang="${LANGS[idx]}"
  prob="${PROBS[idx]}"
  gate_dec="${GATE_DECS[idx]}"
  mode="${MODES[idx]}"
  music="${MUSIC_ONLYS[idx]}"
  det="${DET_METHODS[idx]}"
  mid="${MID_ZONES[idx]}"
  transcript="${TRANSCRIPTS[idx]}"

  printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
    "$run" "$job_id" "$lang" "$prob" "$gate_dec" "$mode" "$music" "$det" "$mid" "$transcript"
done