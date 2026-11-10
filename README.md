# Eufy Cameras (Home Assistant)

Home Assistant custom integration for **Eufy** doorbell and indoor cameras.

It talks to a running [eufy-security-ws](https://github.com/bropat/eufy-security-ws) server (Home Assistant add-on or Docker) and exposes only:

| Device | Entities |
|--------|----------|
| **Doorbell** | Camera, motion, ring, enabled switch, battery (when reported), kind |
| **Indoor camera** | Camera, motion, enabled switch, kind |

Other Eufy product types are ignored. This project is not affiliated with Anker or Eufy.

## Requirements

1. A working **eufy-security-ws** instance logged into your Eufy account  
   (for example the [eufy-security-ws add-on](https://github.com/fuatakgun/eufy_security)).
2. Home Assistant **2024.1** or newer.

## Install (HACS)

1. HACS → Integrations → ⋮ → Custom repositories  
2. Add this repository URL, category **Integration**  
3. Install **Eufy Cameras**  
4. Restart Home Assistant  
5. Settings → Devices & services → Add integration → **Eufy Cameras**  
6. Enter the host/port of eufy-security-ws (default `127.0.0.1:3000`)

### Manual install

Copy `custom_components/eufy_cameras` into your Home Assistant `custom_components/` folder, restart, then add the integration.

## Notes

- Live video streaming is not wired in this lean client; use the eufy-security-ws / go2rtc path for RTSP when you need a live feed.
- Motion and ring binary sensors pulse from websocket push events.
- The **Enabled** switch maps to the device `enabled` property (arm / disarm style control).
- If eufy-security-ws authenticates but lists **0 devices**, your account has likely moved to Eufy’s Mega (v6) cloud. Prefer a Mega-based stack (for example [ha-eufy-sdk-bridge](https://github.com/mega-yfue/ha-eufy-sdk-bridge)) instead of the legacy ws add-on.

## License

MIT
