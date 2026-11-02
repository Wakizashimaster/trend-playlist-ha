# Install and test (preview-only)

## 1. Add the app repository

In Home Assistant: **Settings → Apps → App Store → ⋮ → Repositories**, add:

`https://github.com/Wakizashimaster/trend-playlist-ha`

Install **Trend Playlist Preview**. Before starting it, set **api_token** to a random secret of at least 24 characters. Leave the network port 8099 accessible only on your trusted local network; do **not** forward it through your router or expose it publicly.

**Do not start the app until the TIDAL session and baseline have been migrated.** The app's data is mounted at `/config` inside the app container. Home Assistant OS exposes the add-on configuration directory as a separate location from the Home Assistant Core `/config`; don't confuse them. Securely copy the existing verified `tidal_session.json`, `auto_refresh_state.json` and any required `inputs/`, `seeds.csv`, `blocklist.csv` into the app's configuration directory. Preserve a Windows backup. No passwords or personal files should be committed to GitHub.

## 2. Install the custom integration

Using HACS: add `https://github.com/Wakizashimaster/trend-playlist-ha` as a **custom repository** of type **Integration**, install Trend Playlist, and restart Home Assistant. If HACS does not recognize the repository, manually copy `custom_components/trend_playlist` into Home Assistant Core's `/config/custom_components/trend_playlist` and restart.

Then open **Settings → Devices & services → Add integration → Trend Playlist**. Enter `http://YOUR_PI_LAN_IP:8099` and the same API token. Replace YOUR_PI_LAN_IP with your Pi's LAN IP. Do not use your Home Assistant Cloud URL as the worker URL: HA Core talks to the worker locally.

The integration provides a preview status sensor and a **Run preview** button. You can use them from your authenticated Home Assistant dashboard through Home Assistant Cloud.

## 3. Verify safely

First confirm the app starts and the integration shows a status. Then press **Run preview** and inspect the app log and status sensor. The worker runs `auto_refresh.py --preview` and **does not publish to TIDAL**. The app will refuse a preview when its trusted baseline or TIDAL session is missing.

This is an **untested initial release**. Do not disable the existing Windows task until the Pi is verified. Do not rely on the Monday schedule yet.

## Known limitations

- No Gmail reporting, mobile approval, in-place publishing, or success verification yet.
- The Monday 08:00 Europe/London scheduler has no missed-run catch-up.
- Preview status currently exposes the last 5000 characters of process output as sensor attributes. Avoid sharing diagnostic output publicly.
- This release is intended for installation and connectivity testing, not production automation.
