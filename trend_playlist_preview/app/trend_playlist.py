#!/usr/bin/env python3
"""trend_playlist.py - curate a UK "what's popular right now" list and push it to TIDAL.

Workflow
  1. python trend_playlist.py sweep    fetch sources, score, write data/review.csv
  2. Open data/review.csv. In the `action` column put:
         x   = never pick this song again
         xa  = never pick this artist again
     (optionally add a note in `reason`). Leave blank to keep.
  3. python trend_playlist.py apply    saves your blocks, writes data/approved.csv
  4. python trend_playlist.py push     matches tracks on TIDAL, creates the playlist
     (add --dry-run first to only write data/match_report.csv)

Prefer a browser? `python gui.py` drives all of the above (see README.md).

Blocks live in data/blocklist.csv and are honoured by every later sweep.
Manage them directly with:  block / unblock / blocklist

Sources (each optional, all rank-ordered):
  apple   Apple Music UK most-played feed (keyless, fetched live)
  chart   data/inputs/uk_chart.csv   (columns: artist,title - e.g. the Official Chart
          top 40 supplied from a source you are licensed/allowed to use)
  tiktok  data/inputs/tiktok.csv     (columns: artist,title) or --tokchart (opt-in scrape)
  seed    data/seeds.csv             (hand-picked trend songs, flat score bonus)

Requires: Python 3.9+. `pip install tidalapi` for push; `pip install beautifulsoup4`
only if you use --tokchart.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import time
import urllib.robotparser
import sys
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

import release_policy as rp

# Data lives next to this script (override with TREND_PLAYLIST_DATA) so it works from any folder.
DATA = Path(os.environ.get("TREND_PLAYLIST_DATA") or Path(__file__).resolve().parent / "data")
INPUTS = DATA / "inputs"
SEEDS = DATA / "seeds.csv"
BLOCKLIST = DATA / "blocklist.csv"
REVIEW = DATA / "review.csv"
APPROVED = DATA / "approved.csv"
MATCH_REPORT = DATA / "match_report.csv"
MATCH_CANDIDATES = DATA / "match_candidates.csv"
SESSION_FILE = DATA / "tidal_session.json"

APPLE_URL = "https://rss.applemarketingtools.com/api/v2/{cc}/music/most-played/{n}/songs.json"
TOKCHART_URL = "https://tokchart.com/tiktok-trending-songs/uk"
UA = {"User-Agent": "trend-playlist/0.1 (personal use)"}

# Score = sum over sources of weight * rank_score (1.0 at rank 1, ~0 at the bottom).
WEIGHTS = {"chart": 1.0, "apple": 1.0, "spotify": 0.9, "tiktok": 0.6, "seed": 0.5}
MARKET = {"chart", "apple", "spotify", "tiktok"}

DEFAULT_SEEDS = """artist,title
Sam Fender & Olivia Dean,Rein Me In
Olivia Dean,Man I Need
Olivia Dean,So Easy (To Fall In Love)
Olivia Dean,Nice To Each Other
Lola Young,Messy
Myles Smith,Nice To Meet You
RAYE,WHERE IS MY HUSBAND!
Skye Newman,Family Matters
Gracie Abrams,That's So True
"""

BLOCK_FIELDS = ["scope", "key", "artist", "title", "reason", "added"]
REVIEW_FIELDS = ["action", "score", "artist", "title", "signals", "release_date", "release_status", "reason", "key"]


# --------------------------------------------------------------------------- utils
def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel opens accents / non-Latin titles correctly
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_pairs(path: Path) -> list[tuple[str, str]]:
    out = []
    for r in read_csv(path):
        a, t = (r.get("artist") or "").strip(), (r.get("title") or "").strip()
        if a and t:
            out.append((a, t))
    return out


def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ----------------------------------------------------------------- normalisation
_FEAT = re.compile(r"\s*[\(\[]\s*(feat|ft|with|prod)\b[^\)\]]*[\)\]]", re.I)
_SUFFIX = re.compile(r"\s+[-\u2013]\s+.*(remaster|version|edit|mix|live|sped|slowed|from\b).*$", re.I)
_BRACKETS = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
_SPLIT = re.compile(r"\s*(?:,|/|&|\band\b|\bx\b|\bfeat\.?|\bft\.?|\bwith\b|\bvs\.?)\s*", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[^\w ]+", " ", s.replace("&", " and "))
    return re.sub(r"\s+", " ", s).strip()


def clean_title(t: str) -> str:
    t = _FEAT.sub("", t)
    t = _SUFFIX.sub("", t)
    t = _BRACKETS.sub("", t)
    return norm(t)


def artists_of(a: str) -> list[str]:
    return [n for n in (norm(p) for p in _SPLIT.split(a)) if n]


def artist_identity(artist: str) -> str:
    """Ignore artist punctuation for credit comparisons, not track titles."""
    return re.sub(r"[^a-z0-9]+", "", norm(artist))


def track_identity(artist: str, title: str) -> tuple[str, tuple[str, ...]]:
    """Canonical identity for duplicate input rows with reordered artist credits."""
    return clean_title(title), tuple(sorted(set(
        artist_identity(a) for a in artists_of(artist) if artist_identity(a))))


def dedupe_tracks(rows: list[dict]) -> list[dict]:
    """Keep the first reviewed row; do not fabricate an alternative recording."""
    seen, unique = set(), []
    for row in rows:
        identity = track_identity(row["artist"], row["title"])
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(row)
    return unique


def make_key(artist: str, title: str) -> str:
    names = artists_of(artist)
    return f"{names[0] if names else norm(artist)}|{clean_title(title)}"


# ----------------------------------------------------------------------- sources
def fetch_apple(cc: str = "gb", n: int = 100) -> list[tuple[str, str]]:
    """Retry transient gateway failures and try Apple's alternate public RSS host."""
    from urllib.error import HTTPError, URLError
    urls = [APPLE_URL.format(cc=cc, n=n),
            f"https://rss.marketingtools.apple.com/api/v2/{cc}/music/most-played/{n}/songs.json"]
    errors = []
    for url in urls:
        for attempt in range(3):
            try:
                data = json.loads(http_get(url))
                rows = [(r["artistName"], r["name"]) for r in data["feed"]["results"]]
                if len(rows) < 20:
                    raise ValueError("Apple feed unexpectedly short")
                return rows
            except HTTPError as exc:
                errors.append(f"{url.split('/')[2]}: HTTP {exc.code}")
                if exc.code not in (429, 500, 502, 503, 504):
                    break
            except (URLError, TimeoutError, OSError) as exc:
                errors.append(f"{url.split('/')[2]}: {type(exc).__name__}")
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f"{url.split('/')[2]}: invalid feed ({exc})")
                break
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError("Apple chart unavailable: " + "; ".join(errors[-6:]))


def fetch_spotify_uk_kworb(n: int = 100) -> list[tuple[str, str]]:
    """Read public UK Spotify rankings mirrored by Kworb; no Spotify login."""
    from html.parser import HTMLParser

    class ChartParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_row = False
            self.in_cell = False
            self.cell = []
            self.cells = []
            self.rows = []

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.in_row, self.cells = True, []
            elif self.in_row and tag in ("td", "th"):
                self.in_cell, self.cell = True, []

        def handle_data(self, data):
            if self.in_cell:
                self.cell.append(data)

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self.in_cell:
                self.cells.append(" ".join("".join(self.cell).split()))
                self.in_cell = False
            elif tag == "tr" and self.in_row:
                if self.cells:
                    self.rows.append(self.cells)
                self.in_row = False

    page = http_get("https://kworb.net/spotify/country/gb_daily.html")
    import re as _re
    from datetime import datetime as _datetime, timedelta as _timedelta
    date_match = _re.search(r"Spotify Daily Chart\s*-\s*United Kingdom\s*-\s*(\d{4}/\d{2}/\d{2})", page)
    if not date_match:
        raise ValueError("Spotify mirror has no recognizable chart date")
    chart_day = _datetime.strptime(date_match.group(1), "%Y/%m/%d").date()
    if not (_datetime.now().date() - _timedelta(days=4) <= chart_day <= _datetime.now().date()):
        raise ValueError(f"Spotify mirror chart is stale: {chart_day}")
    parser = ChartParser()
    parser.feed(page)
    tracks = []
    for cells in parser.rows:
        if len(cells) < 3 or not cells[0].isdigit() or int(cells[0]) != len(tracks) + 1:
            continue
        if " - " not in cells[2]:
            continue
        artist, title = cells[2].split(" - ", 1)
        if artist.strip() and title.strip():
            tracks.append((artist.strip(), title.strip()))
        if len(tracks) >= n:
            break
    if len(tracks) < 25:
        raise ValueError(f"Spotify mirror yielded only {len(tracks)} ranked tracks")
    return tracks


def robots_diagnostic(url: str) -> tuple[str, str]:
    """Distinguish missing robots, explicit denial and transport errors."""
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlsplit
    from urllib.robotparser import RobotFileParser
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        req = urllib.request.Request(robots_url, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as response:
            body = response.read(512_000).decode("utf-8", "replace")
    except HTTPError as exc:
        if exc.code in (404, 410):
            return "missing", f"{robots_url}: HTTP {exc.code} (no rules published)"
        return "unavailable", f"{robots_url}: HTTP {exc.code}"
    except (URLError, OSError, ValueError) as exc:
        return "unavailable", f"{robots_url}: {exc}"
    parser = RobotFileParser()
    parser.parse(body.splitlines())
    allowed = parser.can_fetch(UA["User-Agent"], url)
    return ("allowed" if allowed else "denied",
            f"{robots_url}: {'allowed' if allowed else 'explicitly denied'} for {url}")


def permitted_public_page(url: str) -> bool:
    state, detail = robots_diagnostic(url)
    print(f"  robots: {detail}", flush=True)
    if state == "allowed" or state == "missing":
        return True
    if state == "denied":
        raise RuntimeError(f"Robots rules deny automated access: {detail}")
    raise RuntimeError(f"Robots status could not be verified: {detail}")


def fetch_tokchart(url: str = TOKCHART_URL) -> list[tuple[str, str]]:
    if not permitted_public_page(url):
        raise RuntimeError(f"Robots permission not granted for {url}")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(http_get(url), "html.parser")
    out = []
    for tr in soup.select("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        lines = [x.strip() for x in cells[1].get_text("\\n", strip=True).split("\\n") if x.strip()]
        if len(lines) >= 2:
            out.append((lines[1], lines[0]))
    if not out:
        raise ValueError("Tokchart layout changed or no public tracks were found")
    return out[:10]


def fetch_official_chart(url: str = "https://www.officialcharts.com/charts/singles-chart/") -> list[tuple[str, str]]:
    if not permitted_public_page(url):
        raise RuntimeError(f"Robots permission not granted for {url}")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(http_get(url), "html.parser")
    out = []
    for item in soup.select("[data-testid='chart-item'], .chart-item, .chart-list-item"):
        title = item.select_one("[data-testid='track-title'], .track-title, .chart-name")
        artist = item.select_one("[data-testid='track-artist'], .track-artist, .chart-artist")
        if title and artist:
            pair = (artist.get_text(" ", strip=True), title.get_text(" ", strip=True))
            if all(pair) and pair not in out:
                out.append(pair)
    if len(out) < 10:
        raise ValueError("Official Charts layout not recognized; chart source skipped")
    return out[:100]


def cached_source(name: str, fetcher, max_age_hours: int) -> list[tuple[str, str]]:
    path = DATA / "source_cache" / f"{name}.json"
    now = time.time()
    cached = {}
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    age = now - cached.get("fetched_at", 0)
    if cached.get("tracks") and 0 <= age < max_age_hours * 3600:
        print(f"  {name}: cached {len(cached['tracks'])} tracks ({age / 3600:.1f}h old)")
        return [tuple(p) for p in cached["tracks"]]
    try:
        tracks = fetcher()
        if not tracks:
            raise ValueError("empty chart")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": now, "tracks": tracks}), encoding="utf-8")
        print(f"  {name}: refreshed {len(tracks)} tracks")
        return tracks
    except Exception as exc:
        if cached.get("tracks") and 0 <= age < max_age_hours * 3600 * 3:
            print(f"warning: {name}: {exc}; using stale cache ({age / 3600:.1f}h)", file=sys.stderr)
            return [tuple(p) for p in cached["tracks"]]
        print(f"warning: {name}: {exc}; source unavailable", file=sys.stderr)
        return []



def gather_sources(args) -> dict[str, list[tuple[str, str]]]:
    INPUTS.mkdir(parents=True, exist_ok=True)
    if not SEEDS.exists():
        SEEDS.write_text(DEFAULT_SEEDS, encoding="utf-8")
    src: dict[str, list[tuple[str, str]]] = {}
    src["chart"] = (cached_source("official_chart", fetch_official_chart, 168)
                    if getattr(args, "official_chart", False) else [])
    manual_chart = read_pairs(INPUTS / "uk_chart.csv")
    if manual_chart:
        src["chart"] = manual_chart
        print("  chart: manual CSV override")
    try:
        src["apple"] = fetch_apple(args.country, args.apple_depth)
    except Exception as e:  # network or schema problem: carry on with other sources
        print(f"warning: Apple feed failed ({e})", file=sys.stderr)
        src["apple"] = []
    tt = read_pairs(INPUTS / "tiktok.csv")
    if args.tokchart and not tt:
        tt = cached_source("tokchart_uk", fetch_tokchart, 24)
    src["spotify"] = (cached_source("spotify_uk_kworb", fetch_spotify_uk_kworb, 18)
                      if getattr(args, "spotify_mirror", False) else [])
    src["tiktok"] = tt
    src["seed"] = read_pairs(SEEDS)
    return src


# ----------------------------------------------------------------------- scoring
def build_candidates(sources: dict[str, list[tuple[str, str]]]) -> dict[str, dict]:
    cands: dict[str, dict] = {}
    for name in ("chart", "apple", "spotify", "tiktok", "seed"):  # canonical spelling: first seen wins
        pairs = sources.get(name, [])
        n = len(pairs)
        for rank, (artist, title) in enumerate(pairs, 1):
            key = make_key(artist, title)
            c = cands.setdefault(key, {"key": key, "artist": artist, "title": title,
                                       "signals": {}, "score": 0.0})
            if name in c["signals"]:
                continue
            c["signals"][name] = rank
            c["score"] += WEIGHTS[name] * (1.0 if name == "seed" else (n - rank + 1) / n)
    return cands


def load_blocklist() -> tuple[set[str], set[str]]:
    songs, artists = set(), set()
    for r in read_csv(BLOCKLIST):
        (artists if r["scope"] == "artist" else songs).add(r["key"])
    return songs, artists


def add_blocks(new: list[dict]) -> int:
    existing = read_csv(BLOCKLIST)
    seen = {(r["scope"], r["key"]) for r in existing}
    added = 0
    for r in new:
        if (r["scope"], r["key"]) in seen:
            continue
        seen.add((r["scope"], r["key"]))
        existing.append({**r, "added": date.today().isoformat()})
        added += 1
    write_csv(BLOCKLIST, BLOCK_FIELDS, existing)
    return added


def block_record(artist: str, title: str = "", reason: str = "") -> dict:
    """Build a blocklist row: a song block if a title is given, otherwise an artist block."""
    if title:
        return {"scope": "song", "key": make_key(artist, title), "artist": artist,
                "title": title, "reason": reason}
    names = artists_of(artist)
    return {"scope": "artist", "key": names[0] if names else norm(artist), "artist": artist,
            "title": "", "reason": reason}


def remove_block(scope: str, key: str) -> bool:
    rows = read_csv(BLOCKLIST)
    left = [r for r in rows if not (r["scope"] == scope and r["key"] == key)]
    write_csv(BLOCKLIST, BLOCK_FIELDS, left)
    return len(left) < len(rows)


def select(cands: dict[str, dict], size: int, max_tiktok_only: int, require_two: bool, max_revivals: int | None = None) -> list[dict]:
    b_songs, b_artists = load_blocklist()
    pool = [c for c in cands.values()
            if c["key"] not in b_songs and not any(a in b_artists for a in artists_of(c["artist"]))]
    # Keep excluded songs visible, but put eligible songs first.
    priority = {"recent": 0, "revival": 0, "unknown": 1, "old": 2}
    pool.sort(key=lambda c: (priority.get(c.get("release_status"), 0), -c["score"],
                             c["artist"].lower(), c["title"].lower()))
    out, tt_only, revivals = [], 0, 0
    for c in pool:
        sigs = set(c["signals"])
        if require_two and "seed" not in sigs and len(sigs & MARKET) < 2:
            continue
        if sigs == {"tiktok"}:  # viral-only songs are capped: they are often seasonal/catalogue noise
            if tt_only >= max_tiktok_only:
                continue
            tt_only += 1
        if c.get("release_status") == "revival":
            if max_revivals is not None and revivals >= max_revivals:
                continue
            revivals += 1
        out.append(c)
        if len(out) >= size:
            break
    return out


# ---------------------------------------------------------------------- commands
def cmd_sweep(args) -> None:
    DATA.mkdir(exist_ok=True)
    sources = gather_sources(args)
    for name, pairs in sources.items():
        print(f"  {name:<7}{len(pairs):>4} tracks")
    cands = build_candidates(sources)
    cache_path = DATA / "release_dates.json"
    cache = rp.load_cache(cache_path)
    counts = {"recent": 0, "revival": 0, "old": 0, "unknown": 0}
    total = len(cands)
    print(f"PROGRESS|metadata|0|{total}|Starting release-date verification", flush=True)
    for index, c in enumerate(cands.values(), 1):
        print(f"PROGRESS|metadata|{index - 1}|{total}|Checking {c['artist']} - {c['title']}", flush=True)
        released = (rp.lookup_verified_release if getattr(args, "musicbrainz", False) else rp.lookup_release)(c["artist"], c["title"], cache, c["key"], norm, clean_title)
        status = rp.classify(released, c["signals"], args.allow_revivals, years=args.release_years)
        c["release_date"], c["release_status"] = released, status
        counts[status] += 1
        print(f"PROGRESS|metadata|{index}|{total}|{c['artist']} - {c['title']}: {status}", flush=True)
    print(f"PROGRESS|review|{total}|{total}|Writing review CSV", flush=True)
    rp.save_cache(cache_path, cache)
    # Keep old and unknown tracks visible for audit; approval still excludes them.
    items = select(cands, args.review_size, args.max_tiktok_only, args.require_two)
    print(f"Unique candidates: {len(cands)}; review size: {args.review_size}")
    print("Release checks: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    rows = [{
        "action": "", "score": f"{c['score']:.3f}", "artist": c["artist"], "title": c["title"],
        "signals": " ".join(f"{k}#{v}" if k != "seed" else "seed" for k, v in c["signals"].items())
                   + (" (tiktok-only)" if set(c["signals"]) == {"tiktok"} else ""),
        "release_date": c["release_date"], "release_status": c["release_status"],
        "reason": "", "key": c["key"],
    } for c in items]
    print("Review rows: " + ", ".join(
        f"{status}={sum(r['release_status'] == status for r in rows)}" for status in counts))
    write_csv(REVIEW, REVIEW_FIELDS, rows)
    print(f"Wrote {len(rows)} candidates to {REVIEW}. Mark x / xa, then run: apply")
    print(f"PROGRESS|done|{total}|{total}|Sweep completed", flush=True)


def cmd_apply(args) -> None:
    rows = read_csv(REVIEW)
    if not rows:
        sys.exit(f"{REVIEW} is missing or empty - run sweep first")
    blocks, kept = [], []
    for r in rows:
        act = (r.get("action") or "").strip().lower()
        if act == "x":
            blocks.append({"scope": "song", "key": r["key"], "artist": r["artist"],
                           "title": r["title"], "reason": r.get("reason", "")})  # key kept as swept
        elif act == "xa":
            blocks.append(block_record(r["artist"], reason=r.get("reason", "")))
        else:
            if act:
                print(f"note: unknown action {act!r} for {r['artist']} - {r['title']}; keeping it")
            kept.append(r)
    added = add_blocks(blocks)
    b_songs, b_artists = load_blocklist()
    kept = [r for r in kept if r["key"] not in b_songs
            and not any(a in b_artists for a in artists_of(r["artist"]))]  # an xa also removes its other rows
    kept = dedupe_tracks(kept)
    approved = []
    revivals = 0
    for r in kept:
        status = r.get("release_status", "unknown")
        if status == "unknown":
            print(f"needs release-date verification: {r['artist']} - {r['title']}")
            continue
        if status == "revival":
            if revivals >= args.max_revivals:
                continue
            revivals += 1
        elif status != "recent":
            continue
        approved.append(r)
        if len(approved) >= args.size:
            break
    print(f"Approval summary: {len(approved)} eligible, {revivals} revivals (cap {args.max_revivals})")
    write_csv(APPROVED, ["artist", "title", "key"], approved)
    print(f"{added} new block(s) saved. {len(approved)} tracks approved -> {APPROVED}")


def cmd_block(args) -> None:
    if args.artist:
        rec = block_record(args.artist, reason=args.reason)
    elif args.song:
        rec = block_record(args.song[0], args.song[1], args.reason)
    else:
        sys.exit("use --artist NAME or --song ARTIST TITLE")
    print("blocked" if add_blocks([rec]) else "already blocked", rec["key"])


def cmd_unblock(args) -> None:
    if args.artist:
        rec = block_record(args.artist)
    elif args.song:
        rec = block_record(args.song[0], args.song[1])
    else:
        sys.exit("use --artist NAME or --song ARTIST TITLE")
    print("removed" if remove_block(rec["scope"], rec["key"]) else "not found", rec["key"])


def cmd_blocklist(_args) -> None:
    rows = read_csv(BLOCKLIST)
    for r in rows:
        print(f"{r['scope']:<7}{r['artist']} - {r['title']}  [{r['reason']}]" if r["title"]
              else f"{r['scope']:<7}{r['artist']}  [{r['reason']}]")
    print(f"{len(rows)} entries in {BLOCKLIST}")


_ALT = re.compile(r"live|sped|slowed|remix|acoustic|karaoke|instrumental", re.I)


CANDIDATE_FIELDS = ["artist", "title", "query", "source", "tidal_id",
                    "tidal_artist", "tidal_title", "album", "version",
                    "duration_seconds", "isrc", "similarity", "artist_overlap",
                    "reason"]


def _track_candidate(track, artist, title, query, source):
    credits = getattr(track, "artists", None) or [track.artist]
    artist_names = [str(getattr(a, "name", "") or "") for a in credits]
    credited = set()
    for name in artist_names:
        credited.update(artists_of(name))
    similarity = difflib.SequenceMatcher(
        None, clean_title(title), clean_title(str(track.name))).ratio()
    overlap = bool({artist_identity(a) for a in artists_of(artist)} &
                   {artist_identity(a) for a in credited})
    version = str(getattr(track, "version", "") or "")
    alternative = bool(_ALT.search(f"{track.name} {version}") and not _ALT.search(title))
    album = getattr(track, "album", None)
    return {"artist": artist, "title": title, "query": query, "source": source,
            "tidal_id": str(track.id),
            "tidal_artist": " / ".join(artist_names),
            "tidal_title": str(track.name),
            "album": str(getattr(album, "name", "") or ""),
            "version": version,
            "duration_seconds": str(getattr(track, "duration", "") or ""),
            "isrc": str(getattr(track, "isrc", "") or ""),
            "similarity": f"{similarity:.3f}",
            "artist_overlap": str(overlap),
            "reason": ("artist mismatch" if not overlap else
                       "title mismatch" if similarity < 0.88 else
                       "alternate version" if alternative else "candidate")}


def find_track_diagnostic(session, tidalapi, artist: str, title: str, expected_isrc: str = ""):
    """Return conservative automatic match and auditable search candidates."""
    names = artists_of(artist)
    queries = [f"{names[0] if names else artist} {title}", f"{artist} {title}", title]
    candidates, objects, seen = [], {}, set()

    def collect(track, query, source):
        tid = str(track.id)
        if tid in seen:
            return
        seen.add(tid)
        record = _track_candidate(track, artist, title, query, source)
        candidates.append(record)
        objects[tid] = track

    for query in dict.fromkeys(queries):
        try:
            results = session.search(query, models=[tidalapi.Track], limit=25)
            for track in results.get("tracks", []):
                collect(track, query, "track_search")
        except Exception as exc:
            print(f"warning: TIDAL track search failed for {query}: {exc}", file=sys.stderr)

    # Album fallback is diagnostic only: it never silently changes the selected match.
    if not any(c["reason"] == "candidate" for c in candidates):
        for query in dict.fromkeys([title, f"{names[0]} {title}" if names else title]):
            try:
                results = session.search(query, models=[tidalapi.Album], limit=10)
                for album in results.get("albums", []):
                    try:
                        for track in album.tracks():
                            if difflib.SequenceMatcher(
                                    None, clean_title(title), clean_title(str(track.name))).ratio() >= 0.75:
                                collect(track, query, "album_fallback")
                    except Exception as exc:
                        print(f"warning: TIDAL album inspection failed: {exc}", file=sys.stderr)
            except Exception as exc:
                print(f"warning: TIDAL album search failed for {query}: {exc}", file=sys.stderr)

    best, score, best_source = None, 0.0, ""
    expected_isrc = expected_isrc.strip().upper()
    for candidate in candidates:
        if candidate["source"] != "track_search":
            continue
        if candidate["reason"] in ("artist mismatch", "title mismatch"):
            continue
        sim = float(candidate["similarity"])
        penalty = 0.15 if candidate["reason"] == "alternate version" else 0.0
        current = max(0.0, sim - penalty)
        if expected_isrc and candidate["isrc"].upper() != expected_isrc:
            continue
        if current > score:
            best = objects[candidate["tidal_id"]]
            score = current
            best_source = candidate["source"]
    return best, score, candidates, best_source


def find_track(session, tidalapi, artist: str, title: str):
    best, score, _candidates, _source = find_track_diagnostic(
        session, tidalapi, artist, title)
    return best, score



# Explicit, user-verified catalogue links for titles that search cannot resolve.
# Verify metadata against the expected artist and title before accepting an ID.
TIDAL_TRACK_OVERRIDES = {
    ("kolter", "hey everybody (back in the dance)"): "541782374",
}


def verified_tidal_override(session, artist, title):
    """Resolve only explicit overrides, and reject unexpected catalogue metadata."""
    key = (norm(artist), norm(title))
    overrides = {(norm(a), norm(t)): track_id
                 for (a, t), track_id in TIDAL_TRACK_OVERRIDES.items()}
    track_id = overrides.get(key)
    if not track_id:
        return None
    print(f"TIDAL override lookup: {artist} - {title} -> {track_id}", flush=True)
    try:
        track = session.track(int(track_id))
        tidal_artist = getattr(getattr(track, "artist", None), "name", "")
        tidal_title = getattr(track, "name", "")
        print(f"TIDAL override metadata: {track_id}: "
              f"{tidal_artist} - {tidal_title}", flush=True)
    except Exception as exc:
        raise RuntimeError(f"TIDAL override {track_id} lookup failed: {exc}") from exc
    expected_core = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    if (artist_identity(tidal_artist) != artist_identity(artist)
            or norm(tidal_title) not in {norm(title), norm(expected_core)}):
        raise RuntimeError(
            f"TIDAL override {track_id} metadata differs from "
            f"{artist} - {title}: {tidal_artist} - {tidal_title}")
    return track


MATCH_FIELDS = ["artist", "title", "tidal_artist", "tidal_title", "tidal_id",
                "confidence", "status", "decision"]


def protect_playlist_artwork(name: str, dry_run: bool) -> None:
    """Do not change the identity or custom cover of the curated playlist."""
    if name == "Down with the Kids" and not dry_run:
        raise RuntimeError(
            "ARTWORK PROTECTION: Down with the Kids publishing is temporarily "
            "disabled until verified in-place updating is available. "
            "No playlist was changed.")


def cmd_push(args) -> None:
    protect_playlist_artwork(args.name, args.dry_run)
    approved = dedupe_tracks(read_csv(APPROVED))
    if not approved:
        sys.exit(f"{APPROVED} is missing or empty - run sweep, review, apply first")
    try:
        import tidalapi
    except ImportError:
        sys.exit("pip install tidalapi")
    session = tidalapi.Session()
    if not session.login_session_file(SESSION_FILE):
        sys.exit("TIDAL login failed")
    previous = {(r.get("artist"), r.get("title"), r.get("tidal_id")): r.get("decision", "")
                for r in read_csv(MATCH_REPORT)}
    report, matched, diagnostics = [], [], []
    seen_ids = set()
    for r in approved:
        artist, title = r["artist"], r["title"]
        try:
            override = verified_tidal_override(session, artist, title)
            if override is not None:
                t, score = override, 1.0
                print(f"Verified explicit TIDAL track override: {artist} - {title} -> {t.id}")
            else:
                t, score, candidates, source = find_track_diagnostic(
                    session, tidalapi, artist, title, r.get("isrc", ""))
                diagnostics.extend(candidates)
        except Exception as exc:
            t, score = None, 0.0
            print(f"match error for {artist} - {title}: {exc}", file=sys.stderr)
        tidal_id = str(t.id) if t else ""
        duplicate = bool(tidal_id and tidal_id in seen_ids)
        if tidal_id:
            seen_ids.add(tidal_id)
        status = ("unmatched" if not t else "duplicate" if duplicate else
                  "review" if score < 0.98 else "matched")
        decision = previous.get((artist, title, tidal_id), "")
        if decision not in ("", "approve", "reject"):
            decision = ""
        report.append({"artist": artist, "title": title,
                       "tidal_artist": t.artist.name if t else "",
                       "tidal_title": t.name if t else "",
                       "tidal_id": tidal_id, "confidence": f"{score:.2f}",
                       "status": status, "decision": decision})
        if t and not duplicate and decision != "reject":
            matched.append((t, status, decision))
    write_csv(MATCH_REPORT, MATCH_FIELDS, report)
    write_csv(MATCH_CANDIDATES, CANDIDATE_FIELDS, diagnostics)
    print(f"diagnostic candidates: {MATCH_CANDIDATES}")
    unresolved = [r for r in report if r["status"] in ("unmatched", "duplicate") or
                  r["decision"] == "reject" or
                  (r["status"] == "review" and r["decision"] != "approve")]
    for row in unresolved:
        print(f"UNRESOLVED: {row['artist']} - {row['title']} "
              f"[{row['status']}; decision={row['decision'] or '(none)'}]", flush=True)
    print(f"matched {sum(bool(r['tidal_id']) for r in report)}/{len(approved)}; "
          f"{len(unresolved)} unresolved; report: {MATCH_REPORT}")
    if args.dry_run:
        print("DRY RUN: no TIDAL playlist changes")
        return
    if unresolved and not args.allow_partial:
        sys.exit("Push blocked: unresolved or unapproved matches. Review match_report.csv "
                 "and rerun, or explicitly choose --allow-partial.")
    selected = [t for t, status, decision in matched
                if status == "matched" or (status == "review" and decision == "approve")]
    if not selected:
        sys.exit("No approved TIDAL matches to push")
    if args.expected_ids_file:
        if not args.replace or args.allow_partial or args.dry_run:
            raise RuntimeError("Locked match plan requires a full replacement push")
        expected = json.loads(Path(args.expected_ids_file).read_text(encoding="utf-8"))
        if (not isinstance(expected, list) or not expected or
                any(not isinstance(x, str) or not x for x in expected) or
                len(expected) != len(set(expected))):
            raise RuntimeError("Invalid locked TIDAL match plan")
        actual = [str(t.id) for t in selected]
        if actual != expected:
            raise RuntimeError("TIDAL match results changed since dry run; no playlist created")
    # Never delete the original until the replacement has been populated and verified.
    existing = [p for p in session.user.playlists() if p.name == args.name] if args.replace else []
    ids = [str(t.id) for t in selected]
    pl = session.user.create_playlist(args.name, f"Auto-curated {date.today():%d %b %Y}")
    try:
        for i in range(0, len(ids), 50):
            pl.add(ids[i:i + 50])
        verify_playlist_tracks(pl, ids)
    except Exception as exc:
        # Preserve the new playlist for inspection/recovery; do not delete originals.
        sys.exit(f"Replacement was not verified ({exc}). Existing playlists were "
                 f"preserved. Inspect the new playlist in TIDAL before retrying.")
    if existing:
        for old in existing:
            try:
                old.delete()
            except Exception as exc:
                sys.exit(f"New playlist verified, but an old playlist could not be "
                         f"deleted ({exc}). Both playlists may exist; review in TIDAL.")
    print(f"playlist '{args.name}' created and verified with {len(ids)} unique tracks")



def read_playlist_ids(playlist):
    ids = []
    for offset in range(0, 10000, 100):
        batch = playlist.tracks(limit=100, offset=offset)
        if not isinstance(batch, list):
            raise RuntimeError("TIDAL returned an unverifiable playlist page")
        ids.extend(str(track.id) for track in batch)
        if len(batch) < 100:
            return ids
    raise RuntimeError("Playlist exceeds safe 10,000-track limit")


def write_recovery_snapshot(playlist, original, proposed):
    """Persist the original ordering before any remote mutation."""
    import tempfile
    from datetime import datetime, timezone
    folder = DATA / "playlist_recovery"
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = {"playlist_id": str(playlist.id), "playlist_name": playlist.name,
                "original_ids": original, "proposed_ids": proposed,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending"}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=folder,
                                     prefix=".snapshot-", suffix=".tmp",
                                     delete=False) as handle:
        tmp = Path(handle.name)
        json.dump(snapshot, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    path = folder / ("playlist-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    os.replace(tmp, path)
    return path


def update_playlist_in_place(playlist, original, proposed):
    """Append ordered prefixes; otherwise remove, move, and add tracks directly.

    The existing playlist object (and its cover/URL) is never deleted.
    A failed step leaves the snapshot available for supervised recovery.
    """
    if not original or not proposed or len(proposed) != len(set(proposed)):
        raise RuntimeError("Refusing empty baseline, empty proposal or duplicate IDs")
    if read_playlist_ids(playlist) != original:
        raise RuntimeError("Live playlist changed before update; no mutation made")
    snapshot = write_recovery_snapshot(playlist, original, proposed)
    print(f"RECOVERY SNAPSHOT: {snapshot}", flush=True)
    if original == proposed:
        print("Playlist already matches; no changes needed")
        return snapshot
    if proposed[:len(original)] == original:
        # Strict ordered-prefix case: retain every existing entry and append only
        # the missing tail. Never invoke positional removal for this path.
        tail = proposed[len(original):]
        try:
            for i in range(0, len(tail), 50):
                playlist.add(tail[i:i + 50])
                expected = original + tail[:i + 50]
                if read_playlist_ids(playlist) != expected:
                    raise RuntimeError("Unexpected playlist order after append-only update")
            verify_playlist_tracks(playlist, proposed)
        except Exception as exc:
            raise RuntimeError(
                f"APPEND-ONLY UPDATE INCOMPLETE: {exc}. Playlist {playlist.id} was "
                f"NOT deleted. Inspect TIDAL and recovery snapshot {snapshot} "
                "before any retry; automatic rollback is disabled.") from exc
        print(f"Append-only update verified: +{len(tail)} tracks; playlist ID {playlist.id}")
        return snapshot
    try:
        # First remove obsolete entries from right to left, so indices remain stable.
        current = original.copy()
        desired = set(proposed)
        for index in range(len(current) - 1, -1, -1):
            if current[index] not in desired:
                expected = current[:index] + current[index + 1:]
                if playlist.remove_by_index(index) is False:
                    raise RuntimeError(f"Removal returned False at index {index}")
                actual = read_playlist_ids(playlist)
                if actual != expected:
                    raise RuntimeError(f"Unexpected order after removal at {index}")
                current = actual
        # Reorder retained tracks using positional moves, checking each result.
        for position, track_id in enumerate(proposed):
            if track_id not in current:
                continue
            source = current.index(track_id)
            if source == position:
                continue
            expected = current.copy()
            expected.insert(position, expected.pop(source))
            if playlist.move_by_index(source, position) is False:
                raise RuntimeError(f"Move returned False at {source}->{position}")
            actual = read_playlist_ids(playlist)
            if actual != expected:
                raise RuntimeError(f"Unexpected order after move {source}->{position}")
            current = actual
        # Only new IDs are appended; never rely on duplicate additions.
        missing = [track_id for track_id in proposed if track_id not in current]
        for i in range(0, len(missing), 50):
            batch = missing[i:i + 50]
            expected = current + batch
            if playlist.add(batch) is False:
                raise RuntimeError("Addition returned False")
            actual = read_playlist_ids(playlist)
            if actual != expected:
                raise RuntimeError("Unexpected order after adding new tracks")
            current = actual
        # Position newly appended tracks in their final locations.
        for position, track_id in enumerate(proposed):
            source = current.index(track_id)
            if source == position:
                continue
            expected = current.copy()
            expected.insert(position, expected.pop(source))
            if playlist.move_by_index(source, position) is False:
                raise RuntimeError(f"Move returned False at {source}->{position}")
            actual = read_playlist_ids(playlist)
            if actual != expected:
                raise RuntimeError(f"Unexpected order after final move {source}->{position}")
            current = actual
        verify_playlist_tracks(playlist, proposed)
    except Exception as exc:
        raise RuntimeError(
            f"IN-PLACE UPDATE INCOMPLETE: {exc}. Playlist {playlist.id} was NOT "
            f"deleted. Inspect TIDAL and recovery snapshot {snapshot} before "
            "any retry; automatic rollback is intentionally disabled.") from exc
    print(f"In-place update verified: {len(proposed)} tracks; playlist ID {playlist.id}")
    return snapshot


def cmd_update_in_place(args):
    """Explicit supervised update using a locked, reviewed match report."""
    import tidalapi
    report = read_csv(MATCH_REPORT)
    if not report or any(row.get("status") != "matched" or row.get("decision") == "reject"
                         for row in report):
        raise RuntimeError("Require a clean, fully matched dry-run report")
    proposed = [str(row["tidal_id"]) for row in report]
    if len(proposed) < 20 or len(set(proposed)) != len(proposed):
        raise RuntimeError("Require at least 20 distinct TIDAL tracks")
    session = tidalapi.Session()
    if not session.login_session_file(SESSION_FILE):
        raise RuntimeError("TIDAL login failed")
    matches = [p for p in session.user.playlists() if p.name == "Down with the Kids"]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one owned Down with the Kids playlist")
    playlist = matches[0]
    if str(playlist.id) != "ac2a24f5-a386-40cb-a637-ad9f89f32622":
        raise RuntimeError("Protected playlist ID mismatch; refusing any update")
    original = read_playlist_ids(playlist)
    if not original:
        raise RuntimeError("Existing playlist is empty; refusing update")
    if args.expected_ids_file:
        expected = json.loads(Path(args.expected_ids_file).read_text(encoding="utf-8"))
        if expected != proposed:
            raise RuntimeError("Locked proposed IDs differ from match report")
    if args.expected_baseline_file:
        baseline = json.loads(Path(args.expected_baseline_file).read_text(encoding="utf-8"))
        if baseline != original:
            raise RuntimeError("Live playlist differs from locked baseline")
    print(f"Existing playlist {playlist.id}: {len(original)} tracks; proposed: {len(proposed)}")
    print(f"Changes: +{len(set(proposed)-set(original))}, -{len(set(original)-set(proposed))}")
    print("Update strategy: " + ("append-only (no removals)" if proposed[:len(original)] == original
                                  else "direct positional edits (remove, move and add)"))
    print("Add IDs:", [track for track in proposed if track not in set(original)])
    print("Remove IDs:", [track for track in original if track not in set(proposed)])
    print("Reordering required:", [track for track in original if track in set(proposed)]
          != [track for track in proposed if track in set(original)])
    if args.append_only and proposed[:len(original)] != original:
        raise RuntimeError("APPEND-ONLY REQUIRED: existing tracks are not an ordered prefix; no changes made")
    if not args.commit:
        print("PREVIEW ONLY: no playlist changes; use --commit after reviewing.")
        return
    if not args.expected_ids_file or not args.expected_baseline_file:
        raise RuntimeError("Commit requires both locked proposed IDs and baseline files")
    update_playlist_in_place(playlist, original, proposed)


def cmd_promote(args) -> None:
    """Copy a confident match to an existing permanent Zeitgeist playlist."""
    matches = [r for r in read_csv(MATCH_REPORT)
               if r.get("tidal_id") == args.tidal_id and r.get("status") == "matched"]
    if len(matches) != 1:
        raise RuntimeError("Track must have exactly one confident match in the current report")
    import tidalapi
    session = tidalapi.Session()
    if not session.login_session_file(SESSION_FILE):
        raise RuntimeError("TIDAL login failed")
    all_playlists = list(session.user.playlists())
    playlists = [p for p in all_playlists if p.name.strip().casefold() == "zeitgeist"]
    if len(playlists) != 1:
        names = ", ".join(repr(p.name) for p in all_playlists)
        raise RuntimeError(
            f"Expected exactly one owned Zeitgeist playlist; found {len(playlists)}. "
            f"Playlists visible to this TIDAL session: {names or '(none)'}. "
            "If Zeitgeist is a followed playlist rather than one you own, "
            "it cannot be modified using this account's owned-playlist list.")
    playlist = playlists[0]
    existing = []
    for offset in range(0, 10000, 100):
        batch = playlist.tracks(limit=100, offset=offset)
        if not isinstance(batch, list):
            raise RuntimeError("Could not verify Zeitgeist tracks")
        existing.extend(str(t.id) for t in batch)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError("Zeitgeist exceeds safe read limit")
    if args.tidal_id in existing:
        print("Already in Zeitgeist; nothing changed")
        return
    playlist.add([args.tidal_id])
    verify_playlist_tracks(playlist, existing + [args.tidal_id])
    print("Promoted " + matches[0]["artist"] + " - " + matches[0]["title"] + " to Zeitgeist")


def verify_playlist_tracks(playlist, expected_ids: list[str]) -> None:
    """Fail closed: only permit replacement after verifying the complete ordered track list."""
    actual = []
    for offset in range(0, len(expected_ids), 100):
        batch = playlist.tracks(limit=min(100, len(expected_ids) - offset), offset=offset)
        if not isinstance(batch, list):
            raise RuntimeError("TIDAL did not return a verifiable track list")
        actual.extend(str(t.id) for t in batch)
    if actual != expected_ids:
        raise RuntimeError(f"playlist contents differ (expected {len(expected_ids)} tracks, "
                           f"read back {len(actual)})")
    # Also check that no unexpected tracks exist after the expected final track.
    extra = playlist.tracks(limit=1, offset=len(expected_ids))
    if not isinstance(extra, list) or extra:
        raise RuntimeError("playlist has extra tracks or could not be fully verified")


# -------------------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sweep", help="fetch + score -> data/review.csv")
    s.add_argument("--country", default="gb")
    s.add_argument("--apple-depth", type=int, default=100)
    s.add_argument("--review-size", type=int, default=80, help="candidates to review (more than the playlist size so removals backfill)")
    s.add_argument("--tokchart", action="store_true", help="opt-in scrape of Tokchart's public UK page")
    s.add_argument("--max-tiktok-only", type=int, default=5)
    s.add_argument("--require-two", action="store_true", help="drop songs seen by only one market source (seeds exempt)")
    s.add_argument("--official-chart", action="store_true", help="attempt permitted public Official Singles Chart retrieval")
    s.add_argument("--spotify-mirror", action="store_true", help="use public Kworb UK Spotify chart mirror (no Spotify account)")
    s.add_argument("--musicbrainz", action="store_true", help="cross-check release dates with free MusicBrainz API")
    s.add_argument("--release-years", type=int, default=3, help="maximum release age in calendar years")
    s.add_argument("--allow-revivals", action=argparse.BooleanOptionalAction, default=True,
                   help="permit older tracks supported by at least two current trend sources")
    s.set_defaults(fn=cmd_sweep)

    a = sub.add_parser("apply", help="save blocks from review.csv, write approved.csv")
    a.add_argument("--size", type=int, default=50, help="playlist length")
    a.add_argument("--max-revivals", type=int, default=5, help="maximum older revival tracks in approved playlist")
    a.set_defaults(fn=cmd_apply)

    for name, fn in (("block", cmd_block), ("unblock", cmd_unblock)):
        b = sub.add_parser(name)
        b.add_argument("--artist")
        b.add_argument("--song", nargs=2, metavar=("ARTIST", "TITLE"))
        b.add_argument("--reason", default="")
        b.set_defaults(fn=fn)
    sub.add_parser("blocklist", help="list blocked songs/artists").set_defaults(fn=cmd_blocklist)

    u = sub.add_parser("push", help="match on TIDAL and create the playlist")
    u.add_argument("--name", default="UK Trends")
    u.add_argument("--replace", action="store_true", help="verify a new playlist before deleting existing playlists of the same name")
    u.add_argument("--dry-run", action="store_true", help="only write the match report")
    u.add_argument("--expected-ids-file", help="fail unless selected IDs exactly match a locked JSON dry-run plan")
    u.add_argument("--allow-partial", action="store_true", help="explicitly permit a shorter playlist, excluding unresolved matches")
    u.set_defaults(fn=cmd_push)

    inplace = sub.add_parser("update-in-place", help="supervised, artwork-preserving update")
    inplace.add_argument("--commit", action="store_true", help="explicitly authorize live changes")
    inplace.add_argument("--append-only", action="store_true", help="refuse removals or reordering")
    inplace.add_argument("--expected-ids-file", help="JSON list of locked proposed TIDAL IDs")
    inplace.add_argument("--expected-baseline-file", help="JSON list of existing TIDAL IDs")
    inplace.set_defaults(fn=cmd_update_in_place)

    z = sub.add_parser("promote", help="copy a confident TIDAL match to Zeitgeist")
    z.add_argument("--tidal-id", required=True)
    z.set_defaults(fn=cmd_promote)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
