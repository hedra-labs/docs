#!/usr/bin/env bash
set -euo pipefail
: "${HEDRA_API_KEY:?Set HEDRA_API_KEY first}"
API="https://api.hedra.com/v3"
ACK=$(curl --fail-with-body --silent --show-error --max-time 30 \
  -X POST "$API/models/gpt-image-2" \
  -H "Authorization: Key $HEDRA_API_KEY" -H "Content-Type: application/json" \
  -d '{"input":{"prompt":"An industrial inspection camera on a workbench","aspect_ratio":"1:1","resolution":"1K","quality":"medium","output_format":"png"}}')
JOB_ID=$(printf '%s' "$ACK" | jq -er '.job_id')
echo "Job: $JOB_ID"
DEADLINE=$((SECONDS + 600))
while true; do
  if (( SECONDS >= DEADLINE )); then
    echo "Still running: $JOB_ID. Resume polling; do not resubmit." >&2
    exit 1
  fi
  STATUS=$(curl --fail-with-body --silent --show-error --max-time 30 \
    "$API/jobs/$JOB_ID/status" -H "Authorization: Key $HEDRA_API_KEY" | jq -er '.status')
  case "$STATUS" in
    COMPLETED) break ;;
    FAILED) echo "Job failed: $JOB_ID. Inspect GET /v3/jobs/$JOB_ID." >&2; exit 1 ;;
    IN_QUEUE|IN_PROGRESS) sleep 5 ;;
    *) echo "Unexpected status: $STATUS" >&2; exit 1 ;;
  esac
done
RESULT=$(curl --fail-with-body --silent --show-error --max-time 30 \
  "$API/jobs/$JOB_ID" -H "Authorization: Key $HEDRA_API_KEY")
URL=$(printf '%s' "$RESULT" | jq -er '.outputs[0] | select(.status == "COMPLETED") | .url // empty')
# Download without forwarding the API credential to the storage host.
curl --fail --location --silent --show-error --max-time 120 "$URL" -o output.png
echo "Saved output.png"
