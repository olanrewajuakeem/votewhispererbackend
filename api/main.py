"""
VoteWhisperer — FastAPI Backend
Audiera Agent-Native Contest 2026

Run:
  uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

Docs:
  http://localhost:8000/docs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import config

limiter = Limiter(key_func=get_remote_address)
from agent import brain, state as agent_state
from skills import prediction, onchain, social, onboarding, audiera_music
from skills.audiera_music import get_weekly_leaderboard, get_chain_stats
from skills import wallet_session
from api.schemas import (
    ChatRequest, AnalyzeRequest, VoteRequest, StakeRequest,
    OnboardRequest, LyricsRequest, MusicRequest,
    AgentResponse, SongsResponse, StatusResponse,
)

app = FastAPI(
    title="VoteWhisperer API",
    description=(
        "Beatvote Strategist & Prediction Agent for Audiera. "
        "Create → Participate → Earn on BNB Chain."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Health / Status
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "agent":   "VoteWhisperer",
        "version": "1.0.0",
        "status":  "online",
        "mode":    "mock" if config.MOCK_MODE else "live",
        "docs":    "/docs",
    }


@app.get("/status", tags=["Health"])
def status():
    """Full agent + wallet status."""
    wallet = onchain.get_wallet_info()
    state  = agent_state.summary()
    s      = agent_state.load()

    # Last action — most recent vote, stake, or reward
    last_action = None
    votes   = s.get("votes_this_week", [])
    stakes  = s.get("stake_history", [])
    rewards = s.get("reward_history", [])
    if votes:
        v = votes[-1]
        last_action = {"type": "vote", "description": f"Voted for {v['song_name']}", "tx_hash": v["tx_hash"], "timestamp": v["timestamp"]}
    if stakes and (not last_action or stakes[-1]["timestamp"] > last_action["timestamp"]):
        k = stakes[-1]
        last_action = {"type": "stake", "description": f"Staked {k['amount']} BEAT", "tx_hash": k["tx_hash"], "timestamp": k["timestamp"]}
    if rewards and (not last_action or rewards[-1]["timestamp"] > last_action["timestamp"]):
        r = rewards[-1]
        last_action = {"type": "reward", "description": f"Claimed {r['amount']} BEAT rewards", "tx_hash": r["tx_hash"], "timestamp": r["timestamp"]}

    return {
        "agent":       config.AGENT_NAME,
        "mode":        "mock" if config.MOCK_MODE else "live",
        "transactions": "simulated",   # honest label — real wallet not configured yet
        "wallet":      wallet,
        "state":       state,
        "last_action": last_action,
        "contracts": {
            "beat_token": config.BEAT_TOKEN_ADDRESS,
            "voting":     config.VOTING_CONTRACT_ADDRESS,
            "staking":    config.STAKING_CONTRACT_ADDRESS,
        },
        "bscscan": {
            "voting_contract": f"https://bscscan.com/address/{config.VOTING_CONTRACT_ADDRESS}",
            "beat_token":      f"https://bscscan.com/token/{config.BEAT_TOKEN_ADDRESS}",
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Beatvote Data
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/songs", tags=["Beatvote"])
def get_songs():
    """Fetch this week's songs directly from the Beatvote contract."""
    result = onchain.get_voting_songs()
    return result


@app.post("/analyze", tags=["Beatvote"])
def analyze():
    """
    Fetch Beatvote songs + score + rank them.
    Returns full ranked prediction board with confidence scores.
    """
    result = prediction.analyze_trends()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Agent Actions (Claude-orchestrated)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/agent/analyze", tags=["Agent"])
@limiter.limit("10/minute")
def agent_analyze(request: Request):
    """Let Claude analyze Beatvote and give its picks in persona voice."""
    response = brain.run(
        "Fetch the current Beatvote songs from the contract. "
        "Score and rank them. Explain your top 3 picks in your VoteWhisperer voice — "
        "include the on-chain vote counts, confidence scores, and why each track has potential. "
        "End with a one-line prediction disclaimer."
    )
    return {"status": "ok", "response": response}


@app.post("/agent/vote", tags=["Agent"])
@limiter.limit("5/minute")
def agent_vote(request: Request, body: VoteRequest):
    """
    Full stake → analyze → vote → post cycle, orchestrated by Claude.
    Set auto=true to let Claude decide, or pass songs to override.
    """
    if body.auto:
        prompt = (
            "Run the full vote cycle:\n"
            "1. Check wallet balances.\n"
            "2. If veBEAT < 1000 and BEAT balance > 0, stake all available BEAT.\n"
            "3. Fetch current Beatvote songs from the leaderboard.\n"
            "4. Score and rank them.\n"
            "5. Cast votes on the top 3, allocating weight by confidence score.\n"
            "Narrate each step in your VoteWhisperer voice. Show the final vote allocation and tx hash."
        )
    else:
        votes_str = str(body.songs)
        prompt = (
            f"Cast votes on these specific songs: {votes_str}. "
            "Show the vote allocation and tx hash."
        )
    response = brain.run(prompt)
    return {"status": "ok", "response": response}


@app.post("/agent/earn", tags=["Agent"])
@limiter.limit("5/minute")
def agent_earn(request: Request):
    """Claim weekly rewards + restake 80%, orchestrated by Claude."""
    response = brain.run(
        "Claim my weekly voter rewards from the Beatvote reward pool. "
        "After claiming, restake 80% of the rewards to compound my veBEAT for next week. "
        "Tell me the net BEAT earned, the tx hash, and my updated wallet state."
    )
    return {"status": "ok", "response": response}


@app.post("/agent/loop", tags=["Agent"])
@limiter.limit("3/minute")
def agent_loop(request: Request):
    """Full weekly Create→Participate→Earn loop, orchestrated by Claude."""
    response = brain.run(
        "Run the full VoteWhisperer weekly loop. Do each step in order:\n\n"
        "STEP 1 — CREATE:\n"
        "  Generate lyrics for an Audiera dance track (theme: this week's Beatvote energy).\n"
        "  Then generate the full song using those lyrics.\n\n"
        "STEP 2 — ANALYZE:\n"
        "  Fetch current Beatvote songs from the contract.\n"
        "  Score and rank them. Share top 3 picks with confidence scores.\n\n"
        "STEP 3 — STAKE:\n"
        "  Check wallet. If veBEAT < 2000 and BEAT balance > 0, stake all available BEAT.\n\n"
        "STEP 4 — VOTE:\n"
        "  Cast votes on the top 3 songs, proportional to confidence scores.\n\n"
        "STEP 5 — SUMMARY:\n"
        "  Summarize your picks, vote allocations, and tx hash in your VoteWhisperer voice.\n\n"
        "STEP 6 — EARN:\n"
        "  Check and claim any pending rewards.\n\n"
        "STEP 7 — ONBOARD:\n"
        "  Give a Web2-friendly explanation of what you just did.\n\n"
        "Use your full VoteWhisperer voice. Disclaim predictions clearly."
    )
    return {"status": "ok", "response": response}


@app.post("/agent/chat", tags=["Agent"])
@limiter.limit("20/minute")
def agent_chat(request: Request, body: ChatRequest):
    """Chat with VoteWhisperer — ask anything about Beatvote strategy."""
    response = brain.run(body.message)
    return {"status": "ok", "response": response}


@app.post("/agent/onboard", tags=["Agent"])
def agent_onboard(body: OnboardRequest):
    """Run the Web2→Web3 onboarding guide."""
    response = brain.run(
        f"A new user at level '{body.level}' wants to learn how to participate in Audiera Beatvote. "
        "Run the full onboarding guide for them. "
        "Explain staking, veBEAT, voting, and earning in plain language. "
        "Mention the 2× first-time bonus and the weekly 5,000 BEAT reward pool."
    )
    return {"status": "ok", "response": response}


# ─────────────────────────────────────────────────────────────────────────────
# Direct Skill Calls (no Claude — fast, deterministic)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/connect", tags=["Wallet"])
def connect_wallet(body: dict):
    """
    Connect wallet. Two ways:
    1. MetaMask (recommended): send {"wallet_address": "0x..."}
    2. Audiera JWT (fallback):  send {"auth_token": "eyJ..."}
    Fetches live BNB/BEAT/veBEAT balances from BSC for the address.
    No private key needed — read-only.
    """
    wallet_address = body.get("wallet_address", "")
    auth_token     = body.get("auth_token", "")

    if wallet_address:
        return wallet_session.connect_address(wallet_address)
    elif auth_token:
        return wallet_session.connect(auth_token)
    else:
        raise HTTPException(status_code=400, detail="wallet_address or auth_token required")


@app.get("/session", tags=["Wallet"])
def get_session():
    """Get current connected wallet session."""
    session = wallet_session.get_session()
    if not session:
        return {"status": "disconnected", "wallet_address": None}
    return {"status": "connected", **session}


@app.post("/disconnect", tags=["Wallet"])
def disconnect_wallet():
    """Disconnect the current wallet session."""
    return wallet_session.disconnect()


@app.get("/wallet", tags=["Wallet"])
def wallet():
    """Fetch live wallet balances (uses connected session or env wallet)."""
    return onchain.get_wallet_info()


@app.post("/stake", tags=["Skills"])
def stake(body: StakeRequest):
    """Stake BEAT directly."""
    return onchain.stake_beat(body.amount)


@app.post("/claim", tags=["Skills"])
def claim():
    """Claim pending voter rewards directly."""
    return onchain.claim_rewards()


@app.post("/lyrics", tags=["Skills"])
def lyrics(body: LyricsRequest):
    """Generate song lyrics via Audiera Lyrics Skill."""
    return audiera_music.generate_lyrics(theme=body.theme, styles=body.styles)


@app.post("/music", tags=["Skills"])
def music(body: MusicRequest):
    """Generate a full song via Audiera Music Skill."""
    return audiera_music.generate_music(
        styles=body.styles,
        artist_id=body.artist_id,
        lyrics=body.lyrics,
        inspiration=body.inspiration,
    )


@app.get("/state", tags=["Skills"])
def state():
    """Get the agent's persisted state (votes, stakes, rewards history)."""
    return agent_state.summary()


@app.get("/leaderboard", tags=["Audiera"])
def leaderboard():
    """
    Live Audiera weekly leaderboard — top played songs, community favourite,
    rising track. Real data from Audiera API, updates in real time.
    """
    return get_weekly_leaderboard()


@app.get("/chain-stats", tags=["Audiera"])
def chain_stats():
    """
    Live Audiera chain stats — total users, active users last week,
    NFT supply, BEAT burned this week and all time.
    """
    return get_chain_stats()
