#!/bin/sh
# Run on Home Assistant OS (# root shell) or any Docker host:
#   curl -fsSL https://raw.githubusercontent.com/mirimalulkasif/ha-eufy/main/scripts/install-bridge.sh | sh
set -e

DATA_DIR="${EUFY_BRIDGE_DATA:-/mnt/data/eufy-bridge-data}"
IMAGE="ghcr.io/mega-yfue/ha-eufy-sdk-bridge:latest"
NAME="eufy-bridge"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Are you in the HA OS root shell (#)?"
  exit 1
fi

mkdir -p "$DATA_DIR"

# Always read from the real console. `curl … | sh` makes stdin the script pipe,
# so plain `read` would not wait for keyboard input and prompts look jammed together.
ask() {
  # $1 = prompt, $2 = variable name, $3 = optional default
  prompt="$1"
  var="$2"
  default="${3:-}"
  if [ -n "$default" ]; then
    printf "%s [%s]: " "$prompt" "$default" > /dev/tty
  else
    printf "%s: " "$prompt" > /dev/tty
  fi
  if [ "$var" = "EUFY_PASSWORD" ]; then
    stty -echo < /dev/tty 2>/dev/null || true
    IFS= read -r value < /dev/tty
    stty echo < /dev/tty 2>/dev/null || true
    printf "\n" > /dev/tty
  else
    IFS= read -r value < /dev/tty
  fi
  if [ -z "$value" ] && [ -n "$default" ]; then
    value="$default"
  fi
  eval "$var=\"\$value\""
}

if [ -z "${EUFY_EMAIL:-}" ]; then
  ask "Eufy email" EUFY_EMAIL
fi
if [ -z "${EUFY_PASSWORD:-}" ]; then
  ask "Eufy password" EUFY_PASSWORD
fi
if [ -z "${EUFY_COUNTRY:-}" ]; then
  ask "Eufy country code" EUFY_COUNTRY "IL"
fi

# Keep existing password/email if re-running over an env file that already exists
# and the user pasted empty — ask() already required values above.

umask 077
cat > "$DATA_DIR/bridge.env" <<EOF
EUFY_EMAIL=$EUFY_EMAIL
EUFY_PASSWORD=$EUFY_PASSWORD
EUFY_COUNTRY=$EUFY_COUNTRY
BRIDGE_HOST=0.0.0.0
BRIDGE_PORT=3000
# Faster first view after ring/person (opens P2P early). Uses a bit more battery.
BRIDGE_PREWARM=1
# Keep a watched battery/doorbell stream up longer (ms) before Mega sleeps it.
STREAM_BATTERY_BUDGET_MS=180000
STREAM_IDLE_MS=600000
EOF

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker pull "$IMAGE"
docker run -d \
  --name "$NAME" \
  --restart unless-stopped \
  --network host \
  --env-file "$DATA_DIR/bridge.env" \
  -v "$DATA_DIR:/app/data" \
  "$IMAGE"

echo
echo "Started $NAME. Checking health..."
sleep 3
curl -s "http://127.0.0.1:3000/healthz" || true
echo
echo "Logs: docker logs -f $NAME"
echo "In HA, set Eufy Cameras host to the VM LAN IP, port 3000."
echo "For lower latency than HA's built-in player, open:"
echo "  http://<VM-LAN-IP>:1984/stream.html?src=<CAMERA_SERIAL>"
