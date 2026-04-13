"""
X / Twitter posting — real tweepy OAuth 1.0a calls.

Real mode:  posts actual tweets via the X API v2.
Mock mode:  prints what would be posted without sending.
"""

import datetime
from typing import Optional

import config
from agent import state as agent_state
from utils.logger import action, ok, warn, info, err

try:
    import tweepy
    _TWEEPY_OK = True
except ImportError:
    _TWEEPY_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Client factory
# ─────────────────────────────────────────────────────────────────────────────

def _get_client() -> Optional["tweepy.Client"]:
    if not _TWEEPY_OK:
        warn("tweepy not installed — pip install tweepy")
        return None
    if not all([config.X_API_KEY, config.X_API_SECRET, config.X_ACCESS_TOKEN, config.X_ACCESS_TOKEN_SECRET]):
        warn("X API credentials incomplete — check .env")
        return None
    return tweepy.Client(
        consumer_key=config.X_API_KEY,
        consumer_secret=config.X_API_SECRET,
        access_token=config.X_ACCESS_TOKEN,
        access_token_secret=config.X_ACCESS_TOKEN_SECRET,
        bearer_token=config.X_BEARER_TOKEN or None,
        wait_on_rate_limit=True,
    )


def _can_post() -> bool:
    return (
        _TWEEPY_OK
        and not config.MOCK_MODE
        and bool(config.X_API_KEY)
        and bool(config.X_ACCESS_TOKEN)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public posting functions
# ─────────────────────────────────────────────────────────────────────────────

def post_tweet(
    message: str,
    is_thread: bool = False,
    thread_tweets: list[str] | None = None,
) -> dict:
    """Post a single tweet or a thread."""
    thread_tweets = thread_tweets or []
    tweets_to_post = [message] + thread_tweets if is_thread else [message]

    # Truncate to 280 chars each
    tweets_to_post = [t[:280] for t in tweets_to_post]

    action("Posting to X", f"{len(tweets_to_post)} tweet(s)")

    if not _can_post():
        if not config.X_API_KEY:
            info("X not configured — tweet skipped")
            return {"status": "skipped", "reason": "X credentials not configured"}
        return _mock_post(tweets_to_post)

    client = _get_client()
    if not client:
        return {"status": "error", "error": "X client unavailable"}

    try:
        ids = []
        reply_to = None

        for text in tweets_to_post:
            kwargs: dict = {"text": text}
            if reply_to:
                kwargs["in_reply_to_tweet_id"] = reply_to

            resp = client.create_tweet(**kwargs)
            tweet_id = str(resp.data["id"])
            ids.append(tweet_id)
            reply_to = tweet_id
            agent_state.record_post(tweet_id, text)

        ok(f"Posted {len(ids)} tweet(s) — first id: {ids[0]}")
        return {"status": "ok", "tweet_ids": ids, "count": len(ids)}

    except Exception as e:
        err(f"X post failed: {e}")
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Pre-built tweet composers (agent brain calls these for specific situations)
# ─────────────────────────────────────────────────────────────────────────────

def tweet_prediction(ranked_songs: list[dict]) -> dict:
    """Compose and post a prediction tweet from ranked songs."""
    top = ranked_songs[:3]
    picks = " | ".join(f'"{s["name"]}" ({s["score"]:.0%})' for s in top)
    msg = (
        f"🎵 VoteWhisperer weekly prediction is in.\n\n"
        f"High-signal tracks this cycle:\n{picks}\n\n"
        f"Running the data + vibes model 24/7. "
        f"Predictions only — not financial advice. Let's get these into the Top 10.\n\n"
        f"#AudieraAI #BEAT #BinanceAI {config.AUDIERA_X_HANDLE}"
    )[:280]
    return post_tweet(msg)


def tweet_vote_confirmation(votes: list[dict], tx_hash: str) -> dict:
    """Post confirmation of on-chain votes cast."""
    song_names = ", ".join(f'"{v["song_name"]}"' for v in votes[:3])
    pct_list   = " | ".join(f'{v["song_name"]} {int(v["weight"]*100)}%' for v in votes[:3])
    main = (
        f"Just cast my veBEAT votes on-chain. 🗳️\n\n"
        f"Allocation: {pct_list}\n\n"
        f"Tx: {tx_hash[:20]}... (BSCScan 👇)\n\n"
        f"#AudieraAI #BEAT #Beatvote"
    )[:280]

    thread = [
        (
            f"Why these tracks? Strong X engagement + dance-mat compatibility signals. "
            f"Every veBEAT vote = a share of the weekly 5,000 BEAT pool. "
            f"If you haven't staked yet → {config.AUDIERA_STAKE_URL} 🔗 "
            f"#BinanceAI #AudieraAI"
        )[:280]
    ]
    return post_tweet(main, is_thread=True, thread_tweets=thread)


def tweet_reward_claim(amount: float, tx_hash: str) -> dict:
    """Post a reward claim announcement."""
    msg = (
        f"💰 Reward claim landed.\n\n"
        f"+{amount:.2f} $BEAT from the weekly voter pool.\n"
        f"Restaking 80% to compound veBEAT for next week. "
        f"The flywheel keeps spinning.\n\n"
        f"Tx: {tx_hash[:20]}...\n\n"
        f"#AudieraAI #BEAT #BinanceAI"
    )[:280]
    return post_tweet(msg)


def tweet_onboarding_guide() -> dict:
    """Post a Web2-friendly onboarding thread."""
    thread = [
        (
            "🧵 How to earn $BEAT by just voting on music — a quick guide for Web2 users:\n\n"
            "It takes ~5 mins. No prior crypto experience needed. Let's go 👇\n\n"
            "#AudieraAI #BEAT #BinanceAI"
        )[:280],
        (
            "1/ Get $BEAT tokens.\n"
            "Buy on a DEX or earn from Audiera activities.\n"
            f"Token address: {config.BEAT_TOKEN_ADDRESS[:20]}... (BNB Chain)"
        )[:280],
        (
            f"2/ Stake $BEAT → get veBEAT.\n"
            f"Go to {config.AUDIERA_STAKE_URL}\n"
            f"First-time stakers get a 2× veBEAT boost (like a new-user multiplier).\n"
            f"veBEAT = your voting power."
        )[:280],
        (
            f"3/ Vote on Beatvote.\n"
            f"Go to {config.AUDIERA_BEATVOTE_URL}\n"
            f"Use your veBEAT to vote for songs you think will hit the Top 10.\n"
            f"Votes are on-chain — transparent and permanent."
        )[:280],
        (
            "4/ Earn weekly.\n"
            "Every voter who casts at least 1 vote shares a pool of up to 5,000 $BEAT.\n"
            "Bigger veBEAT = bigger share.\n"
            "Rewards claim at week end — then restake and repeat. 🔄"
        )[:280],
        (
            "That's it. You're now a real on-chain music curator earning from your taste.\n\n"
            f"Follow me for weekly predictions and vote signals. "
            f"Let your agent create, play, and earn. 🎵\n\n"
            f"#AudieraAI #BEAT {config.AUDIERA_X_HANDLE}"
        )[:280],
    ]
    return post_tweet(thread[0], is_thread=True, thread_tweets=thread[1:])


# ─────────────────────────────────────────────────────────────────────────────
# Mock posting
# ─────────────────────────────────────────────────────────────────────────────

def _mock_post(tweets: list[str]) -> dict:
    from utils.logger import console
    from rich.panel import Panel
    from rich import box
    info("Mock post (MOCK_MODE=true) — would post:")
    for i, t in enumerate(tweets):
        console.print(
            Panel(t, title=f"[bold cyan]Tweet {i+1}/{len(tweets)}[/bold cyan]",
                  border_style="cyan", box=box.ROUNDED)
        )
    mock_ids = [f"mock_{i}_{datetime.datetime.utcnow().timestamp():.0f}" for i in range(len(tweets))]
    for mid, text in zip(mock_ids, tweets):
        agent_state.record_post(mid, text)
    ok(f"Mock: would have posted {len(tweets)} tweet(s)")
    return {"status": "ok", "mode": "mock", "tweet_ids": mock_ids, "count": len(tweets)}
