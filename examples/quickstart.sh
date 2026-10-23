#!/usr/bin/env bash
set -euo pipefail
: "${HEDRA_API_KEY:?Set HEDRA_API_KEY first}"
RESPONSE=$(curl --fail-with-body --silent --show-error --max-time 130 \
  https://api.hedra.com/v3/chat/completions \
  -H "Authorization: Bearer $HEDRA_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "glm-5.3",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "List the visible objects and their spatial relationships. Describe only what the image shows."},
      {"type": "image_url", "image_url": {"url": "https://imagedelivery.net/yn_JX_LzJpQI9TTynGwR_Q/www-redesign/training/hero-robot-lab-20261019/public"}}
    ]
  }],
  "reasoning_effort": "low",
  "max_tokens": 4096
}
JSON
)
printf '%s' "$RESPONSE" | jq -er '
  .choices[0] | if .finish_reason == "stop" and (.message.content | length) > 0
  then .message.content else error("No complete answer; inspect finish_reason") end
'
