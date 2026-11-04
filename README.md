# Trend Playlist for Home Assistant

**Discover what's trending. Review it on your phone. Publish to TIDAL only when you decide.**

Trend Playlist is a community-maintained Home Assistant OS app (add-on) and HACS custom integration for a carefully guarded, human-approved TIDAL playlist workflow. It collects UK trend signals, checks release eligibility, matches tracks on TIDAL and prepares a proposed playlist update for review.

> **Independent community project.** Not affiliated with or endorsed by Home Assistant, HACS, TIDAL, Spotify, Apple Music, or Official Charts. Chart and music metadata remain the property of their respective owners. You need your own TIDAL account and a working authenticated session. Use at your own risk; back up your playlist before the first publish.

[Installation and configuration](INSTALL.md) · [Email notifications](NOTIFICATIONS.md) · [Release history](CHANGELOG.md)

## Features

- **Weekly discovery:** Monday at 08:00 Europe/London, with a manual preview button.
- **Phone-friendly review:** proposed additions/removals, individual exclude, retain and Zeitgeist intent, automatic eligible replacements and explicit approval.
- **Separate publish action:** approval, live-playlist safety preflight and publish are three distinct steps.
- **In-place TIDAL updates:** protected existing playlist identity, recovery snapshots, final track verification and a fail-closed publishing journal.
- **Permanent song blocks:** an explicit *Block from future proposals* choice writes to the local blocklist; blocks survive subsequent previews.
- **No automatic publishing:** scheduled jobs only prepare previews. The live playlist changes only when you press **Publish approved playlist**.

## Safety and scope

The current app targets **one configured-in-code playlist, Down with the Kids**. It is **not** a general-purpose multi-playlist integration. Publishing can alter your live playlist. A partial TIDAL/network failure may require supervised manual recovery; the app will not automatically retry or delete and recreate the playlist. Do not expose the app's API port to the internet.

Zeitgeist selections are **recorded only** at present; publishing to the separate Zeitgeist playlist is not enabled. Optional Home Assistant Gmail notification automation examples are available in [NOTIFICATIONS.md](NOTIFICATIONS.md). The app does not send Gmail messages directly.

## Installation

Add this repository to the Home Assistant **App Store** for the app, and as a **custom Integration repository** in HACS for the Home Assistant entities. The app and HACS integration are **separate installs**.

See [INSTALL.md](INSTALL.md) for prerequisites, secure migration, the complete approval-to-publish sequence and troubleshooting.

## Project structure

- `trend_playlist_preview/` — Home Assistant OS app, scheduler and TIDAL worker.
- `custom_components/trend_playlist/` — HACS integration: sensors, selects and buttons.
- `INSTALL.md` — setup and operation.
- `CHANGELOG.md` — user-facing release notes.

## Privacy and maintenance

TIDAL session data, API tokens, blocklists, approval decisions, recovery snapshots and Gmail credentials belong **only in your local Home Assistant app configuration**. Never commit them or paste them into issues. Report defects with redacted logs, app/integration versions and reproducible steps. Avoid using the publish button again after a partial failure.

This repository contains installation code, not private playlist state.
