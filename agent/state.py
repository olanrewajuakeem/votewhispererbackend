"""
Persistent agent state — survives across runs.
Stored in data/state.json (gitignored).
"""

import json
import os
import datetime
from typing import Any

import config

_STATE_DEFAULTS = {
    "wallet_address": "",
    "beat_balance": 0.0,
    "vebeat_balance": 0.0,
    "bnb_balance": 0.0,
    "total_staked": 0.0,
    "total_rewards_claimed": 0.0,
    "current_week": 0,
    "votes_this_week": [],          # [{song_id, song_name, weight, tx_hash, timestamp}]
    "reward_history": [],           # [{week, amount, tx_hash, timestamp}]
    "stake_history": [],            # [{amount, tx_hash, timestamp}]
    "posts": [],                    # [{tweet_id, content, timestamp}]
    "analysis_history": [],         # last 5 analyses
    "first_stake_done": False,
    "last_updated": "",
}


def load() -> dict:
    os.makedirs(os.path.dirname(config.STATE_FILE), exist_ok=True)
    if not os.path.exists(config.STATE_FILE):
        return dict(_STATE_DEFAULTS)
    with open(config.STATE_FILE, "r") as f:
        data = json.load(f)
    # merge in any new default keys
    for k, v in _STATE_DEFAULTS.items():
        data.setdefault(k, v)
    return data


def save(state: dict) -> None:
    state["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    os.makedirs(os.path.dirname(config.STATE_FILE), exist_ok=True)
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def update(key: str, value: Any) -> dict:
    state = load()
    state[key] = value
    save(state)
    return state


def append_to(key: str, item: Any) -> dict:
    """Append an item to a list key in state."""
    state = load()
    if key not in state or not isinstance(state[key], list):
        state[key] = []
    state[key].append(item)
    # cap history lists at 50 entries
    if len(state[key]) > 50:
        state[key] = state[key][-50:]
    save(state)
    return state


def record_vote(song_id: str, song_name: str, weight: float, tx_hash: str) -> None:
    append_to("votes_this_week", {
        "song_id": song_id,
        "song_name": song_name,
        "weight": weight,
        "tx_hash": tx_hash,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    })


def record_stake(amount: float, tx_hash: str) -> None:
    state = load()
    append_to("stake_history", {
        "amount": amount,
        "tx_hash": tx_hash,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    })
    state = load()
    state["total_staked"] = state.get("total_staked", 0) + amount
    state["first_stake_done"] = True
    save(state)


def record_reward(week: int, amount: float, tx_hash: str) -> None:
    append_to("reward_history", {
        "week": week,
        "amount": amount,
        "tx_hash": tx_hash,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    })
    state = load()
    state["total_rewards_claimed"] = state.get("total_rewards_claimed", 0) + amount
    save(state)


def record_post(tweet_id: str, content: str) -> None:
    append_to("posts", {
        "tweet_id": tweet_id,
        "content": content,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    })


def summary() -> dict:
    state = load()
    return {
        "wallet": state.get("wallet_address", "not set"),
        "beat_balance": state.get("beat_balance", 0),
        "vebeat_balance": state.get("vebeat_balance", 0),
        "total_staked": state.get("total_staked", 0),
        "total_rewards_claimed": state.get("total_rewards_claimed", 0),
        "votes_this_week_count": len(state.get("votes_this_week", [])),
        "posts_count": len(state.get("posts", [])),
    }
