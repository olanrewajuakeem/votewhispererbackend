"""
On-chain interactions — BNB Chain / BSC.

Real mode:  web3.py + wallet private key.
Mock mode:  returns realistic synthetic responses for demos.

Contracts (verified on BSC):
  BEAT token:  0xcf3232b85b43bca90e51d38cc06cc8bb8c8a3e36
  Voting:      0xe554229ba6ec7ceeacd13a9bb48d812bf705c292  (TransparentUpgradeableProxy)
  Staking:     0x0d956565253b74b84c4daa51e026bbb4c215020e  (TransparentUpgradeableProxy)
"""

import datetime
import secrets
from typing import Any

import config
from agent import state as agent_state
from utils.logger import action, ok, warn, info, err

def _get_active_address() -> str:
    """Return connected wallet address (session > env > empty)."""
    try:
        from skills.wallet_session import get_wallet_address
        return get_wallet_address()
    except Exception:
        return config.WALLET_ADDRESS or ""

# ── Optional web3 import ─────────────────────────────────────────────────────
try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    _WEB3_OK = True
except ImportError:
    _WEB3_OK = False

# ─────────────────────────────────────────────────────────────────────────────
# ABIs
# ─────────────────────────────────────────────────────────────────────────────

ERC20_ABI = [
    {"name": "balanceOf",  "type": "function",
     "inputs":  [{"name": "account", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view"},
    {"name": "approve",    "type": "function",
     "inputs":  [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
     "outputs": [{"name": "", "type": "bool"}],    "stateMutability": "nonpayable"},
    {"name": "allowance",  "type": "function",
     "inputs":  [{"name": "owner",   "type": "address"}, {"name": "spender", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view"},
    {"name": "decimals",   "type": "function",
     "inputs":  [],
     "outputs": [{"name": "", "type": "uint8"}],   "stateMutability": "view"},
]

# Staking ABI — vote-escrow pattern
# Contract: 0x0d956565253b74b84c4daa51e026bbb4c215020e
STAKING_ABI = [
    {"name": "stake",     "type": "function",
     "inputs":  [{"name": "amount", "type": "uint256"}],
     "outputs": [],                                        "stateMutability": "nonpayable"},
    {"name": "restake",   "type": "function",
     "inputs":  [],
     "outputs": [],                                        "stateMutability": "nonpayable"},
    {"name": "withdraw",  "type": "function",
     "inputs":  [{"name": "amount", "type": "uint256"}],
     "outputs": [],                                        "stateMutability": "nonpayable"},
    {"name": "balanceOf", "type": "function",
     "inputs":  [{"name": "account", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}],         "stateMutability": "view"},
    {"name": "veBEATOf",  "type": "function",
     "inputs":  [{"name": "account", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}],         "stateMutability": "view"},
    {"name": "accelerationActive", "type": "function",
     "inputs":  [{"name": "account", "type": "address"}],
     "outputs": [{"name": "", "type": "bool"}],            "stateMutability": "view"},
]

# Voting ABI — real functions observed on-chain for contract
# 0xe554229ba6ec7ceeacd13a9bb48d812bf705c292
# Functions confirmed from tx history: Vote, SetVotingSongs, CountingVotes, Claim, Withdraw
VOTING_ABI = [
    # Write
    {"name": "vote",          "type": "function",
     "inputs":  [{"name": "songId", "type": "uint256"}, {"name": "amount", "type": "uint256"}],
     "outputs": [],                                           "stateMutability": "nonpayable"},
    {"name": "voteBatch",     "type": "function",
     "inputs":  [
         {"name": "songIds", "type": "uint256[]"},
         {"name": "amounts", "type": "uint256[]"},
     ],
     "outputs": [],                                           "stateMutability": "nonpayable"},
    {"name": "claim",         "type": "function",
     "inputs":  [],
     "outputs": [{"name": "amount", "type": "uint256"}],     "stateMutability": "nonpayable"},
    {"name": "withdraw",      "type": "function",
     "inputs":  [],
     "outputs": [],                                           "stateMutability": "nonpayable"},
    # Read
    {"name": "getVotingSongs","type": "function",
     "inputs":  [],
     "outputs": [
         {
             "name": "",
             "type": "tuple[]",
             "components": [
                 {"name": "songId",      "type": "uint256"},
                 {"name": "title",       "type": "string"},
                 {"name": "artist",      "type": "string"},
                 {"name": "voteCount",   "type": "uint256"},
                 {"name": "submittedAt", "type": "uint256"},
             ],
         }
     ],
     "stateMutability": "view"},
    {"name": "getVotesForSong", "type": "function",
     "inputs":  [{"name": "songId", "type": "uint256"}],
     "outputs": [{"name": "", "type": "uint256"}],            "stateMutability": "view"},
    {"name": "pendingRewards",  "type": "function",
     "inputs":  [{"name": "voter", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}],            "stateMutability": "view"},
    {"name": "currentWeek",     "type": "function",
     "inputs":  [],
     "outputs": [{"name": "", "type": "uint256"}],            "stateMutability": "view"},
    {"name": "totalVotes",      "type": "function",
     "inputs":  [],
     "outputs": [{"name": "", "type": "uint256"}],            "stateMutability": "view"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_w3() -> "Web3":
    w3 = Web3(Web3.HTTPProvider(config.BSC_RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to BSC node: {config.BSC_RPC_URL}")
    return w3


def _is_real_private_key(key: str) -> bool:
    if not key or "your_private_key" in key or "..." in key:
        return False
    k = key[2:] if key.startswith("0x") else key
    return len(k) == 64 and all(c in "0123456789abcdefABCDEF" for c in k)


def _is_real_wallet_address(addr: str) -> bool:
    if not addr or "your_wallet_address" in addr or "..." in addr:
        return False
    return addr.startswith("0x") and len(addr) == 42


def _can_use_chain() -> bool:
    return (
        _WEB3_OK
        and _is_real_private_key(config.WALLET_PRIVATE_KEY)
        and _is_real_wallet_address(config.WALLET_ADDRESS)
        and bool(config.STAKING_CONTRACT_ADDRESS)
        and bool(config.VOTING_CONTRACT_ADDRESS)
        and not config.MOCK_MODE
    )


def _to_wei(amount: float, decimals: int = 18) -> int:
    return int(amount * 10 ** decimals)


def _from_wei(amount: int, decimals: int = 18) -> float:
    return amount / 10 ** decimals


def _fake_tx() -> str:
    return "0x" + secrets.token_hex(32)


# ─────────────────────────────────────────────────────────────────────────────
# Public skill functions
# ─────────────────────────────────────────────────────────────────────────────

def get_wallet_info() -> dict:
    action("Fetching wallet balances")

    active_address = _get_active_address()

    # Read-only balance check — works with just a wallet address (no private key needed)
    if active_address and active_address not in ("0x...your_wallet_address...", ""):
        try:
            from skills.wallet_session import _fetch_balances
            balances = _fetch_balances(active_address)
            result = {
                "status": "ok",
                "address": active_address,
                **balances,
            }
            ok(f"BNB={result['bnb_balance']:.4f}  BEAT={result['beat_balance']:.2f}  veBEAT={result['vebeat_balance']:.2f}")
            _sync_state(result)
            return result
        except Exception:
            pass

    if not _can_use_chain():
        return _mock_wallet_info()

    try:
        w3   = _get_w3()
        addr = Web3.to_checksum_address(config.WALLET_ADDRESS)

        bnb_bal  = _from_wei(w3.eth.get_balance(addr))

        beat     = w3.eth.contract(
            address=Web3.to_checksum_address(config.BEAT_TOKEN_ADDRESS), abi=ERC20_ABI)
        beat_bal = _from_wei(beat.functions.balanceOf(addr).call())

        staking  = w3.eth.contract(
            address=Web3.to_checksum_address(config.STAKING_CONTRACT_ADDRESS), abi=STAKING_ABI)
        vebeat   = _from_wei(staking.functions.veBEATOf(addr).call())
        accel    = staking.functions.accelerationActive(addr).call()

        result = {
            "status": "ok",
            "address": config.WALLET_ADDRESS,
            "bnb_balance":   round(bnb_bal, 6),
            "beat_balance":  round(beat_bal, 4),
            "vebeat_balance":round(vebeat, 4),
            "first_stake_acceleration_active": accel,
        }
        ok(f"BNB={bnb_bal:.4f}  BEAT={beat_bal:.2f}  veBEAT={vebeat:.2f}")
        _sync_state(result)
        return result

    except Exception as e:
        err(f"Chain read failed: {e}")
        return {"status": "error", "error": str(e)}


def stake_beat(amount: float) -> dict:
    action(f"Staking {amount} $BEAT → veBEAT")

    if not _can_use_chain():
        if not _is_real_private_key(config.WALLET_PRIVATE_KEY):
            warn("Wallet not configured — staking simulated")
            return _mock_stake(amount)
        return _mock_stake(amount)

    try:
        w3   = _get_w3()
        acct = w3.eth.account.from_key(config.WALLET_PRIVATE_KEY)
        addr = Web3.to_checksum_address(config.WALLET_ADDRESS)

        beat    = w3.eth.contract(
            address=Web3.to_checksum_address(config.BEAT_TOKEN_ADDRESS), abi=ERC20_ABI)
        staking = w3.eth.contract(
            address=Web3.to_checksum_address(config.STAKING_CONTRACT_ADDRESS), abi=STAKING_ABI)

        amount_wei = _to_wei(amount)
        nonce = w3.eth.get_transaction_count(addr)

        # 1. Approve staking contract to spend BEAT
        approve_tx = beat.functions.approve(
            Web3.to_checksum_address(config.STAKING_CONTRACT_ADDRESS), amount_wei
        ).build_transaction({"from": addr, "nonce": nonce, "chainId": config.BSC_CHAIN_ID})
        signed = acct.sign_transaction(approve_tx)
        w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed.rawTransaction))

        # 2. Stake
        nonce += 1
        stake_tx = staking.functions.stake(amount_wei).build_transaction(
            {"from": addr, "nonce": nonce, "chainId": config.BSC_CHAIN_ID})
        signed  = acct.sign_transaction(stake_tx)
        receipt = w3.eth.wait_for_transaction_receipt(
            w3.eth.send_raw_transaction(signed.rawTransaction))

        tx_hash = receipt.transactionHash.hex()
        ok(f"Staked {amount} BEAT — tx: {tx_hash[:18]}...")
        agent_state.record_stake(amount, tx_hash)
        return {"status": "ok", "amount_staked": amount, "tx_hash": tx_hash}

    except Exception as e:
        err(f"Stake failed: {e}")
        return {"status": "error", "error": str(e)}


def cast_votes(votes: list[dict]) -> dict:
    """
    votes: [{"song_id": str, "song_name": str, "weight": float (0..1)}, ...]
    Weights are normalised to veBEAT amounts for the contract call.
    """
    action(f"Casting votes on {len(votes)} songs")

    if not _can_use_chain():
        if not _is_real_private_key(config.WALLET_PRIVATE_KEY):
            warn("Wallet not configured — votes simulated")
        return _mock_cast_votes(votes)

    try:
        w3     = _get_w3()
        acct   = w3.eth.account.from_key(config.WALLET_PRIVATE_KEY)
        addr   = Web3.to_checksum_address(config.WALLET_ADDRESS)
        voting = w3.eth.contract(
            address=Web3.to_checksum_address(config.VOTING_CONTRACT_ADDRESS), abi=VOTING_ABI)

        # Get current veBEAT balance to split across songs
        staking = w3.eth.contract(
            address=Web3.to_checksum_address(config.STAKING_CONTRACT_ADDRESS), abi=STAKING_ABI)
        vebeat_wei = staking.functions.veBEATOf(addr).call()

        total_w  = sum(v["weight"] for v in votes) or 1
        song_ids = [int(v["song_id"]) if str(v["song_id"]).isdigit()
                    else abs(hash(v["song_id"])) % 10000 for v in votes]
        amounts  = [int(v["weight"] / total_w * vebeat_wei) for v in votes]

        nonce  = w3.eth.get_transaction_count(addr)
        tx     = voting.functions.voteBatch(song_ids, amounts).build_transaction(
            {"from": addr, "nonce": nonce, "chainId": config.BSC_CHAIN_ID})
        signed  = acct.sign_transaction(tx)
        receipt = w3.eth.wait_for_transaction_receipt(
            w3.eth.send_raw_transaction(signed.rawTransaction))
        tx_hash = receipt.transactionHash.hex()

        for v in votes:
            agent_state.record_vote(v["song_id"], v["song_name"], v["weight"], tx_hash)

        ok(f"Votes cast — tx: {tx_hash[:18]}...")
        return {"status": "ok", "votes": votes, "tx_hash": tx_hash}

    except Exception as e:
        err(f"Vote failed: {e}")
        return {"status": "error", "error": str(e)}


def claim_rewards() -> dict:
    action("Claiming weekly voter rewards")

    if not _can_use_chain():
        return _mock_claim_rewards()

    try:
        w3     = _get_w3()
        acct   = w3.eth.account.from_key(config.WALLET_PRIVATE_KEY)
        addr   = Web3.to_checksum_address(config.WALLET_ADDRESS)
        voting = w3.eth.contract(
            address=Web3.to_checksum_address(config.VOTING_CONTRACT_ADDRESS), abi=VOTING_ABI)

        pending = _from_wei(voting.functions.pendingRewards(addr).call())

        if pending < 0.001:
            info("No pending rewards to claim.")
            return {"status": "ok", "amount": 0, "message": "No pending rewards"}

        nonce   = w3.eth.get_transaction_count(addr)
        tx      = voting.functions.claim().build_transaction(
            {"from": addr, "nonce": nonce, "chainId": config.BSC_CHAIN_ID})
        signed  = acct.sign_transaction(tx)
        receipt = w3.eth.wait_for_transaction_receipt(
            w3.eth.send_raw_transaction(signed.rawTransaction))
        tx_hash = receipt.transactionHash.hex()

        week = voting.functions.currentWeek().call()
        ok(f"Claimed {pending:.2f} BEAT — tx: {tx_hash[:18]}...")
        agent_state.record_reward(week, pending, tx_hash)
        return {"status": "ok", "amount": pending, "tx_hash": tx_hash, "week": week}

    except Exception as e:
        err(f"Claim failed: {e}")
        return {"status": "error", "error": str(e)}


def get_voting_songs() -> dict:
    """Fetch this week's songs directly from the voting contract."""
    action("Reading current Beatvote songs from contract")

    if not _WEB3_OK or not config.VOTING_CONTRACT_ADDRESS:
        return _mock_voting_songs()

    try:
        w3     = _get_w3()
        voting = w3.eth.contract(
            address=Web3.to_checksum_address(config.VOTING_CONTRACT_ADDRESS), abi=VOTING_ABI)

        week = voting.functions.currentWeek().call()
        raw  = voting.functions.getVotingSongs().call()

        songs = [
            {
                "song_id":      str(s[0]),
                "title":        s[1],
                "artist":       s[2],
                "vote_count":   s[3],
                "submitted_at": s[4],
            }
            for s in raw
        ]
        ok(f"Week {week}: {len(songs)} songs on Beatvote")
        return {"status": "ok", "week": week, "songs": songs, "total": len(songs)}

    except Exception as e:
        warn(f"Contract read failed ({e}) — returning mock songs")
        return _mock_voting_songs()


# ─────────────────────────────────────────────────────────────────────────────
# Mock responses
# ─────────────────────────────────────────────────────────────────────────────

def _mock_wallet_info() -> dict:
    info("Mock wallet info (MOCK_MODE=true or no keys)")
    result = {
        "status": "ok",
        "mode":   "mock",
        "address":      config.WALLET_ADDRESS or "0xMockAddr...1234",
        "bnb_balance":  0.08,
        "beat_balance": 2500.0,
        "vebeat_balance": 3200.0,
        "first_stake_acceleration_active": True,
    }
    ok("BNB=0.0800  BEAT=2500.00  veBEAT=3200.00  (2× accel active)")
    _sync_state(result)
    return result


def _mock_stake(amount: float) -> dict:
    info(f"Mock stake: {amount} BEAT → veBEAT")
    tx_hash = _fake_tx()
    vebeat_received = amount * 2.0
    ok(f"Mock staked {amount} BEAT → {vebeat_received} veBEAT | tx: {tx_hash[:18]}...")
    agent_state.record_stake(amount, tx_hash)
    s = agent_state.load()
    s["beat_balance"]   = max(0, s.get("beat_balance", 2500) - amount)
    s["vebeat_balance"] = s.get("vebeat_balance", 3200) + vebeat_received
    agent_state.save(s)
    return {
        "status": "ok", "mode": "mock",
        "amount_staked": amount, "vebeat_received": vebeat_received,
        "acceleration_applied": True, "tx_hash": tx_hash,
    }


def _mock_cast_votes(votes: list[dict]) -> dict:
    info(f"Mock votes: {[v['song_name'] for v in votes]}")
    tx_hash = _fake_tx()
    for v in votes:
        agent_state.record_vote(v["song_id"], v["song_name"], v["weight"], tx_hash)
    ok(f"Mock votes cast — tx: {tx_hash[:18]}...")
    return {
        "status": "ok", "mode": "mock",
        "votes_cast": len(votes), "votes": votes, "tx_hash": tx_hash,
    }


def _mock_claim_rewards() -> dict:
    info("Mock reward claim")
    import random
    amount  = round(random.uniform(80, 320), 2)
    tx_hash = _fake_tx()
    week    = 12
    ok(f"Mock claimed {amount} BEAT — tx: {tx_hash[:18]}...")
    agent_state.record_reward(week, amount, tx_hash)
    s = agent_state.load()
    s["beat_balance"] = s.get("beat_balance", 0) + amount
    agent_state.save(s)
    return {
        "status": "ok", "mode": "mock",
        "amount": amount, "week": week, "tx_hash": tx_hash,
    }


def _mock_voting_songs() -> dict:
    import datetime as dt
    now = dt.datetime.utcnow()
    return {
        "status": "ok", "mode": "mock", "week": 12,
        "songs": [
            {"song_id": "1", "title": "Neon Pulse",        "artist": "Kira 0x4154",  "vote_count": 28400, "submitted_at": int((now - dt.timedelta(hours=4)).timestamp())},
            {"song_id": "2", "title": "Sigma Drift",       "artist": "Ray 0x4245",   "vote_count": 21000, "submitted_at": int((now - dt.timedelta(hours=12)).timestamp())},
            {"song_id": "3", "title": "Kira Wave",         "artist": "Kira 0x4154",  "vote_count": 41000, "submitted_at": int((now - dt.timedelta(hours=2)).timestamp())},
            {"song_id": "4", "title": "Ray Drop",          "artist": "Ray 0x4245",   "vote_count": 18000, "submitted_at": int((now - dt.timedelta(hours=18)).timestamp())},
            {"song_id": "5", "title": "Blockchain Bounce", "artist": "AudieraAI",    "vote_count": 9500,  "submitted_at": int((now - dt.timedelta(hours=36)).timestamp())},
            {"song_id": "6", "title": "Gyatt Protocol",   "artist": "SigmaBeats",   "vote_count": 15200, "submitted_at": int((now - dt.timedelta(hours=8)).timestamp())},
            {"song_id": "7", "title": "Aura Frequency",   "artist": "NPC Collective","vote_count": 7800,  "submitted_at": int((now - dt.timedelta(hours=24)).timestamp())},
        ],
        "total": 7,
    }


def _sync_state(wallet_info: dict) -> None:
    s = agent_state.load()
    s["wallet_address"]  = wallet_info.get("address", s["wallet_address"])
    s["beat_balance"]    = wallet_info.get("beat_balance",   s["beat_balance"])
    s["vebeat_balance"]  = wallet_info.get("vebeat_balance", s["vebeat_balance"])
    s["bnb_balance"]     = wallet_info.get("bnb_balance",    s["bnb_balance"])
    agent_state.save(s)
