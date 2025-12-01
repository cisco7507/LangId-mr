#!/usr/bin/env bash
set -uo pipefail

# Defaults
API_BASE="http://localhost:8080"
RUNS=10
POLL_INTERVAL=5
TIMEOUT=600
FILE_PATH=""

usage() {
  cat <<EOF
Usage: $0 -f FILE [-n RUNS] [-u API_BASE] [-p POLL_INTERVAL] [-t TIMEOUT]

  -f FILE         Audio file to test (required)
  -n RUNS         Number of runs (default: 10)
  -u API_BASE     LangId API base URL (default: http://localhost:8080)
  -p SECONDS      Poll interval in seconds (default: 5)
  -t SECONDS      Timeout per job in seconds (default: 600)
EOF
}

while getopts "f:n:u:p:t:" opt; do
  case "$opt" in
    f) FILE_PATH="$OPTARG" ;;
    n) RUNS="$OPTARG" ;;
    u) API_BASE="$OPTARG" ;;
    p) POLL_INTERVAL="$OPTARG" ;;
    t) TIMEOUT="$OPTARG" ;;
    *) usage; exit 1 ;;
  esac
done

if [[ -z "$FILE_PATH" ]]; then
  echo "ERROR: -f FILE is required" >&2
  usage
  exit 1
fi

if [[ ! -f "$FILE_PATH" ]]; then
  echo "ERROR: File not found: $FILE_PATH" >&2
  exit 1
fi

API_BASE="${API_BASE%/}"

submit_job() {
  local file="$1"
  curl -sS -f -F "file=@${file}" "${API_BASE}/jobs"
}

poll_job_status() {
  local job_id="$1"
  local interval="$2"
  local timeout="$3"

  local url="${API_BASE}/jobs?job_id=${job_id}"
  local start now
  start=$(date +%s)

  while true; do
    now=$(date +%s)
    if (( now - start > timeout )); then
      echo ""
      return 1
    fi

    local resp
    if ! resp=$(curl -sS -f "$url" 2>/dev/null); then
      sleep "$interval"
      continue
    fi

    local status
    status=$(echo "$resp" | jq -r '.jobs[0].status // empty' 2>/dev/null || echo "")

    if [[ -z "$status" ]]; then
      sleep "$interval"
      continue
    fi

    if [[ "$status" == "succeeded" || "$status" == "failed" || "$status" == "error" ]]; then
      echo "$resp"
      return 0
    fi

    sleep "$interval"
  done
}

sanitize_snippet() {
  local txt="$1"
  # one line, escape pipes, trim, limit length
  txt=${txt//$'\n'/ }
  txt=${txt//'|'/'\|'}
  txt=${txt//\`/}
  txt=${txt//$'\r'/}
  txt=$(echo "$txt" | sed 's/[[:space:]]\+/ /g')
  if (( ${#txt} > 80 )); then
    txt="${txt:0:77}..."
  fi
  echo "$txt"
}

echo "Running ${RUNS} runs against ${API_BASE} with file: ${FILE_PATH}"

declare -a JOB_IDS ERRORS STATUSES LANGS PROBS DETMETHODS GATEDECIS MODES MUSIC MIDZ SNIPS

echo "Submitting jobs..."

tmp_submit_dir=$(mktemp -d "/tmp/langid_submit.XXXXXX")

# ---------- Phase 1: fire all submits in parallel ----------
for (( i=0; i<RUNS; i++ )); do
  (
    submit_resp=""
    if ! submit_resp=$(submit_job "$FILE_PATH" 2>&1); then
      printf "ERROR submit_failed: %s\n" "$submit_resp" >"$tmp_submit_dir/$i"
      exit 0
    fi

    job_id=$(printf '%s\n' "$submit_resp" | jq -r '.job_id // empty' 2>/dev/null || printf '')
    if [[ -z "$job_id" ]]; then
      printf "ERROR no_job_id\n" >"$tmp_submit_dir/$i"
    else
      printf "%s\n" "$job_id" >"$tmp_submit_dir/$i"
    fi
  ) &
done

wait || true
echo "All submit workers finished, collecting results..."

# Collect submit results
ok=0
fail=0
for (( i=0; i<RUNS; i++ )); do
  if [[ -f "$tmp_submit_dir/$i" ]]; then
    content=$(<"$tmp_submit_dir/$i")
    if [[ "$content" == ERROR* ]]; then
      ERRORS[i]="${content#ERROR }"
      JOB_IDS[i]=""
      ((fail++))
    else
      JOB_IDS[i]="$content"
      ERRORS[i]=""
      ((ok++))
    fi
  else
    ERRORS[i]="submit_unknown"
    JOB_IDS[i]=""
    ((fail++))
  fi
done

rm -rf "$tmp_submit_dir"

echo "Submissions complete: $ok ok, $fail failed."
echo "All jobs submitted. Polling for completion..."
echo

# ---------- Phase 2: poll each job & fetch result ----------
for (( i=0; i<RUNS; i++ )); do
  job_id="${JOB_IDS[i]}"
  if [[ -z "$job_id" ]]; then
    STATUSES[i]="submit_error"
    LANGS[i]=""
    PROBS[i]=""
    DETMETHODS[i]=""
    GATEDECIS[i]=""
    MODES[i]=""
    MUSIC[i]=""
    MIDZ[i]=""
    SNIPS[i]=""
    continue
  fi

  status_json=""
  if ! status_json=$(poll_job_status "$job_id" "$POLL_INTERVAL" "$TIMEOUT" 2>/dev/null); then
    STATUSES[i]="timeout"
    ERRORS[i]="timeout_waiting"
    continue
  fi

  status=$(echo "$status_json" | jq -r '.jobs[0].status // "unknown"' 2>/dev/null || echo "unknown")
  STATUSES[i]="$status"

  if [[ "$status" != "succeeded" ]]; then
    ERRORS[i]="status_${status}"
    continue
  fi

  result_json=""
  if ! result_json=$(curl -sS -f "${API_BASE}/jobs/${job_id}/result" 2>/dev/null); then
    ERRORS[i]="result_fetch_failed"
    continue
  fi

  LANGS[i]=$(echo "$result_json" | jq -r '.language // "unknown"' 2>/dev/null || echo "unknown")
  PROBS[i]=$(echo "$result_json" | jq -r '.probability // 0' 2>/dev/null || echo "0")
  DETMETHODS[i]=$(echo "$result_json" | jq -r '.detection_method // "unknown"' 2>/dev/null || echo "unknown")
  GATEDECIS[i]=$(echo "$result_json" | jq -r '.gate_decision // "unknown"' 2>/dev/null || echo "unknown")

  music_flag=$(echo "$result_json" | jq -r '.music_only // false' 2>/dev/null || echo "false")
  MUSIC[i]="$music_flag"

  mid_zone=$(echo "$result_json" | jq -r '.gate_meta.mid_zone // false' 2>/dev/null || echo "false")
  MIDZ[i]="$mid_zone"

  mode="BASE"
  use_vad=$(echo "$result_json" | jq -r '.raw.raw.lang_gate.use_vad // .raw.lang_gate.use_vad // false' 2>/dev/null || echo "false")
  if [[ "$use_vad" == "true" || "${DETMETHODS[i]}" == *"vad"* ]]; then
    mode="VAD"
  elif [[ "$mid_zone" == "true" || "${GATEDECIS[i]}" == *"mid_zone"* ]]; then
    mode="MID_ZONE"
  fi
  MODES[i]="$mode"

  snippet=$(echo "$result_json" | jq -r '.transcript_snippet // .raw.text // ""' 2>/dev/null || echo "")
  SNIPS[i]=$(sanitize_snippet "$snippet")
done

# ---------- Phase 3: tabular report ----------
printf "\n==================== PER-RUN RESULTS ====================\n\n"
printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
  "Run" "JobId" "Lang" "Prob" "GateDecision" "Mode" "Music" "DetectMethod" "MidZone" "Transcript"
printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
  "----" "--------------------------------------" "--------" "-----------" "--------------------" "----------" "--------" "---------------" "--------" "----------"

for (( i=0; i<RUNS; i++ )); do
  run=$((i+1))
  job_id="${JOB_IDS[i]}"
  lang="${LANGS[i]:-}"
  prob="${PROBS[i]:-}"
  gate="${GATEDECIS[i]:-}"
  mode="${MODES[i]:-}"
  music="${MUSIC[i]:-}"
  det="${DETMETHODS[i]:-}"
  mid="${MIDZ[i]:-}"
  snip="${SNIPS[i]:-}"

  printf "%-4s %-38s %-8s %-11s %-20s %-10s %-8s %-15s %-8s %s\n" \
    "$run" "${job_id:0:38}" "$lang" "$prob" "$gate" "$mode" "$music" "$det" "$mid" "$snip"
done

# ---------- Phase 4: consistency vs run #1 ----------
baseline_idx=-1
for (( i=0; i<RUNS; i++ )); do
  if [[ -z "${ERRORS[i]:-}" && "${STATUSES[i]:-}" == "succeeded" ]]; then
    baseline_idx=$i
    break
  fi
done

printf "\n======================= SUMMARY =========================\n"

if (( baseline_idx == -1 )); then
  echo "No successful baseline run found; cannot compute consistency."
  exit 0
fi

base_lang="${LANGS[baseline_idx]}"
base_prob="${PROBS[baseline_idx]}"
base_gate="${GATEDECIS[baseline_idx]}"
base_mode="${MODES[baseline_idx]}"
base_music="${MUSIC[baseline_idx]}"
base_det="${DETMETHODS[baseline_idx]}"

inconsistent_fields=()

for (( i=0; i<RUNS; i++ )); do
  if [[ "${STATUSES[i]}" != "succeeded" ]]; then
    continue
  fi
  if [[ "${LANGS[i]}" != "$base_lang" ]]; then
    inconsistent_fields+=("Language")
  fi
  if [[ "${GATEDECIS[i]}" != "$base_gate" ]]; then
    inconsistent_fields+=("GateDecision")
  fi
  if [[ "${MODES[i]}" != "$base_mode" ]]; then
    inconsistent_fields+=("PipelineMode")
  fi
  if [[ "${MUSIC[i]}" != "$base_music" ]]; then
    inconsistent_fields+=("MusicOnly")
  fi
  if [[ "${DETMETHODS[i]}" != "$base_det" ]]; then
    inconsistent_fields+=("DetectionMethod")
  fi
done

if (( ${#inconsistent_fields[@]} == 0 )); then
  echo "All successful runs are consistent with baseline run #$((baseline_idx+1))."
  exit 0
fi

# dedupe fields
mapfile -t inconsistent_fields < <(printf "%s\n" "${inconsistent_fields[@]}" | sort -u)

echo "Found inconsistencies vs run #$((baseline_idx+1)) for fields:"
for f in "${inconsistent_fields[@]}"; do
  echo "  $f"
done