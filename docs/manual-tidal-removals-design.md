# Respect manual TIDAL removals — implementation contract

Status: design for an opt-in feature; **not enabled or implemented**.

## User behaviour

When enabled, a track manually removed from the protected *Down with the Kids* playlist is excluded from subsequent Trendee proposals until the track is manually re-added in TIDAL. The user can continue editing the playlist in TIDAL. Scheduled Monday runs remain preview-only.

## Critical current limitation

`auto_refresh.main(preview=True)` currently invokes `verify_live_baseline(previous["track_ids"])` before discovery. Any manual playlist edit therefore stops the preview. This guard must not simply be removed: it protects publishing from stale plans.

## Proposed implementation and acceptance checks

1. Introduce an opt-in add-on setting, default **false**. Do not change existing installs' behaviour without consent.
2. Read the exact protected playlist ID, verify its name, obtain complete ordered IDs twice (or otherwise detect concurrent changes), and fail closed on authentication, pagination, duplicates, unexpected playlist size, or ambiguous identity.
3. Compare against the last successfully verified baseline. The verified in-place publisher updates that baseline after publish; its removals are **not** user removals. If the publish journal is unresolved, refuse reconciliation.
4. Detect `baseline - live` as manual removals; record reversible TIDAL-ID exclusions separately from permanent song blocks. Store an auditable record with track ID, detection time and source; resolve artist/title metadata for display when available.
5. Preserve manual additions to the live playlist in the new baseline. Never silently erase them on publish; require the normal review and preflight, and verify the live sequence again immediately before mutation.
6. Reconcile only after successful read/validation and write a backup of the previous baseline before atomic replacement. If any stage fails, do not alter blocks or baseline.
7. Apply blocks to discovery *before* selecting the 50- and 80-track pools; ensure no blocked song can enter via a catalogue alternate/override or review replacement.
8. Automatically lift a reversible exclusion when its track ID reappears in the live playlist. Provide a list of exclusions and optional manual clear control. Keep explicitly user-blocked songs permanent.
9. Invalidate existing proposal, approval and preflight on reconciliation; a new preview must generate fresh review artifacts.
10. Test: unchanged playlist; one manual removal; multiple removals; manual addition; reorder-only; failed/partial TIDAL reads; ambiguous playlist; unresolved publish journal; concurrent edit; last verified publish removals; metadata missing; re-add and automatic unblock; blocked alternate match; safe preflight; opt-out.
11. Never write to TIDAL during detection, preview, or tests. Publish remains a separate explicit approval and preflight flow.

## Rollout

Develop and test on this feature branch. Do not merge or enable on the live Home Assistant installation until automated tests pass and the user approves the release.

## Revised user decision (2026-11-04)

Manual TIDAL removals are **reversible**, not permanent. Re-adding the same TIDAL track ID to the live playlist clears its automatic exclusion on the next successful preview. A Trendee explicit song block remains permanent. A re-added song becomes eligible, not guaranteed a place in the top 50. The pure reconciliation policy and offline unit tests are now on this branch; wiring into live preview, safe persistence, and candidate selection is still pending.

## Implementation progress

- Pure reconciliation policy: `trend_playlist_preview/app/manual_reconciliation.py`.
- Durable reversible exclusion store: `trend_playlist_preview/app/manual_exclusions.py` (atomic JSON writes and timestamped events).
- Offline unit tests: `tests/test_manual_reconciliation.py`, `tests/test_manual_exclusions.py`.
- **Not yet wired to the Monday preview or candidate matching.** The store does not itself authorize changing the trusted baseline. Safe reconciliation must validate the publish journal and two consistent live reads, back up the baseline, and commit changes with recovery semantics before enabling the feature.
- The store is keyed by TIDAL track ID; song-level aliases and catalog alternatives require separate matching safeguards.
