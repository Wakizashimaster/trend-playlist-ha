# Respect manual TIDAL removals — implementation contract

Status: design for an opt-in feature; **not enabled or implemented**.

## User behaviour

When enabled, a track manually removed from the protected *Down with the Kids* playlist is excluded from subsequent Trendee proposals until explicitly unblocked. The user can continue editing the playlist in TIDAL. Scheduled Monday runs remain preview-only.

## Critical current limitation

`auto_refresh.main(preview=True)` currently invokes `verify_live_baseline(previous["track_ids"])` before discovery. Any manual playlist edit therefore stops the preview. This guard must not simply be removed: it protects publishing from stale plans.

## Proposed implementation and acceptance checks

1. Introduce an opt-in add-on setting, default **false**. Do not change existing installs' behaviour without consent.
2. Read the exact protected playlist ID, verify its name, obtain complete ordered IDs twice (or otherwise detect concurrent changes), and fail closed on authentication, pagination, duplicates, unexpected playlist size, or ambiguous identity.
3. Compare against the last successfully verified baseline. The verified in-place publisher updates that baseline after publish; its removals are **not** user removals. If the publish journal is unresolved, refuse reconciliation.
4. Detect `baseline - live` as manual removals; capture verified artist/title metadata before persisting permanent song blocks. Store an auditable record with track ID, title, artist, detection time and source. If metadata cannot be verified, do not silently create a song block.
5. Preserve manual additions to the live playlist in the new baseline. Never silently erase them on publish; require the normal review and preflight, and verify the live sequence again immediately before mutation.
6. Reconcile only after successful read/validation and write a backup of the previous baseline before atomic replacement. If any stage fails, do not alter blocks or baseline.
7. Apply blocks to discovery *before* selecting the 50- and 80-track pools; ensure no blocked song can enter via a catalogue alternate/override or review replacement.
8. Provide an explicit unblock operation, list of exclusions, and the ability to disable automatic detection without deleting already stored exclusions. Distinguish manually detected exclusions from explicitly user-blocked songs.
9. Invalidate existing proposal, approval and preflight on reconciliation; a new preview must generate fresh review artifacts.
10. Test: unchanged playlist; one manual removal; multiple removals; manual addition; reorder-only; failed/partial TIDAL reads; ambiguous playlist; unresolved publish journal; concurrent edit; last verified publish removals; metadata missing; unblock; blocked alternate match; safe preflight; opt-out.
11. Never write to TIDAL during detection, preview, or tests. Publish remains a separate explicit approval and preflight flow.

## Rollout

Develop and test on this feature branch. Do not merge or enable on the live Home Assistant installation until automated tests pass and the user approves the release.
