#!/bin/sh
# Request a fresh Eufy 2FA (or submit one) against a running bridge.
#
# Usage (HA OS # shell):
#   # ask Eufy to email/SMS a NEW code:
#   curl -fsSL https://raw.githubusercontent.com/mirimalulkasif/ha-eufy/main/scripts/submit-2fa.sh | sh
#
#   # submit the newest code (example 123456):
#   curl -fsSL https://raw.githubusercontent.com/mirimalulkasif/ha-eufy/main/scripts/submit-2fa.sh | sh -s -- 123456
set -e

CODE="${1:-}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found"
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx eufy-bridge; then
  echo "Container eufy-bridge is not running. Start it first (install-bridge.sh)."
  exit 1
fi

# ESM client inside the bridge image (depends on `ws`).
docker exec -i eufy-bridge node --input-type=module - "$CODE" <<'EOF'
import WebSocket from "ws";

const code = process.argv[2] || "";
const url = "ws://127.0.0.1:3000/ws";

function rpc(ws, cmd, extra = {}) {
  return new Promise((resolve, reject) => {
    const id = Math.floor(Math.random() * 1e9);
    const onMsg = (raw) => {
      let msg;
      try {
        msg = JSON.parse(raw.toString());
      } catch {
        return;
      }
      if (msg.id !== id) return;
      ws.off("message", onMsg);
      if (msg.ok) resolve(msg);
      else reject(new Error(msg.error || "command failed"));
    };
    ws.on("message", onMsg);
    ws.send(JSON.stringify({ id, cmd, ...extra }));
  });
}

const ws = new WebSocket(url);
ws.on("error", (e) => {
  console.error(e.message);
  process.exit(1);
});
ws.on("open", async () => {
  try {
    const status = await rpc(ws, "auth.status");
    let auth = status.auth || {};
    console.log(
      "auth state:",
      auth.state,
      auth.method ? `method=${auth.method}` : ""
    );
    if (auth.state === "ok") {
      console.log("Already logged in.");
      process.exit(0);
    }
    if (!code) {
      const r = await rpc(ws, "auth.retrigger");
      auth = r.auth || {};
      console.log("Requested a NEW challenge →", auth.state, auth.method || "");
      console.log("Check email/SMS for the newest Eufy code (ignore older ones), then run:");
      console.log(
        "  curl -fsSL https://raw.githubusercontent.com/mirimalulkasif/ha-eufy/main/scripts/submit-2fa.sh | sh -s -- YOURCODE"
      );
      process.exit(0);
    }
    const r = await rpc(ws, "auth.submit", { code });
    auth = r.auth || {};
    console.log("Submit result →", auth.state);
    if (auth.state !== "ok") {
      console.log("Not ok yet. Run without a code to request another, use only the newest email.");
      process.exit(2);
    }
    console.log("Login OK. In HA: Add integration → Eufy Cameras → 127.0.0.1 port 3000");
    process.exit(0);
  } catch (e) {
    console.error(e.message || e);
    process.exit(1);
  } finally {
    try {
      ws.close();
    } catch {
      /* ignore */
    }
  }
});
EOF
