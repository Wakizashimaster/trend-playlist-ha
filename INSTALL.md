# Installation and operation

> **Before you start:** Trend Playlist is an independent community integration for an existing TIDAL playlist. It can make real changes to your playlist **only after an explicit Publish action**. Back up your playlist, confirm your account/session and keep the app's API private to your LAN.

## 1. Install the Home Assistant OS app

In **Settings → Apps → App Store → ⋮ → Repositories**, add:

`https://github.com/Wakizashimaster/trend-playlist-ha`

Install **Trend Playlist Preview**. The legacy app name is retained for upgrade compatibility; it now supports reviewed publishing. Set a unique `api_token` of at least 24 characters. Do not forward port **8099** or expose it publicly.

The app expects a working local `tidal_session.json`, `auto_refresh_state.json` and any existing `blocklist.csv` / input files in its own persistent add-on configuration directory. Home Assistant Core's `/config` is **not** the same directory. Keep offline backups. Never commit session files or credentials to Git.

## 2. Install the HACS integration

Add this repository as a **custom Integration** repository in HACS, download **Trend Playlist**, and restart Home Assistant. If updating an existing installation, use **Redownload** in HACS and restart Home Assistant after updating the app.

Go to **Settings → Devices & services → Add integration → Trend Playlist**. Enter the app's LAN URL, e.g. `http://YOUR_PI_IP:8099`, and the same API token. Home Assistant Core contacts the app locally; do not use a Home Assistant Cloud URL for this connection.

## 3. Review and publish

1. Press **Trend Playlist run preview** (or wait for Monday 08:00 UK). Preview is read-only with respect to TIDAL.
2. Inspect **Trend Playlist proposal** and the per-track review selects. Exclude unwanted additions, retain proposed removals or mark an addition for Zeitgeist.
3. **Block from future proposals** writes a permanent song block to the app's local `blocklist.csv`. Changing the select back does not automatically unblock it; use the existing blocklist tooling for removal. A fresh preview will apply saved blocks.
4. Press **Approve reviewed proposal** or **Approve Everything** (the latter requires no individual decisions).
5. Press **Trend Playlist check publish safety**. Confirm `approval_recorded: true` and `publish_preflight_passed: true`.
6. Only when ready to change TIDAL, press **Trend Playlist Publish approved playlist**. Monitor the preview/status sensor for `publish_status: verified`, then inspect the live playlist and artwork in TIDAL.

The live playlist must still match its saved baseline immediately before publishing. Publishing creates a local recovery snapshot and verifies the final track IDs. An error or partial update is **not** automatically rolled back: do not retry blindly. Preserve the recovery files and investigate.

## 4. What the status means

- `approval_recorded: false` — current selection is not approved.
- `publish_preflight_passed: false` — run the safety check after approval.
- `publish_status: verified` — the last publish passed automated track verification.
- `ok: false` after a successful publish — the old preview was intentionally invalidated; it is **not** a publish failure.
- `zeitgeist_pending` — recorded intentions only, not a Zeitgeist playlist update.

## Current limitations

- One protected TIDAL playlist; playlist ID is currently configured in the app code.
- No Gmail summary or publish notifications yet.
- Zeitgeist promotion is recorded but not executed.
- No missed-Monday-run catch-up; an always-on Home Assistant host is recommended.
- No automatic recovery from a partially applied TIDAL update.
- The app API is authenticated but **not HTTPS** on its LAN port; do not expose it beyond your trusted network.

## 0.3.0 candidate: respecting manual TIDAL edits (opt-in)

**Do not install this candidate from the development branch or enable it until
the release is approved.** The add-on and HACS integration version must match.

Once released and installed, open the Trend Playlist app's **Configuration**
tab and set `respect_manual_tidal_removals: true`; save and restart the app.
The default is `false`, retaining the previous strict-baseline behaviour.

A manual or Monday preview then compares the saved verified track sequence
with repeated reads of the protected live TIDAL playlist. A removed TIDAL track
ID becomes an automatic reversible exclusion; re-adding the exact ID clears
that exclusion on the next preview. A different recording or alternate TIDAL
ID is not treated as the same track. Explicit Home Assistant song blocks are
permanent and separate.

The feature never edits TIDAL during preview. Every actual playlist update
still requires the usual review, approval, preflight and explicit publish.
Manual additions to the live playlist become part of the verified baseline.
If too many changes are detected, reads disagree, a publish journal is
unresolved, or local reconciliation is interrupted, the preview stops and
requires investigation. **Do not delete recovery markers to force a retry.**

For the first test after upgrading, leave the option disabled until you have
a current backup and a successful normal preview. Enable it and run a manual
preview without changing the live playlist; check the review before trying a
single controlled manual removal. Do not publish during this test.
