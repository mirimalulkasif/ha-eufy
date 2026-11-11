# Eufy Cameras Bridge (add-on)

Runs the Mega [`ha-eufy-sdk-bridge`](https://github.com/mega-yfue/ha-eufy-sdk-bridge) inside Home Assistant so the **Eufy Cameras** HACS integration does not need a separate Docker host.

## Install (GUI)

1. **Settings → Add-ons → Add-on store → ⋮ → Repositories**
2. Add `https://github.com/mirimalulkasif/ha-eufy`
3. Install **Eufy Cameras Bridge**
4. **Configuration**: set eufy `email`, `password`, `country` (same region as the Eufy app)
5. **Start** the add-on
6. Install the **Eufy Cameras** integration via HACS (same repo), restart HA, then **Add integration**
7. If asked for host/port use your HA host IP (or the discovered values) and port `3000` — **not** `localhost` from inside the HA container

On first login Eufy may require **2FA / captcha**. Complete it in the integration config flow (or check the add-on log).

## Notes

- Architectures: **amd64** and **aarch64** only.
- Prefer a dedicated eufy account shared with admin rights so the phone app does not kick the bridge session.
- Published ports: `3000` (WS/HTTP), `8554` (RTSP). Change them in the add-on **Network** panel if needed.
