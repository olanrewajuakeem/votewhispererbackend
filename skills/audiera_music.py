"""
Audiera Music & Lyrics Skills — contest-required integrations.

Endpoints:
  POST https://ai.audiera.fi/api/skills/music   → generate a full song
  POST https://ai.audiera.fi/api/skills/lyrics  → generate lyrics

Real mode:  calls Audiera API with AUDIERA_API_KEY.
Mock mode:  returns realistic synthetic responses.
"""

import time
import datetime
import requests
from typing import Any

import config
from utils.logger import action, ok, warn, info, err

_BASE = config.AUDIERA_API_BASE   # https://ai.audiera.fi/api

VALID_STYLES = [
    "Pop", "Rock", "Hip-Hop", "Country", "Dance", "Electronic", "Disco",
    "Blues", "Jazz", "Folk", "Latin", "Metal", "Punk", "R&B", "Soul",
    "Funk", "Reggae", "Indie", "Afrobeat", "Classical", "World-music",
]


# ─────────────────────────────────────────────────────────────────────────────
# Lyrics generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_lyrics(theme: str, styles: list[str] | None = None) -> dict:
    """
    Generate song lyrics from a theme or inspiration.
    Returns: {status, lyrics, theme, styles, generated_at}
    """
    action(f"Generating lyrics for theme: {theme[:50]}")
    styles = _validate_styles(styles or ["Pop", "Electronic"])

    if not config.AUDIERA_API_KEY:
        return _mock_lyrics(theme, styles)

    try:
        # Audiera API uses "inspiration" field, not "theme"
        resp = requests.post(
            f"{_BASE}/skills/lyrics",
            headers={"Authorization": f"Bearer {config.AUDIERA_API_KEY}",
                     "Content-Type": "application/json"},
            json={"inspiration": theme, "styles": styles},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        lyrics_text = data.get("data", {}).get("lyrics") or data.get("lyrics", "")
        ok(f"Lyrics generated ({len(lyrics_text)} chars)")
        return {
            "status":       "ok",
            "lyrics":       lyrics_text,
            "theme":        theme,
            "styles":       styles,
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        err(f"Lyrics generation failed: {e}")
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Music generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_music(
    styles: list[str] | None = None,
    artist_id: str = "default",
    lyrics: str | None = None,
    inspiration: str | None = None,
    poll_timeout: int = 120,
) -> dict:
    """
    Generate a full song with vocals.
    Either lyrics or inspiration must be provided.

    Returns: {status, song_id, title, url, file_url, duration, generated_at}
    """
    if not lyrics and not inspiration:
        inspiration = "An energetic dance track for Audiera Beatvote"

    styles = _validate_styles(styles or ["Dance", "Electronic"])
    action(f"Generating music — styles: {styles}")

    if not config.AUDIERA_API_KEY:
        return _mock_music(styles, lyrics or inspiration)

    # Use AUDIERA_ARTIST_ID from env if not passed explicitly
    if artist_id == "default":
        artist_id = config.AUDIERA_ARTIST_ID or "default"

    try:
        payload: dict[str, Any] = {"styles": styles, "artistId": artist_id}
        if lyrics:
            payload["lyrics"] = lyrics
        if inspiration:
            payload["inspiration"] = inspiration

        resp = requests.post(
            f"{_BASE}/skills/music",
            headers={"Authorization": f"Bearer {config.AUDIERA_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        # Artist not found = fall back to mock gracefully
        if resp.status_code == 404 and "Artist not found" in resp.text:
            warn("Artist ID not configured — falling back to mock music. Set AUDIERA_ARTIST_ID in .env")
            return _mock_music(styles, lyrics or inspiration)
        resp.raise_for_status()
        task = resp.json()
        task_id  = task.get("taskId") or task.get("data", {}).get("taskId")
        raw_poll = task.get("pollUrl") or task.get("data", {}).get("pollUrl", "")
        # pollUrl from Audiera is relative (/api/skills/music/ID) — make it absolute
        if raw_poll.startswith("/"):
            poll_url = f"https://ai.audiera.fi{raw_poll}"
        elif raw_poll:
            poll_url = raw_poll
        else:
            poll_url = f"{_BASE}/skills/music/{task_id}"

        if not task_id:
            return {"status": "error", "error": "No taskId in response"}

        info(f"Music task created: {task_id} — polling...")

        # Step 2 — poll for result
        return _poll_music_task(poll_url, poll_timeout)

    except Exception as e:
        err(f"Music generation failed: {e}")
        return {"status": "error", "error": str(e)}


def _poll_music_task(poll_url: str, timeout: int) -> dict:
    deadline = time.time() + timeout
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        try:
            resp = requests.get(
                poll_url,
                headers={"Authorization": f"Bearer {config.AUDIERA_API_KEY}"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status") or data.get("data", {}).get("status", "pending")
            if status == "completed":
                # May return data.music (single) or data.musics (array)
                music = data.get("data", {})
                song = music.get("music") or (music.get("musics") or [{}])[0] or music
                ok(f"Music ready after {attempts} polls: {song.get('title', 'untitled')}")
                return {
                    "status":       "ok",
                    "song_id":      song.get("id", ""),
                    "title":        song.get("title", "Untitled"),
                    "url":          song.get("url", ""),
                    "file_url":     song.get("fileUrl", ""),
                    "duration":     song.get("duration", 0),
                    "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
                }
            elif status in ("failed", "error"):
                return {"status": "error", "error": data.get("message", "Generation failed")}

        except Exception as e:
            warn(f"Poll attempt {attempts} failed: {e}")

        time.sleep(5)

    return {"status": "error", "error": f"Timed out after {timeout}s ({attempts} polls)"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate_styles(styles: list[str]) -> list[str]:
    valid = [s for s in styles if s in VALID_STYLES]
    if not valid:
        valid = ["Electronic"]
    return valid[:3]   # max 3 styles


# ─────────────────────────────────────────────────────────────────────────────
# Mock responses
# ─────────────────────────────────────────────────────────────────────────────

def _mock_lyrics(theme: str, styles: list[str]) -> dict:
    info("Mock lyrics generation (MOCK_MODE=true or no AUDIERA_API_KEY)")
    mock_lyrics = f"""[Verse 1]
Riding the chain where the music drops
veBEAT stacked high, nobody stops
Audiera lights on the BNB floor
Kira and Ray unlock every door

[Chorus]
Vote for the wave, claim your BEAT
Top 10 rising, feel the heat
Stack it, earn it, let it ride
VoteWhisperer by your side

[Verse 2]
Scanning the charts, the signals are clear
{theme[:40]} drops hard this year
Dance mat ready, the gyatt is real
Every on-chain vote is the deal

[Outro]
Predictions only — but trust the data
#AudieraAI #BEAT #BinanceAI
"""
    ok("Mock lyrics generated")
    return {
        "status":       "ok",
        "mode":         "mock",
        "lyrics":       mock_lyrics,
        "theme":        theme,
        "styles":       styles,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


def _mock_music(styles: list[str], inspiration: str) -> dict:
    info("Mock music generation (no AUDIERA_API_KEY or artist ID not set)")
    ok("Mock song generated: 'VoteWhisperer Anthem'")
    return {
        "status":       "ok",
        "mode":         "mock",
        "song_id":      "mock_song_001",
        "title":        "VoteWhisperer Anthem",
        "url":          "https://ai.audiera.fi/music/mock_001",
        "file_url":     "https://ai.audiera.fi/files/mock_001.mp3",
        "duration":     187,
        "styles":       styles,
        "inspiration":  inspiration,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Real-time Audiera platform data
# ─────────────────────────────────────────────────────────────────────────────

def get_weekly_leaderboard() -> dict:
    """
    Fetch this week's top songs, community favourite, and rising track
    directly from the Audiera API. Always live — no mock fallback needed,
    this endpoint requires only AUDIERA_API_KEY.
    """
    action("Fetching weekly leaderboard from Audiera")

    if not config.AUDIERA_API_KEY:
        return {"status": "error", "error": "AUDIERA_API_KEY not set"}

    try:
        r = requests.get(
            f"{_BASE}/skills/weekly-leaderboard",
            headers={"Authorization": f"Bearer {config.AUDIERA_API_KEY}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("data", {})

        top_played        = data.get("topPlayed", [])
        community_fav     = data.get("communityFavorite", {})
        rising            = data.get("risingTrack", {})

        ok(f"Leaderboard fetched — {len(top_played)} top played songs")
        return {
            "status":            "ok",
            "top_played":        top_played,       # [{id, title, plays, likes, url}]
            "community_favorite": community_fav,   # {id, title, plays, likes, url}
            "rising_track":      rising,           # {id, title, plays, likes, playsGrowth, url}
            "fetched_at":        datetime.datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        err(f"Leaderboard fetch failed: {e}")
        return {"status": "error", "error": str(e)}


def get_chain_stats() -> dict:
    """
    Fetch Audiera platform chain stats: total users, active users,
    NFT supply, BEAT burned this week + all time.
    """
    action("Fetching chain stats from Audiera")

    if not config.AUDIERA_API_KEY:
        return {"status": "error", "error": "AUDIERA_API_KEY not set"}

    try:
        r = requests.get(
            f"{_BASE}/skills/chain-stats",
            headers={"Authorization": f"Bearer {config.AUDIERA_API_KEY}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        ok(f"Chain stats: {data.get('totalUsers', 0):,} users, {data.get('lastWeekBurnedBeat', 0):,} BEAT burned this week")
        return {"status": "ok", **data}
    except Exception as e:
        err(f"Chain stats fetch failed: {e}")
        return {"status": "error", "error": str(e)}
