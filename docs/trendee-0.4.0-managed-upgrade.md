# Trendee 0.4.0 managed-upgrade checklist (draft; do not deploy yet)

The 0.4.0 implementation is in a **development branch** and is **not a release**.
Do not install a development-branch snapshot over a working Home Assistant instance.

## Prerequisites

- Preserve a full Home Assistant backup including the Trend Playlist app's persistent data.
- Preserve the current working app and HACS integration versions and note the rollback route.
- Disable automatic app updates during the supervised upgrade.
- Never commit or export `api_token`, `tidal_session.json`, recovery files or other credentials.
- Do not change the protected playlist in TIDAL while verifying the upgrade.

## Home Assistant state and recorder review

The playlist sensor's **state** is a numeric track count, not a JSON string,
so it does not breach Home Assistant's 255-character *state* limit. The
`tracks` list is instead stored in **attributes**. Those attributes are
broadcast to connected Home Assistant frontends and may be recorded every
time the sensor changes. The current implementation allows up to 500 tracks,
which could create unnecessarily large state events and database rows.

**Implemented on the development branch:** the sensor now exposes only
readiness, playlist identity and count. The full cached track list is returned
only through the Home Assistant-authenticated `trendee/playlist` WebSocket
command, without exposing worker credentials to the browser.

**Release decision: not yet approved.** Offline syntax and contract tests
are necessary but not sufficient: test the dashboard with a real 50-track
playlist, a failed TIDAL read, Home Assistant recorder, and mobile navigation.
Do not rely on users manually configuring recorder exclusions as the
default solution.

## Release gates

1. Confirm all automated checks pass for the final commit.
2. Validate the read-only `GET /playlist` response against a real TIDAL session
   without using any POST or publish operation. Confirm the playlist ID, name,
   ordering, artwork, track count and safe handling of expired authentication.
3. Validate the HACS sensor and responsive Trendee panel against the upgraded app.
   Check browser state size and Home Assistant recorder implications of a 50-track
   sensor attribute payload; if necessary, replace it with an authenticated
   Home Assistant backend endpoint before release.
4. Confirm a safe upgrade from 0.3.0 with preserved add-on data, and verify
   rollback using a disposable/test installation or a documented backup restore.
5. Synchronize the locally tested sidebar registration safety change into the
   GitHub release branch.
6. Review all 0.4.0 release notes and migration instructions.
7. Merge approved changes, tag a release and verify the app repository and HACS
   both expose version 0.4.0 through their normal update mechanisms.

## Supervised upgrade sequence (only after release gates pass)

1. Update the Trend Playlist app through **Settings → Apps** and confirm its
   version and persistent TIDAL session remain intact.
2. Update the Trend Playlist integration through HACS.
3. **Only with explicit user permission**, restart Home Assistant if required.
4. Open Trendee and confirm the existing status cards still work.
5. Confirm the read-only playlist shows the expected tracks in the expected
   order on desktop and mobile; test search, artwork and TIDAL links.
6. Confirm there is no publish action or automatic TIDAL mutation in this view.

If the playlist API fails, stop and inspect the app logs; do not publish or
reset TIDAL credentials as a workaround. If the integration fails, use the
saved backup and documented rollback process.
