"""Release-age policy and best-effort metadata lookup for Trend Playlist."""
from __future__ import annotations

import calendar
import difflib
import json
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path


def cutoff_years(today: date, years: int) -> date:
    year = today.year - years
    day = min(today.day, calendar.monthrange(year, today.month)[1])
    return date(year, today.month, day)


def classify(release_date: str, signals: dict, allow_revivals: bool, today: date | None = None, years: int = 3) -> str:
    """recent, revival, old, or unknown. Seeds do not count as independent evidence."""
    try:
        released = date.fromisoformat((release_date or "")[:10])
    except ValueError:
        return "unknown"
    today = today or date.today()
    if released > today:
        return "unknown"
    if released >= cutoff_years(today, years):
        return "recent"
    independent = set(signals) & {"apple", "chart", "tiktok"}
    return "revival" if allow_revivals and len(independent) >= 2 else "old"


def lookup_release(artist: str, title: str, cache: dict, key: str, norm, clean_title) -> str:
    """Look up an earliest matching iTunes track date. Uncertain matches stay unknown."""
    if key in cache:
        return cache[key]
    query = urllib.parse.urlencode({"term": f"{artist} {title}", "entity": "song", "country": "gb", "limit": 200})
    url = "https://itunes.apple.com/search?" + query
    found = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "trend-playlist/0.2"})
        with urllib.request.urlopen(req, timeout=12) as response:
            results = json.load(response).get("results", [])
        wanted_title = clean_title(title)
        wanted_artist = norm(artist)
        for r in results:
            actual_title = clean_title(r.get("trackName", ""))
            if not actual_title or difflib.SequenceMatcher(None, actual_title, wanted_title).ratio() < 0.88:
                continue
            actual_artist = norm(r.get("artistName", ""))
            if not actual_artist or not wanted_artist:
                continue
            if (actual_artist != wanted_artist and actual_artist not in wanted_artist
                    and wanted_artist not in actual_artist
                    and difflib.SequenceMatcher(None, actual_artist, wanted_artist).ratio() < 0.82):
                continue
            raw = r.get("releaseDate", "")[:10]
            try:
                date.fromisoformat(raw)
            except ValueError:
                continue
            found.append(raw)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"warning: release lookup failed for {artist} - {title}: {exc}", file=__import__("sys").stderr)
    # Conflicting dates across the eligibility boundary are ambiguous (often
    # reissues or compilations). Never silently classify them as old or new.
    cutoff = cutoff_years(date.today(), 3).isoformat()
    value = ""
    if found and not (min(found) < cutoff <= max(found)):
        value = min(found)
    if value:
        cache[key] = value
    return value


_LAST_MB_REQUEST = 0.0


def lookup_musicbrainz(artist: str, title: str, norm, clean_title) -> str:
    """Conservative recording lookup; return earliest release only for a strong match."""
    global _LAST_MB_REQUEST
    query = urllib.parse.urlencode({
        "query": f'recording:"{title}" AND artist:"{artist}"',
        "fmt": "json", "limit": 10,
    })
    url = "https://musicbrainz.org/ws/2/recording/?" + query
    delay = 1.1 - (time.monotonic() - _LAST_MB_REQUEST)
    if delay > 0:
        time.sleep(delay)
    _LAST_MB_REQUEST = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "TrendPlaylist/0.3 (https://github.com/Wakizashimaster/trend-playlist)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=12) as response:
            results = json.load(response).get("recordings", [])
        matches = []
        for record in results:
            if int(record.get("score", 0)) < 95:
                continue
            if clean_title(record.get("title", "")) != clean_title(title):
                continue
            credited = " ".join(x.get("name", "") for x in record.get("artist-credit", [])
                                if isinstance(x, dict))
            if not credited or (norm(artist) not in norm(credited)
                                and norm(credited) not in norm(artist)):
                continue
            raw = record.get("first-release-date", "")[:10]
            try:
                date.fromisoformat(raw)
            except ValueError:
                continue
            matches.append(raw)
        return min(matches) if matches else ""
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def lookup_verified_release(artist: str, title: str, cache: dict, key: str, norm, clean_title) -> str:
    """Use MusicBrainz when available; flag conflicting catalogue evidence."""
    if key in cache:
        return cache[key]
    mb = lookup_musicbrainz(artist, title, norm, clean_title)
    itunes = lookup_release(artist, title, cache, key, norm, clean_title)
    if mb and itunes and (mb < cutoff_years(date.today(), 3).isoformat()) != (
            itunes < cutoff_years(date.today(), 3).isoformat()):
        cache.pop(key, None)
        return ""
    value = mb or itunes
    if value:
        cache[key] = value
    return value


def load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
