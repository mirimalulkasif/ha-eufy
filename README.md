# Eufy Cameras (Home Assistant)

Home Assistant integration for **Eufy** doorbell (T82xx) and indoor (T84xx) cameras on the **Mega (v6) cloud**.

The Mega Node SDK cannot run inside a Python custom component, so this repository ships **both**:

1. **Eufy Cameras Bridge** — Supervisor add-on (wraps [`ha-eufy-sdk-bridge`](https://github.com/mega-yfue/ha-eufy-sdk-bridge))
2. **Eufy Cameras** — HACS integration (entities, snapshots, RTSP, motion/ring)

You install both from the **same GitHub URL** in the HA UI. No separate Docker SSH step on HA OS / Supervised.

This project is not affiliated with Anker or Eufy.

## Install on HA OS / Supervised (GUI)

### 1. Bridge add-on

1. **Settings → Add-ons → Add-on store → ⋮ → Repositories**
2. Add: `https://github.com/mirimalulkasif/ha-eufy`
3. Install **Eufy Cameras Bridge**
4. **Configuration**: eufy email, password, country (same as the Eufy app)
5. **Start** the add-on (wait until it is running)

### 2. Integration (HACS)

1. HACS → Integrations → ⋮ → Custom repositories → same URL, category **Integration**
2. Download **Eufy Cameras** → restart Home Assistant
3. **Settings → Devices & services → Add integration → Eufy Cameras**
4. Confirm discovery, or enter your **HA host IP** and port **3000** (not `127.0.0.1` from inside the HA container)
5. If Eufy asks for **2FA / captcha**, enter it in the setup dialog

### Entities

| Device | Models | Entities |
|--------|--------|----------|
| Doorbell | T82xx (e.g. T8224) | Camera, motion, person, ring, switches, battery, model |
| Indoor | T84xx (e.g. T8400) | Camera, motion, person, switches, battery, model, power |

## HA Container / Core (no Supervisor)

If your VM runs Home Assistant **Container** (no Add-on store), run the bridge container on that VM (host network), then add the HACS integration pointed at the VM’s LAN IP / `3000`. See the [bridge docs](https://github.com/mega-yfue/ha-eufy-sdk-bridge/blob/main/docs/docker-compose.md).

## Requirements

- Home Assistant **2024.1+**
- Bridge add-on / image: **amd64** or **aarch64** only
- Prefer a dedicated eufy account shared into your home (admin) so the phone app does not kick the bridge session

## License

MIT
