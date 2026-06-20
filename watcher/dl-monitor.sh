#!/usr/bin/env bash
set -euo pipefail
CONFIG="$HOME/.config/download-watcher/config"
source "$CONFIG"
STATE_FILE="/dev/shm/dl-watcher-state.json"
MILESTONE_FILE="/dev/shm/dl-watcher-milestones"
LAST_GOOD=$(cat "$STATE_FILE" 2>/dev/null || echo '{"bytes_total":0,"last_epoch":0,"files_ok":0}')
SVC_STATUS=$(systemctl --user is-active "glm52-download" 2>/dev/null || echo "inactive")

if [ "$SVC_STATUS" != "active" ]; then
  JOURNAL=$(journalctl --user -u "$SERVICE" --no-pager -n 20 2>/dev/null || echo "")
  echo "{\"status\":\"failed\",\"message\":\"Service $SERVICE is $SVC_STATUS\",\"journal\":$(echo "$JOURNAL" | jq -Rs .)}"
  exit 0
fi

FILE_COUNT=$(find "$DIR" -maxdepth 1 -type f ! -name '.*' 2>/dev/null | wc -l)
TOTAL_BYTES=$(du -sb "$DIR" 2>/dev/null | cut -f1)
CURRENT_SIZE_HUMAN=$(du -sh "$DIR" 2>/dev/null | cut -f1)

LAST_BYTES=$(echo "$LAST_GOOD" | jq -r '.bytes_total // 0')
NOW_EPOCH=$(date +%s)
LAST_EPOCH=$(echo "$LAST_GOOD" | jq -r '.last_epoch // 0')
RATE_MB=0
if [ "$LAST_EPOCH" -gt 0 ] && [ "$TOTAL_BYTES" -gt "$LAST_BYTES" ]; then
  ELAPSED=$(( NOW_EPOCH - LAST_EPOCH ))
  DELTA=$(( TOTAL_BYTES - LAST_BYTES ))
  [ "$ELAPSED" -gt 0 ] && RATE_MB=$(( DELTA / ELAPSED / 1048576 ))
fi

printf '{"files_ok":%d,"bytes_total":%d,"last_epoch":%d}\n' \
  "$FILE_COUNT" "$TOTAL_BYTES" "$NOW_EPOCH" > "$STATE_FILE"

LAST_FILES=$(echo "$LAST_GOOD" | jq -r '.files_ok // 0')
PCT=0
[ "$TOTAL_FILES" -gt 0 ] && PCT=$(( FILE_COUNT * 100 / TOTAL_FILES ))

REMAINING_HUMAN="calculating..."
if [ "$RATE_MB" -gt 0 ] && [ "$FILE_COUNT" -gt 0 ] && [ "$FILE_COUNT" -lt "$TOTAL_FILES" ]; then
  AVG_FILE_BYTES=$(( TOTAL_BYTES / FILE_COUNT ))
  REMAINING_BYTES=$(( (TOTAL_FILES - FILE_COUNT) * AVG_FILE_BYTES ))
  REMAINING_SEC=$(( REMAINING_BYTES / (RATE_MB * 1048576) ))
  REMAINING_HUMAN=$(printf '%dh %dm' $(( REMAINING_SEC / 3600 )) $(( (REMAINING_SEC % 3600) / 60 )))
fi

REPORT=""
for m in 10 20 30 40 50 60 70 80 90 100; do
  if [ "$PCT" -ge "$m" ] && [ "$PCT" -lt $(( m + 10 )) ] || [ "$PCT" -eq 100 ]; then
    if [ ! -f "$MILESTONE_FILE" ] || ! grep -q "pct_$m" "$MILESTONE_FILE" 2>/dev/null; then
      echo "pct_$m" >> "$MILESTONE_FILE"
      [ -z "$REPORT" ] && REPORT="📊 **${PCT}%** complete (${FILE_COUNT}/${TOTAL_FILES} files, ${CURRENT_SIZE_HUMAN}) | ~${REMAINING_HUMAN} remaining | ${RATE_MB} MB/s"
    fi
  fi
done
[ ! -f "$MILESTONE_FILE" ] && touch "$MILESTONE_FILE"

if [ "$FILE_COUNT" -ne "$LAST_FILES" ] && [ -z "$REPORT" ]; then
  REPORT="📦 ${FILE_COUNT}/${TOTAL_FILES} files landed (~${CURRENT_SIZE_HUMAN}) | ${RATE_MB} MB/s | ~${REMAINING_HUMAN} left"
fi

jq -n \
  --arg status "running" \
  --arg files "$FILE_COUNT" \
  --arg total "$CURRENT_SIZE_HUMAN" \
  --arg rate "${RATE_MB}" \
  --arg remaining "$REMAINING_HUMAN" \
  --arg pct "$PCT" \
  --arg report "$REPORT" \
  --arg max "$TOTAL_FILES" \
  '{status:$status,files:$files,total:$total,rate:$rate,remaining:$remaining,pct:$pct,report:$report,max_files:$max}'
