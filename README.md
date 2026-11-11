# Eufy Cameras (Home Assistant)

Home Assistant integration for **Eufy** doorbell (T82xx) and indoor (T84xx) cameras on the **Mega (v6) cloud**.

The Mega Node SDK cannot run inside a Python custom component. You need:

1. **Bridge** — Docker container (`ha-eufy-sdk-bridge`) that logs into Eufy
2. **Eufy Cameras** — this HACS integration (entities, snapshots, RTSP, motion/ring)

If **Settings → Add-ons** is missing, you are on **Home Assistant Container / Core** — use the Docker steps below (most VM installs).

This project is not affiliated with Anker or Eufy.

## Install (HA Container / Core — no Add-ons)

### 1. Bridge on the same VM

You need a **normal Linux shell** (`$` or `#`), not the Home Assistant CLI (`ha>`).

If you see `unknown command "sudo" for "ha"`, you are inside `ha>` — type `login` (HA OS console) or open an SSH session that drops you into bash, or run the bridge on another machine on your LAN instead.

Then:

```bash
mkdir -p /opt/eufy-bridge-data
docker run -d --name eufy-bridge --restart unless-stopped --network host \
  -e EUFY_EMAIL='you@example.com' \
  -e EUFY_PASSWORD='your-password' \
  -e EUFY_COUNTRY='IL' \
  -v /opt/eufy-bridge-data:/app/data \
  ghcr.io/mega-yfue/ha-eufy-sdk-bridge:latest
```

Use the same **country** as the Eufy app. Check:

```bash
curl -s http://127.0.0.1:3000/healthz
docker logs -f eufy-bridge
```

You want `"auth":{"state":"ok"}`. If it asks for 2FA, the integration setup dialog can submit the code after step 2.

### 2. Integration (HACS GUI)

1. HACS → Integrations → ⋮ → Custom repositories  
   URL: `https://github.com/mirimalulkasif/ha-eufy` · Category: **Integration**
2. Download **Eufy Cameras** → restart Home Assistant
3. **Settings → Devices & services → Add integration → Eufy Cameras**
4. Host / port:
   - If HA uses **host networking**: `127.0.0.1` / `3000`
   - If HA is on the default Docker bridge: use the **VM’s LAN IP** / `3000` (not `127.0.0.1`)
5. Complete **2FA / captcha** in the dialog if prompted

### Compose alternative

```yaml
services:
  eufy-bridge:
    image: ghcr.io/mega-yfue/ha-eufy-sdk-bridge:latest
    container_name: eufy-bridge
    restart: unless-stopped
    network_mode: host
    environment:
      EUFY_EMAIL: "you@example.com"
      EUFY_PASSWORD: "your-password"
      EUFY_COUNTRY: "IL"
      BRIDGE_HOST: "0.0.0.0"
      BRIDGE_PORT: "3000"
    volumes:
      - /opt/eufy-bridge-data:/app/data
```

## Install (HA OS / Supervised — has Add-ons)

1. **Settings → Add-ons → Add-on store → ⋮ → Repositories** → add `https://github.com/mirimalulkasif/ha-eufy`
2. Install **Eufy Cameras Bridge** → set email/password/country → Start
3. Install the HACS integration (same URL) → Add integration → host = HA IP, port `3000`

## Entities

| Device | Models | Entities |
|--------|--------|----------|
| Doorbell | T82xx (e.g. T8224) | Camera (**stills** from push/event thumbnails — no live WebRTC), motion, person, ring, switches, battery, model |
| Indoor | T84xx (e.g. T8400) | Camera (live RTSP via go2rtc), motion, person, switches, battery, model, power |

Doorbell live video on Mega often opens a black window (same limitation as the Homebridge plugin). The integration shows the latest motion/ring still instead. Trigger the doorbell or walk in front of it once if the tile is empty, then refresh the card. For indoor live video, if RTSP is black, set the integration **host** to the VM’s LAN IP (not `127.0.0.1`) so HA Core can reach go2rtc.

## Requirements

- Home Assistant **2024.1+**
- Bridge image: **amd64** or **aarch64** only
- Prefer a dedicated eufy account shared into your home (admin) so the phone app does not kick the bridge session

## License

MIT
