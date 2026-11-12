# Changelog

All notable user-facing changes are recorded here. Releases follow semantic versioning where practical. The Home Assistant app and HACS integration should be updated together.

## 0.6.0 — Full sidebar review and publishing controls (development; not released)

- Individual addition choices: Keep, Exclude this week, Promote to Zeitgeist, Block from future proposals.
- Individual removal choices: Remove as proposed or Retain in playlist.
- Review decisions use existing Home Assistant select entities; permanent block requires an additional confirmation.
- Show final revised additions/removals, replacement count, and approval status before committing.
- Approve reviewed proposal, Approve Everything, and read-only publish safety preflight.
- Publish is disabled until approval and preflight succeed, and requires a separate typed final confirmation bound to the exact proposal ID and plan hash.
- Browser never receives the worker token. Existing Home Assistant service entities and server-side proposal checks remain authoritative.
- **Development only**: no live TIDAL changes, Home Assistant reloads, merges or releases as part of this branch.

## 0.5.0 — Trendee preview and review (development; not released)

### Added
- Run the existing dry-run preview from the Trendee sidebar using the Home Assistant button entity and authenticated service call.
- Display proposed additions, removals, unchanged count, proposed track count, approval status and preflight status directly in the sidebar.
- Disable preview initiation while a preview is already running; show progress and safe error feedback.
- Escape proposed track metadata before rendering; no worker credentials exposed to the browser.
- Automated preview/review safety contract tests.

### Safety
- No sidebar Approve or Publish controls. Running a preview never mutates the protected TIDAL playlist.
- The 0.5.0 code is on a development branch only; do not install until reviewed, merged and explicitly approved.
- Update the add-on and HACS integration together when approved.

## 0.4.1 — Playlist import-path hotfix

- Fix add-on worker imports for the read-only playlist endpoint.
- Verify live TIDAL playlist count, artwork and links in Home Assistant.

## 0.4.0 — Trendee playlist view (development, not released)

### Added
- Read-only Trendee sidebar panel with existing worker/preview/publish status cards.
- Searchable live TIDAL playlist view with track order, artist, album, artwork and TIDAL links.
- Bearer-authenticated, read-only worker `GET /playlist` API, with protected playlist identity checks and a ten-minute Home Assistant refresh.
- Home Assistant-authenticated `trendee/playlist` WebSocket command for the cached track list. Browser clients never receive the worker bearer token.
- Summary-only playlist sensor to avoid storing track lists in Home Assistant recorder attributes.
- Offline contract, WebSocket behavior, and playlist snapshot tests.

### Upgrade and safety
- **Not released or approved for live deployment.** The add-on and HACS integration must be upgraded together through their managed update mechanisms after release checks.
- No new publishing action is provided by the Trendee panel; playlist viewing does not mutate TIDAL.
- Home Assistant runtime, mobile, failed-authentication, and upgrade/rollback validation remain release gates.
- Keep a Home Assistant backup including add-on data; do not use development branch files as an update.

## 0.3.0 — release candidate (not deployed)

### Added
- Opt-in **Respect manual TIDAL removals** app setting, disabled by default.
- Monday/manual previews can reconcile a small, verified set of manual changes to the protected live playlist without changing TIDAL.
- Tracks manually removed in TIDAL are excluded by TIDAL ID from future candidate matching; re-adding the same track in TIDAL clears its reversible exclusion on the next preview.
- Ranked 80-to-50 candidate refill, including the phone replacement pool; insufficient safe matches fail closed.
- Local reconciliation journal, backup, double-read verification, final live check and publisher recovery guard.
- Offline GitHub Actions tests for reconciliation, candidate exclusion and refill.

### Safety and limitations
- **Monday remains preview-only.** Publishing still requires explicit review, approval, preflight and publish action.
- More than ten additions/removals in a poll require manual investigation.
- The exclusion is tied to the exact TIDAL track ID; different recordings/catalogue IDs of the same song are not automatically treated as equivalent.
- Interrupted local reconciliation blocks subsequent previews/publishing pending supervised recovery.
- This version has not been tested against the user's live Home Assistant/TIDAL environment. Do not enable until the user approves the upgrade and a supervised preview test.

## 0.2.2 — 2026-11-04

### Added
- Persistent `preview_result_at` and `preview_result` attributes after every completed preview.
- Persistent `publish_result_at` after every completed publishing attempt, including failures.
- Four optional Home Assistant email automation examples in [NOTIFICATIONS.md](NOTIFICATIONS.md):
  preview ready, preview failed, publish verified and publish failed.

### Notes
- Gmail is configured and authorised through Home Assistant, not this app.
- Notifications are optional and do not approve or publish to TIDAL.
- Existing preview-ready automations should be migrated to the new timestamp trigger.
- Browser/app branding assets are being prepared separately and are **not included in 0.2.2**.
- Notification delivery is best effort; Home Assistant downtime can miss events.

## 0.2.1 — 2026-11-03

### Added
- Permanent song blocklist persistence from the phone review's **Block from future proposals** choice. Saved blocks apply to subsequent previews.
- Updated HACS-facing README, installation and safety guidance, and maintained release notes.

### Notes
- The existing app name **Trend Playlist Preview** remains for installation compatibility, even though it now supports approved publishing.
- Changing a blocked song's review choice does not remove its permanent block.
- Zeitgeist promotion and Gmail delivery remain pending.

## 0.2.0 — 2026-11-03

### Added
- Separate **Publish approved playlist** button gated by approval and preflight.
- In-place TIDAL update with locked plan, recovery snapshot, final verification and a fail-closed publishing journal.
- Live publish verified on a 50-track playlist, with existing ID and artwork confirmed manually.

### Safety
- Publishing is never automatic; Monday runs remain previews.
- Partial failures require supervised recovery rather than blind retry.

## 0.1.9 — 2026-11-03

- Added read-only **check publish safety** button and live baseline preflight.

## 0.1.8 — 2026-11-03

- Named removal tracks and separate `zeitgeist_pending` review.
- Persisted exact approved track ID sequence.

## 0.1.7 — 2026-11-03

- Per-removal retain/remove controls and approval recording.
- Approval invalidation on review changes.

## 0.1.6 — 2026-11-02

- Automatic ranked replacement of excluded tracks from a verified reserve pool.

## 0.1.5 — 2026-11-02

- Per-track phone review decisions.

## 0.1.4 and earlier

- Preview proposal sensor, source matching, weekly scheduler, protected playlist baseline and initial HACS integration.
