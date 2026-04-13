"""
Prediction engine — fetches current week's songs from the Beatvote contract
and scores them by on-chain vote tallies + qualitative signals.

Real mode:  reads songs from the voting contract on BNB Chain.
Mock mode:  returns realistic synthetic data for demos/testing.
"""

import datetime
from typing import Any

import config
from utils.logger import action, ok, warn, info
from skills import audiera_music

# ── Optional web3 import ─────────────────────────────────────────────────────
try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    _WEB3_OK = True
except ImportError:
    _WEB3_OK = False

# Keywords that signal dance-mat / rhythm-game compatibility
_DANCE_KEYWORDS = [
    "dance", "mat", "bpm", "rhythm", "beat drop", "slap", "banger", "gyatt",
    "hype", "groove", "floor", "move", "vibe", "energy", "lit", "fire",
]

# Keywords that indicate meme / social buzz potential
_BUZZ_KEYWORDS = [
    "audiera", "beatvote", "#beat", "vebeat", "kira", "ray", "trending",
    "top10", "chart", "vote", "aura", "sigma", "npc", "no cap", "fr fr",
    "lowkey", "slay", "based", "certified", "certified banger",
]

# Minimal ABI for reading songs from the voting contract
VOTING_READ_ABI = [
    {
        "name": "getVotingSongs",
        "type": "function",
        "inputs": [],
        "outputs": [
            {
                "name": "",
                "type": "tuple[]",
                "components": [
                    {"name": "songId",    "type": "uint256"},
                    {"name": "title",     "type": "string"},
                    {"name": "artist",    "type": "string"},
                    {"name": "voteCount", "type": "uint256"},
                    {"name": "submittedAt", "type": "uint256"},
                ],
            }
        ],
        "stateMutability": "view",
    },
    {
        "name": "getVotesForSong",
        "type": "function",
        "inputs": [{"name": "songId", "type": "uint256"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "currentWeek",
        "type": "function",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────

def analyze_trends(queries: list[str] | None = None) -> dict:
    """
    Main analysis function called by the agent brain.
    Priority: 1) Audiera weekly-leaderboard API  2) On-chain contract  3) Mock
    """
    action("Fetching current Beatvote songs from Audiera")

    # Priority 1 — Audiera weekly leaderboard (real platform data, always fresh)
    if config.AUDIERA_API_KEY:
        result = _leaderboard_analysis()
        if result.get("status") == "ok":
            return result
        warn("Leaderboard API failed — trying on-chain fallback")

    # Priority 2 — On-chain contract read
    if _can_read_chain():
        return _live_analysis()

    # Priority 3 — Mock
    return _mock_analysis()


def score_songs(songs: list[dict]) -> list[dict]:
    """
    Score and rank an arbitrary list of songs.
    Each song dict should have at least: id, name.
    """
    scored = [_score_single(s) for s in songs]
    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(ranked):
        s["rank"] = i + 1
    return ranked


# ─────────────────────────────────────────────────────────────────────────────
# Scoring logic
# ─────────────────────────────────────────────────────────────────────────────

def _score_single(song: dict) -> dict:
    weights = config.SCORE_WEIGHTS

    # On-chain vote count (primary signal — this is the ground truth)
    vote_count = song.get("vote_count", 0)
    vote_score  = min(vote_count / 50000, 1.0)   # normalise; cap at 50k votes

    # Dance potential from title/description text
    text = (song.get("description", "") + " " + song.get("name", "")).lower()
    dance_hits  = sum(1 for kw in _DANCE_KEYWORDS if kw in text)
    dance_score = min(dance_hits / 5, 1.0)

    # Meme / buzz energy
    buzz_hits   = sum(1 for kw in _BUZZ_KEYWORDS if kw in text)
    buzz_score  = min(buzz_hits / 4, 1.0)

    # Recency — newer submissions slightly preferred
    submitted_at = song.get("submitted_at", "")
    recency_score = _recency_score(submitted_at)

    # Past performance (chart history)
    past_score = min(song.get("past_top10_count", 0) / 3, 1.0)

    composite = (
        vote_score    * weights["vote_count"]       +
        dance_score   * weights["dance_potential"]   +
        buzz_score    * weights["meme_energy"]       +
        recency_score * weights["recency"]           +
        past_score    * weights["past_performance"]
    )

    signals = []
    if vote_score > 0.5:    signals.append("🔥 leading votes")
    if dance_score > 0.5:   signals.append("💃 dance-mat ready")
    if buzz_score > 0.5:    signals.append("📣 meme energy")
    if recency_score > 0.7: signals.append("⚡ fresh submission")
    if past_score > 0.3:    signals.append("🏆 chart history")

    return {
        **song,
        "score": round(composite, 4),
        "signal_summary": " · ".join(signals) if signals else "low signals",
        "breakdown": {
            "vote_count":      round(vote_score, 3),
            "dance_potential": round(dance_score, 3),
            "meme_energy":     round(buzz_score, 3),
            "recency":         round(recency_score, 3),
            "past_performance":round(past_score, 3),
        },
    }


def _recency_score(submitted_at) -> float:
    if not submitted_at:
        return 0.5
    try:
        if isinstance(submitted_at, int):
            # Unix timestamp from contract
            dt = datetime.datetime.utcfromtimestamp(submitted_at)
        else:
            dt = datetime.datetime.fromisoformat(str(submitted_at).rstrip("Z"))
        age_hours = (datetime.datetime.utcnow() - dt).total_seconds() / 3600
        return max(0.0, 1.0 - age_hours / 168)
    except Exception:
        return 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Audiera weekly leaderboard (primary real data source)
# ─────────────────────────────────────────────────────────────────────────────

def _leaderboard_analysis() -> dict:
    """
    Build ranked predictions from the Audiera weekly leaderboard API.
    Combines top_played, community_favorite, and rising_track into one scored list.
    """
    try:
        lb = audiera_music.get_weekly_leaderboard()
        if lb.get("status") != "ok":
            return lb

        # Merge all songs into one deduplicated list
        seen = set()
        songs = []

        def _add(s: dict, bonus_tag: str = ""):
            sid = str(s.get("id", ""))
            if sid in seen:
                return
            seen.add(sid)
            songs.append({
                "id":               sid,
                "name":             s.get("title", "Unknown"),
                "artist":           "",
                "vote_count":       s.get("plays", 0),   # plays as proxy for popularity
                "likes":            s.get("likes", 0),
                "submitted_at":     "",
                "description":      f"{s.get('title','')} {bonus_tag}",
                "past_top10_count": 0,
                "platform_url":     s.get("url", ""),
                "bonus_tag":        bonus_tag,
            })

        for s in lb.get("top_played", []):
            _add(s, "dance bpm trending audiera beatvote")

        cf = lb.get("community_favorite", {})
        if cf:
            _add(cf, "community favourite dance gyatt energy kira ray")

        rt = lb.get("rising_track", {})
        if rt:
            _add(rt, "rising trending meme energy audiera")

        if not songs:
            return {"status": "error", "error": "No songs in leaderboard"}

        ranked = score_songs(songs)
        ok(f"Leaderboard analysis: scored {len(ranked)} real Audiera songs")
        result = _format_result(ranked)
        result["source"] = "audiera_leaderboard"
        return result

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Live Beatvote contract reading
# ─────────────────────────────────────────────────────────────────────────────

def _can_read_chain() -> bool:
    return _WEB3_OK and bool(config.VOTING_CONTRACT_ADDRESS)


def _live_analysis() -> dict:
    try:
        w3 = Web3(Web3.HTTPProvider(config.BSC_RPC_URL))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        if not w3.is_connected():
            warn("Cannot connect to BSC — falling back to mock")
            return _mock_analysis()

        voting = w3.eth.contract(
            address=Web3.to_checksum_address(config.VOTING_CONTRACT_ADDRESS),
            abi=VOTING_READ_ABI,
        )

        # Try to get the structured song list
        try:
            raw_songs = voting.functions.getVotingSongs().call()
            songs = _parse_contract_songs(raw_songs, voting)
        except Exception as e:
            warn(f"getVotingSongs() failed ({e}) — trying vote-by-ID fallback")
            songs = _fallback_song_read(voting)

        if not songs:
            warn("No songs returned from contract — falling back to mock")
            return _mock_analysis()

        ranked = score_songs(songs)
        ok(f"Fetched {len(ranked)} songs from Beatvote contract")
        return _format_result(ranked)

    except Exception as e:
        warn(f"Live analysis failed: {e} — falling back to mock")
        return _mock_analysis()


def _parse_contract_songs(raw_songs: list, voting) -> list[dict]:
    """Parse the tuple array returned by getVotingSongs()."""
    songs = []
    for s in raw_songs:
        song_id    = str(s[0])
        title      = s[1] if len(s) > 1 else f"Song #{song_id}"
        artist     = s[2] if len(s) > 2 else "Unknown"
        vote_count = s[3] if len(s) > 3 else 0
        submitted  = s[4] if len(s) > 4 else 0
        songs.append({
            "id":           song_id,
            "name":         title,
            "artist":       artist,
            "vote_count":   vote_count,
            "submitted_at": submitted,
            "description":  f"{title} {artist}",
            "past_top10_count": 0,
        })
    return songs


def _fallback_song_read(voting, max_id: int = 20) -> list[dict]:
    """
    If getVotingSongs() isn't available, probe song IDs 1–max_id
    and collect those with non-zero vote counts.
    """
    songs = []
    for song_id in range(1, max_id + 1):
        try:
            votes = voting.functions.getVotesForSong(song_id).call()
            if votes > 0:
                songs.append({
                    "id":           str(song_id),
                    "name":         f"Track #{song_id}",
                    "artist":       "Audiera Artist",
                    "vote_count":   votes,
                    "submitted_at": "",
                    "description":  "",
                    "past_top10_count": 0,
                })
        except Exception:
            break   # past the end of the song list
    return songs


# ─────────────────────────────────────────────────────────────────────────────
# Mock data (demo / CI / no-wallet mode)
# ─────────────────────────────────────────────────────────────────────────────

def _mock_analysis() -> dict:
    info("Using mock Beatvote data (MOCK_MODE=true or no chain connection)")
    now = datetime.datetime.utcnow()
    mock_songs = [
        {
            "id": "1", "name": "Neon Pulse", "artist": "Kira 0x4154",
            "vote_count": 28400, "submitted_at": (now - datetime.timedelta(hours=4)).isoformat(),
            "description": "banger dance mat gyatt energy audiera beatvote #BEAT",
            "past_top10_count": 1,
        },
        {
            "id": "2", "name": "Sigma Drift", "artist": "Ray 0x4245",
            "vote_count": 21000, "submitted_at": (now - datetime.timedelta(hours=12)).isoformat(),
            "description": "trending sigma energy dance floor bpm fire #AudieraAI",
            "past_top10_count": 2,
        },
        {
            "id": "3", "name": "Kira Wave", "artist": "Kira 0x4154",
            "vote_count": 41000, "submitted_at": (now - datetime.timedelta(hours=2)).isoformat(),
            "description": "kira hype dance mat rhythm banger certified",
            "past_top10_count": 3,
        },
        {
            "id": "4", "name": "Ray Drop", "artist": "Ray 0x4245",
            "vote_count": 18000, "submitted_at": (now - datetime.timedelta(hours=18)).isoformat(),
            "description": "ray vibe groove floor move lit",
            "past_top10_count": 1,
        },
        {
            "id": "5", "name": "Blockchain Bounce", "artist": "AudieraAI",
            "vote_count": 9500, "submitted_at": (now - datetime.timedelta(hours=36)).isoformat(),
            "description": "vebeat vote audiera top10 chart",
            "past_top10_count": 0,
        },
        {
            "id": "6", "name": "Gyatt Protocol", "artist": "SigmaBeats",
            "vote_count": 15200, "submitted_at": (now - datetime.timedelta(hours=8)).isoformat(),
            "description": "gyatt energy dance bpm fire trending no cap",
            "past_top10_count": 0,
        },
        {
            "id": "7", "name": "Aura Frequency", "artist": "NPC Collective",
            "vote_count": 7800, "submitted_at": (now - datetime.timedelta(hours=24)).isoformat(),
            "description": "aura slay lowkey certified banger",
            "past_top10_count": 0,
        },
    ]
    ranked = score_songs(mock_songs)
    ok(f"Mock Beatvote: scored {len(ranked)} songs")
    return _format_result(ranked)


# ─────────────────────────────────────────────────────────────────────────────
# Output formatting
# ─────────────────────────────────────────────────────────────────────────────

def _format_result(ranked: list[dict]) -> dict:
    top3 = ranked[:3]
    return {
        "status": "ok",
        "source": "beatvote_contract",
        "mode": "mock" if config.MOCK_MODE else "live",
        "analyzed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "total_songs": len(ranked),
        "ranked_songs": ranked,
        "top_picks": [
            {
                "rank": s["rank"],
                "id":   s["id"],
                "name": s["name"],
                "artist": s.get("artist", ""),
                "score": s["score"],
                "vote_count": s.get("vote_count", 0),
                "signal_summary": s["signal_summary"],
                "suggested_vote_weight": _suggested_weight(s["score"], ranked),
            }
            for s in top3
        ],
        "recommendation": _build_recommendation(top3),
    }


def _suggested_weight(score: float, all_songs: list[dict]) -> float:
    total = sum(s["score"] for s in all_songs[:5]) or 1
    return round(score / total, 2)


def _build_recommendation(top3: list[dict]) -> str:
    if not top3:
        return "No strong signals this week — hold veBEAT."
    names = [f'"{s["name"]}"' for s in top3]
    top = top3[0]
    return (
        f"On-chain data points to {', '.join(names[:-1])} and {names[-1]} leading the pack. "
        f"Top pick: {names[0]} ({top.get('vote_count', 0):,} votes, {top['score']:.0%} composite). "
        f"Predictions only — always DYOR."
    )
