"""
Wallet session management — connects user wallet via Audiera auth token.

Flow:
  1. Frontend sends Audiera auth_token (JWT from browser cookie)
  2. We decode it to get wallet address (no secret needed — just base64 decode)
  3. We fetch live BNB/BEAT/veBEAT balances from BSC for that address
  4. Session stored in memory + state.json for the server lifetime

No private key needed for read-only balance display.
Private key only needed for sending transactions (staking/voting).
"""

import base64
import json
import datetime
import requests as _requests

import config
from agent import state as agent_state
from utils.logger import action, ok, warn, info, err

# In-memory session (persists while server is running)
_session: dict = {}

# ─────────────────────────────────────────────────────────────────────────────
# JWT decode (no signature check — we trust Audiera's token)
# ─────────────────────────────────────────────────────────────────────────────

def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verifying signature."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        # Add padding
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        err(f"JWT decode failed: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def connect_address(wallet_address: str) -> dict:
    """
    Connect directly with a wallet address (from MetaMask).
    No JWT needed — just the address. Fetches live BSC balances.
    """
    action(f"Connecting wallet: {wallet_address[:10]}...")

    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        return {"status": "error", "error": "Invalid wallet address"}

    balances = _fetch_balances(wallet_address)

    _session["wallet_address"] = wallet_address
    _session["user_id"]        = ""
    _session["auth_token"]     = ""
    _session["connected_at"]   = datetime.datetime.utcnow().isoformat() + "Z"
    _session["expires_at"]     = ""
    _session.update(balances)

    s = agent_state.load()
    s["wallet_address"] = wallet_address
    s["beat_balance"]   = balances.get("beat_balance", 0)
    s["vebeat_balance"] = balances.get("vebeat_balance", 0)
    s["bnb_balance"]    = balances.get("bnb_balance", 0)
    agent_state.save(s)

    ok(f"Connected: {wallet_address} | BNB={balances.get('bnb_balance',0):.4f} BEAT={balances.get('beat_balance',0):.2f} veBEAT={balances.get('vebeat_balance',0):.2f}")

    return {
        "status":          "ok",
        "wallet_address":  wallet_address,
        "bnb_balance":     balances.get("bnb_balance", 0),
        "beat_balance":    balances.get("beat_balance", 0),
        "vebeat_balance":  balances.get("vebeat_balance", 0),
        "first_stake_acceleration_active": balances.get("first_stake_acceleration_active", False),
        "connected_at":    _session["connected_at"],
    }


def connect(auth_token: str) -> dict:
    """
    Connect a wallet using the Audiera auth_token JWT.
    Decodes the token to get wallet address, then fetches live balances.
    """
    action("Connecting wallet via Audiera auth token")

    payload = _decode_jwt_payload(auth_token)
    if not payload:
        return {"status": "error", "error": "Invalid auth token"}

    wallet_address = payload.get("wallet", "")
    user_id        = payload.get("sub", "")
    exp            = payload.get("exp", 0)

    if not wallet_address:
        return {"status": "error", "error": "No wallet address in token"}

    # Check expiry
    now = datetime.datetime.utcnow().timestamp()
    if exp and now > exp:
        return {"status": "error", "error": "Auth token has expired — reconnect on Audiera"}

    ok(f"Wallet from token: {wallet_address[:10]}...")

    # Fetch live balances from BSC
    balances = _fetch_balances(wallet_address)

    # Store session
    _session["wallet_address"] = wallet_address
    _session["user_id"]        = user_id
    _session["auth_token"]     = auth_token
    _session["connected_at"]   = datetime.datetime.utcnow().isoformat() + "Z"
    _session["expires_at"]     = datetime.datetime.utcfromtimestamp(exp).isoformat() + "Z" if exp else ""
    _session.update(balances)

    # Sync to state
    s = agent_state.load()
    s["wallet_address"] = wallet_address
    s["beat_balance"]   = balances.get("beat_balance", 0)
    s["vebeat_balance"] = balances.get("vebeat_balance", 0)
    s["bnb_balance"]    = balances.get("bnb_balance", 0)
    agent_state.save(s)

    ok(f"Connected: {wallet_address} | BNB={balances.get('bnb_balance',0):.4f} BEAT={balances.get('beat_balance',0):.2f} veBEAT={balances.get('vebeat_balance',0):.2f}")

    return {
        "status":          "ok",
        "wallet_address":  wallet_address,
        "bnb_balance":     balances.get("bnb_balance", 0),
        "beat_balance":    balances.get("beat_balance", 0),
        "vebeat_balance":  balances.get("vebeat_balance", 0),
        "first_stake_acceleration_active": balances.get("first_stake_acceleration_active", False),
        "connected_at":    _session["connected_at"],
        "expires_at":      _session.get("expires_at", ""),
    }


def get_session() -> dict:
    """Return current session, or empty dict if not connected."""
    return dict(_session)


def is_connected() -> bool:
    return bool(_session.get("wallet_address"))


def get_wallet_address() -> str:
    return _session.get("wallet_address", config.WALLET_ADDRESS or "")


def disconnect() -> dict:
    _session.clear()
    ok("Wallet disconnected")
    return {"status": "ok", "message": "Disconnected"}


# ─────────────────────────────────────────────────────────────────────────────
# Live balance fetching from BSC
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_balances(wallet_address: str) -> dict:
    """Fetch BNB, BEAT, and veBEAT balances for a wallet address."""
    try:
        from web3 import Web3
        from web3.middleware import ExtraDataToPOAMiddleware

        w3 = Web3(Web3.HTTPProvider(config.BSC_RPC_URL))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not w3.is_connected():
            warn("BSC node unreachable — showing zero balances")
            return _zero_balances(wallet_address)

        addr = Web3.to_checksum_address(wallet_address)

        # BNB balance
        bnb = w3.eth.get_balance(addr) / 1e18

        # BEAT balance (ERC20)
        beat_abi = [{"name": "balanceOf", "type": "function",
                     "inputs": [{"name": "a", "type": "address"}],
                     "outputs": [{"name": "", "type": "uint256"}],
                     "stateMutability": "view"}]
        beat = w3.eth.contract(
            address=Web3.to_checksum_address(config.BEAT_TOKEN_ADDRESS), abi=beat_abi)
        beat_bal = beat.functions.balanceOf(addr).call() / 1e18

        # veBEAT balance (staking contract)
        vebeat_abi = [
            {"name": "veBEATOf", "type": "function",
             "inputs": [{"name": "a", "type": "address"}],
             "outputs": [{"name": "", "type": "uint256"}],
             "stateMutability": "view"},
            {"name": "accelerationActive", "type": "function",
             "inputs": [{"name": "a", "type": "address"}],
             "outputs": [{"name": "", "type": "bool"}],
             "stateMutability": "view"},
        ]
        staking = w3.eth.contract(
            address=Web3.to_checksum_address(config.STAKING_CONTRACT_ADDRESS), abi=vebeat_abi)

        try:
            vebeat = staking.functions.veBEATOf(addr).call() / 1e18
            accel  = staking.functions.accelerationActive(addr).call()
        except Exception:
            vebeat = 0.0
            accel  = False

        return {
            "bnb_balance":    round(bnb, 6),
            "beat_balance":   round(beat_bal, 4),
            "vebeat_balance": round(vebeat, 4),
            "first_stake_acceleration_active": accel,
        }

    except ImportError:
        warn("web3 not installed — showing zero balances")
        return _zero_balances(wallet_address)
    except Exception as e:
        warn(f"Balance fetch failed: {e} — showing zero balances")
        return _zero_balances(wallet_address)


def _zero_balances(wallet_address: str) -> dict:
    return {
        "bnb_balance": 0.0,
        "beat_balance": 0.0,
        "vebeat_balance": 0.0,
        "first_stake_acceleration_active": False,
    }
