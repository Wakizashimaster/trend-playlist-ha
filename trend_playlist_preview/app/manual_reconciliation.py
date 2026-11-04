"""Pure reconciliation policy for user edits to the protected TIDAL playlist.

No network calls and no writes. The caller must supply two identical,
complete, independently read live snapshots before accepting this plan.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Reconciliation:
    live_ids: tuple[str, ...]
    removed_ids: tuple[str, ...]
    restored_ids: tuple[str, ...]
    added_ids: tuple[str, ...]
    reordered: bool

def reconcile(previous_ids, live_ids, excluded_ids, *, min_tracks=20, max_edits=10):
    old = tuple(str(x) for x in previous_ids)
    live = tuple(str(x) for x in live_ids)
    excluded = {str(x) for x in excluded_ids}
    if (len(old) < min_tracks or len(live) < min_tracks
            or len(old) != len(set(old)) or len(live) != len(set(live))
            or not all(x.isdigit() for x in old + live)):
        raise ValueError("Invalid or incomplete playlist snapshot; reconciliation refused")
    old_set, live_set = set(old), set(live)
    removed = tuple(x for x in old if x not in live_set)
    added = tuple(x for x in live if x not in old_set)
    restored = tuple(x for x in live if x in excluded)
    if len(removed) + len(added) > max_edits:
        raise ValueError("Too many manual playlist changes; review before reconciling")
    return Reconciliation(
        live_ids=live,
        removed_ids=removed,
        restored_ids=restored,
        added_ids=added,
        reordered=not removed and not added and old != live,
    )

def next_exclusions(previous_excluded, result):
    """Missing IDs remain excluded until re-added to the live playlist."""
    return (set(map(str, previous_excluded)) | set(result.removed_ids)) - set(result.restored_ids)
