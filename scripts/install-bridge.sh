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

umask 077
cat > "$DATA_DIR/bridge.env" <<EOF
EUFY_EMAIL=$EUFY_EMAIL
EUFY_PASSWORD=$EUFY_PASSWORD
EUFY_COUNTRY=$EUFY_COUNTRY
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
echo "Next: HACS install https://github.com/mirimalulkasif/ha-eufy → Add integration → 127.0.0.1:3000"
