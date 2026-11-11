# Eufy Cameras (Home Assistant)

Home Assistant custom integration for **Eufy** doorbell and indoor cameras on the **Mega (v6) cloud**.

It talks to a running [ha-eufy-sdk-bridge](https://github.com/mega-yfue/ha-eufy-sdk-bridge) and exposes only:

| Device | Models | Entities |
|--------|--------|----------|
| **Doorbell** | T82xx (e.g. T8224) | Camera (snapshot + RTSP), motion, person, ring, enabled / status LED / light switches, battery, model, kind |
| **Indoor camera** | T84xx (e.g. T8400) | Camera (snapshot + RTSP), motion, person, enabled / status LED / light switches, battery, model, kind, power |

Other Eufy product types are ignored. This project is not affiliated with Anker or Eufy.

## Requirements

1. A working **ha-eufy-sdk-bridge** instance logged into your Eufy Mega account  
   (Docker / compose from the bridge repo — complete 2FA/captcha there until `auth.state` is `ok`).
2. Home Assistant **2024.1** or newer.
3. The bridge’s go2rtc RTSP port reachable from Home Assistant if you want live streams (default `8554`).

> Legacy [eufy-security-ws](https://github.com/bropat/eufy-security-ws) is **not** supported anymore. Mega accounts return 0 devices on that stack.

## Install (HACS)

1. HACS → Integrations → ⋮ → Custom repositories  
2. Add this repository URL, category **Integration**  
3. Install **Eufy Cameras**  
4. Restart Home Assistant  
5. Settings → Devices & services → Add integration → **Eufy Cameras**  
6. Enter the host/port of the Mega bridge (default `127.0.0.1:3000` — WebSocket path is `/ws`)

### Manual install

Copy `custom_components/eufy_cameras` into your Home Assistant `custom_components/` folder, restart, then add the integration.

## What works

- **Discovery** of Mega doorbell / indoor cameras (`devices.list`, filtered by model prefix).
- **Snapshots** via `GET /snapshot/<sn>?mode=stored` (falls back to the bridge default).
- **Live stream** source from `stream.start` → go2rtc RTSP URL.
- **Motion / person / doorbell ring** binary sensors from bridge push events.
- **Property switches** for enabled/privacy, status LED, and light when reported.
- **Battery / model / power** diagnostic sensors.

## Notes

- Point the integration at the **bridge HTTP/WS port** (usually `3000`), not the go2rtc RTSP port.
- If connect fails with an auth-state message, finish 2FA/captcha on the bridge first.
- Doorbells that cannot open WebRTC live video on 32-bit hosts still get stored snapshots and motion/ring events through the bridge.

## License

MIT
