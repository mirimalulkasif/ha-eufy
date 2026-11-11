#!/bin/sh
# Translate HA add-on options → bridge env, start daemon, register discovery.
set -e

OPTS=/data/options.json
SUPERVISOR_API="${SUPERVISOR:-http://supervisor}"

export EUFY_EMAIL="$(jq -r '.email // ""' "$OPTS")"
export EUFY_PASSWORD="$(jq -r '.password // ""' "$OPTS")"
export EUFY_COUNTRY="$(jq -r '.country // "IL"' "$OPTS")"
export EUFY_SESSION="/data/.eufy-session.json"
export BRIDGE_HOST="0.0.0.0"
export BRIDGE_PORT="${BRIDGE_PORT:-3000}"

export EUFY_POLL_MS="$(jq -r '.poll_ms // 600000' "$OPTS")"
export STREAM_IDLE_MS="$(jq -r '.stream_idle_ms // 300000' "$OPTS")"
export RTSP_IDLE_OFF_MS="$(jq -r '.rtsp_idle_off_ms // 300000' "$OPTS")"

budget_ms="$(jq -r '.stream_battery_budget_ms // empty' "$OPTS")"
[ -n "$budget_ms" ] && export STREAM_BATTERY_BUDGET_MS="$budget_ms"

case "$(jq -r '.snapshot_live // empty' "$OPTS")" in
  on) export SNAPSHOT_LIVE=1 ;;
  off) export SNAPSHOT_LIVE=0 ;;
  auto) export SNAPSHOT_LIVE=auto ;;
esac

[ "$(jq -r '.prewarm // false' "$OPTS")" = "true" ] && export BRIDGE_PREWARM=1
[ "$(jq -r '.event_log // true' "$OPTS")" = "false" ] && export BRIDGE_EVENT_LOG=0
[ "$(jq -r '.debug // false' "$OPTS")" = "true" ] && export BRIDGE_DEBUG=1
[ "$(jq -r '.go2rtc_enable // true' "$OPTS")" = "false" ] && export GO2RTC_ENABLE=0

if [ -z "$EUFY_EMAIL" ] || [ -z "$EUFY_PASSWORD" ]; then
  echo "[addon] Set email and password in the add-on Configuration tab, then restart."
  exit 1
fi

register_discovery() {
  if [ -z "${SUPERVISOR_TOKEN:-}" ]; then
    echo "[addon] SUPERVISOR_TOKEN unavailable; skipping discovery"
    return
  fi

  addon_info="$(curl -fsS -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" "${SUPERVISOR_API}/addons/self/info")" || {
    echo "[addon] could not read add-on info; skipping discovery"
    return
  }
  network_info="$(curl -fsS -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" "${SUPERVISOR_API}/network/info")" || network_info='{"data":{}}'

  addon_host="$(printf '%s' "$addon_info" | jq -r '.data.hostname // "eufy-cameras-bridge"')"
  gateway="$(printf '%s' "$network_info" | jq -r '.data.docker.gateway // empty')"

  port_value() {
    key="$1"
    internal="$2"
    mapped="$(printf '%s' "$addon_info" | jq -r --arg key "$key" '.data.network[$key] // empty')"
    if [ -n "$mapped" ] && [ -n "$gateway" ]; then
      printf '%s\n' "$mapped"
    else
      printf '%s\n' "$internal"
    fi
  }

  if [ -n "$gateway" ]; then
    bridge_host="$gateway"
  else
    bridge_host="$addon_host"
  fi
  bridge_port="$(port_value "3000/tcp" 3000)"
  rtsp_port="$(port_value "8554/tcp" 8554)"

  discovery_payload="$(
    jq -cn \
      --arg host "$bridge_host" \
      --argjson port "$bridge_port" \
      --argjson rtsp_port "$rtsp_port" \
      '{
        service: "eufy_sdk",
        config: {
          host: $host,
          port: $port,
          go2rtc_rtsp_port: $rtsp_port
        }
      }'
  )"

  if curl -fsS -X POST -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" -H "Content-Type: application/json" \
    -d "$discovery_payload" "${SUPERVISOR_API}/discovery" >/dev/null; then
    echo "[addon] registered discovery ${bridge_host}:${bridge_port}"
  else
    echo "[addon] could not register discovery"
  fi
}

wait_for_bridge() {
  health_url="http://127.0.0.1:${BRIDGE_PORT}/healthz"
  attempt=1
  echo "[addon] waiting for ${health_url}"
  until curl -fsS "$health_url" >/dev/null; do
    if ! kill -0 "$bridge_pid" 2>/dev/null; then
      echo "[addon] bridge exited before becoming healthy"
      return 1
    fi
    if [ "$attempt" -ge 45 ]; then
      echo "[addon] bridge not healthy within 45s; skipping discovery"
      return 1
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
}

if [ ! -x /usr/local/bin/eufy-sdk-bridge ]; then
  echo "[addon] /usr/local/bin/eufy-sdk-bridge missing — wrong base image?"
  exit 1
fi

/usr/local/bin/eufy-sdk-bridge &
bridge_pid="$!"

stop_bridge() {
  kill -TERM "$bridge_pid" 2>/dev/null || true
  wait "$bridge_pid"
}
trap stop_bridge TERM INT

(
  wait_for_bridge && register_discovery
) &

wait "$bridge_pid"
