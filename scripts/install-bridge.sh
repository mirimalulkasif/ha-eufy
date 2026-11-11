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

if [ -z "${EUFY_EMAIL:-}" ]; then
  printf "Eufy email: "
  read -r EUFY_EMAIL
fi
if [ -z "${EUFY_PASSWORD:-}" ]; then
  printf "Eufy password: "
  # -s hides input when the terminal supports it
  stty -echo 2>/dev/null || true
  read -r EUFY_PASSWORD
  stty echo 2>/dev/null || true
  echo
fi
if [ -z "${EUFY_COUNTRY:-}" ]; then
  printf "Eufy country code [IL]: "
  read -r EUFY_COUNTRY
  EUFY_COUNTRY="${EUFY_COUNTRY:-IL}"
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
