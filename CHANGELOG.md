# Changelog

All notable user-facing changes are recorded here. Releases follow semantic versioning where practical. The Home Assistant app and HACS integration should be updated together.

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
