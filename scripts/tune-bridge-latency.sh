#!/bin/sh
# Recreate eufy-bridge with prewarm + longer stream budget (keeps existing login data).
#   curl -fsSL https://raw.githubusercontent.com/mirimalulkasif/ha-eufy/main/scripts/tune-bridge-latency.sh | sh
set -e

DATA_DIR="${EUFY_BRIDGE_DATA:-/mnt/data/eufy-bridge-data}"
IMAGE="ghcr.io/mega-yfue/ha-eufy-sdk-bridge:latest"
NAME="eufy-bridge"
ENV_FILE="$DATA_DIR/bridge.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — run install-bridge.sh first."
  exit 1
fi

# Merge / refresh latency-related knobs without wiping credentials.
tmp="$(mktemp)"
grep -vE '^(BRIDGE_PREWARM|STREAM_BATTERY_BUDGET_MS|STREAM_IDLE_MS|BRIDGE_HOST|BRIDGE_PORT)=' "$ENV_FILE" > "$tmp" || true
cat >> "$tmp" <<EOF
BRIDGE_HOST=0.0.0.0
BRIDGE_PORT=3000
BRIDGE_PREWARM=1
STREAM_BATTERY_BUDGET_MS=180000
STREAM_IDLE_MS=600000
EOF
mv "$tmp" "$ENV_FILE"
chmod 600 "$ENV_FILE"

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker pull "$IMAGE"
docker run -d \
  --name "$NAME" \
  --restart unless-stopped \
  --network host \
  --env-file "$ENV_FILE" \
  -v "$DATA_DIR:/app/data" \
  "$IMAGE"

echo "Recreated $NAME with BRIDGE_PREWARM=1 and longer stream budget."
curl -s "http://127.0.0.1:3000/healthz" || true
echo
